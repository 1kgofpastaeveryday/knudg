do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'knudg_app') then
    create role knudg_app;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'knudg_worker') then
    create role knudg_worker;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'knudg_readonly_ops') then
    create role knudg_readonly_ops;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'knudg_migration') then
    create role knudg_migration bypassrls;
  end if;
end
$$;

revoke create on schema public from public;
create schema if not exists knudg_private;
create schema if not exists knudg_crypto;
create extension if not exists pgcrypto with schema knudg_crypto;

revoke all on schema knudg_private from public;
revoke all on schema knudg_crypto from public;
grant usage on schema public to knudg_app, knudg_worker, knudg_readonly_ops;
grant usage on schema knudg_private to knudg_app, knudg_worker;

revoke all on function knudg_crypto.hmac(bytea, bytea, text) from public;
revoke all on function knudg_crypto.digest(bytea, text) from public;

create sequence if not exists event_stream_position_seq as bigint;

create table if not exists tenants (
  id uuid primary key,
  slug text not null unique,
  name text not null,
  created_at timestamptz not null default now(),
  disabled_at timestamptz null
);

create table if not exists principals (
  id uuid primary key,
  principal_type text not null check (principal_type in (
    'human_user', 'delegated_client', 'worker', 'reviewer', 'tenant_admin', 'platform_admin'
  )),
  display_name text not null,
  external_subject text null,
  disabled_at timestamptz null,
  created_at timestamptz not null default now()
);

create table if not exists external_identities (
  id uuid primary key,
  principal_id uuid not null references principals(id) on delete restrict,
  issuer text not null,
  subject text not null,
  audience text not null,
  identity_provider_id text not null,
  provider_key_id text null,
  verified_at timestamptz not null,
  disabled_at timestamptz null,
  created_at timestamptz not null default now()
);
create unique index if not exists external_identities_active_identity_uidx
  on external_identities(issuer, subject, identity_provider_id, audience)
  where disabled_at is null;

create table if not exists claim_signing_keys (
  kid text primary key,
  alg text not null check (alg = 'HS256'),
  verify_secret bytea not null,
  not_before timestamptz not null,
  not_after timestamptz null,
  disabled_at timestamptz null,
  custody_profile text not null default 'local_hs256_dev_envelope_required'
    check (custody_profile = 'local_hs256_dev_envelope_required'),
  created_at timestamptz not null default now()
);

create table if not exists request_claim_contexts (
  backend_pid integer not null,
  transaction_id xid8 not null,
  request_id uuid not null,
  claims_digest text not null,
  principal_id uuid not null references principals(id) on delete restrict,
  tenant_id uuid not null references tenants(id) on delete restrict,
  actor_role text not null,
  namespace_ids uuid[] not null,
  grant_snapshot_version bigint not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  primary key (backend_pid, transaction_id, request_id)
);

create table if not exists schema_migrations (
  version text primary key,
  checksum text not null,
  state text not null check (state in ('applying', 'applied', 'rolling_back', 'rolled_back', 'failed')),
  started_at timestamptz not null,
  finished_at timestamptz null,
  step text null,
  error_class text null
);

create table if not exists event_stream_positions (
  event_stream_position bigint primary key,
  tenant_id uuid not null references tenants(id) on delete restrict,
  event_source_type text not null check (event_source_type in ('card', 'domain')),
  card_event_id uuid null,
  domain_event_id uuid null,
  created_at timestamptz not null default now(),
  unique (tenant_id, event_stream_position),
  check (
    (event_source_type = 'card' and card_event_id is not null and domain_event_id is null)
    or (event_source_type = 'domain' and domain_event_id is not null and card_event_id is null)
  )
);

create table if not exists approval_challenges (
  tenant_id uuid not null,
  id uuid not null,
  subject_id uuid not null references principals(id) on delete restrict,
  namespace_id uuid null,
  consent_scope text not null,
  artifact_type text not null,
  artifact_id uuid not null,
  card_version_id uuid null,
  artifact_digest text not null,
  policy_version text not null,
  policy_digest text not null,
  challenge_digest text not null,
  origin text not null,
  expires_at timestamptz not null,
  used_at timestamptz null,
  used_by_consent_id uuid null,
  invalidated_at timestamptz null,
  created_by uuid not null references principals(id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id),
  check ((used_at is null and used_by_consent_id is null) or (used_at is not null and used_by_consent_id is not null))
);

create table if not exists lookup_catalog (
  lookup_table text not null,
  key text not null,
  label text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  valid_from_schema_version text not null default '0001_m0_schema',
  valid_to_schema_version text null,
  retired_at timestamptz null,
  primary key (lookup_table, key),
  check ((is_active and retired_at is null) or (not is_active))
);

create table if not exists card_statuses (primary key (key)) inherits (lookup_catalog);
create table if not exists card_event_types (primary key (key)) inherits (lookup_catalog);
create table if not exists domain_event_types (primary key (key)) inherits (lookup_catalog);
create table if not exists actor_roles (primary key (key)) inherits (lookup_catalog);
create table if not exists outcome_types (primary key (key)) inherits (lookup_catalog);
create table if not exists quality_states (primary key (key)) inherits (lookup_catalog);
create table if not exists verification_statuses (primary key (key)) inherits (lookup_catalog);
create table if not exists evidence_strengths (primary key (key)) inherits (lookup_catalog);
create table if not exists namespace_visibilities (primary key (key)) inherits (lookup_catalog);
create table if not exists revocation_subject_types (primary key (key)) inherits (lookup_catalog);
create table if not exists consent_scopes (primary key (key)) inherits (lookup_catalog);
create table if not exists artifact_types (primary key (key)) inherits (lookup_catalog);
create table if not exists card_edge_types (primary key (key)) inherits (lookup_catalog);

create or replace function knudg_private.seed_lookup(table_name text, keys text[])
returns void
language plpgsql
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  key_value text;
begin
  foreach key_value in array keys loop
    execute format(
      'insert into %I(lookup_table, key, label) values (%L, $1, $2) on conflict (key) do nothing',
      table_name,
      table_name
    )
    using key_value, replace(initcap(replace(key_value, '_', ' ')), ' ', ' ');
  end loop;
end;
$$;

select knudg_private.seed_lookup('card_statuses', array[
  'candidate_created','pending_admission','deferred','pending_redaction','pending_review',
  'awaiting_user_approval','approved_private','approved_for_publication','discard_pending',
  'publication_withdrawn','published','indexed_hot','indexed_main','rejected','superseded',
  'deprecated','revoked'
]);
select knudg_private.seed_lookup('card_event_types', array[
  'card_created','admission_accepted','version_created','admission_deferred',
  'redaction_requested','review_requested','redaction_completed','user_approval_requested',
  'private_approved','publication_approved','approval_withdrawn','discard_requested',
  'discard_restored','approval_digest_invalidated','reviewer_rejected_after_approval',
  'reviewer_requested_reredaction','reviewer_published','hot_indexed','main_indexed',
  'rejected','superseded','deprecated','revoked','dispute_recorded'
]);
select knudg_private.seed_lookup('domain_event_types', array[
  'tenant_revoked','namespace_revoked','source_artifact_revoked','derived_artifact_revoked',
  'search_index_manifest_revoked','consent_granted','consent_terminated',
  'approval_challenge_created','approval_challenge_invalidated','operational_case_opened',
  'operational_case_closed','index_manifest_created','index_manifest_activated'
]);
select knudg_private.seed_lookup('actor_roles', array[
  'app_user','agent_delegated_user','ingestion_worker','approval_challenge_worker',
  'redaction_worker','review_worker','index_worker','compaction_worker','revocation_worker',
  'billing_worker','reviewer','tenant_admin','platform_admin','break_glass_admin'
]);
select knudg_private.seed_lookup('outcome_types', array['solved','failed_only','inconclusive','unknown_clarified']);
select knudg_private.seed_lookup('quality_states', array['unreviewed','solved_once','solved_many','verified','disputed']);
select knudg_private.seed_lookup('verification_statuses', array['active','expired','revoked','superseded']);
select knudg_private.seed_lookup('evidence_strengths', array['single_session','multi_session','reproduced','external_reference','operator_judgment']);
select knudg_private.seed_lookup('namespace_visibilities', array['private','team','enterprise','public']);
select knudg_private.seed_lookup('revocation_subject_types', array['tenant','namespace','card','card_version','source_artifact','derived_artifact','search_index_manifest']);
select knudg_private.seed_lookup('consent_scopes', array[
  'private_candidate_collection','private_retention','team_namespace_grant','public_publication',
  'intake_review_escrow','raw_source_retention','derived_artifact','commercial_use',
  'model_eval_use'
]);
select knudg_private.seed_lookup('artifact_types', array['card_version','source_artifact','derived_artifact','search_index_manifest','policy_document']);
select knudg_private.seed_lookup('card_edge_types', array['contradicts','supersedes','duplicate_of','variant_of','deprecated_by']);

create table if not exists tenant_memberships (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  principal_id uuid not null references principals(id) on delete restrict,
  membership_role text not null check (membership_role in ('member', 'admin', 'reviewer', 'worker', 'break_glass_admin')),
  status text not null check (status in ('active', 'revoked', 'expired')),
  created_at timestamptz not null default now(),
  valid_from timestamptz not null,
  expires_at timestamptz null,
  revoked_at timestamptz null,
  effective_until timestamptz null,
  grant_version bigint not null default 1,
  primary key (tenant_id, id)
);
create unique index if not exists tenant_memberships_open_uidx
  on tenant_memberships(tenant_id, principal_id, membership_role)
  where status = 'active' and revoked_at is null and effective_until is null;

create table if not exists namespaces (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  key text not null,
  name text not null,
  visibility text not null references namespace_visibilities(key),
  created_at timestamptz not null default now(),
  archived_at timestamptz null,
  primary key (tenant_id, id),
  unique (tenant_id, key)
);

create table if not exists namespace_grants (
  tenant_id uuid not null,
  id uuid not null,
  namespace_id uuid not null,
  principal_id uuid not null references principals(id) on delete restrict,
  grant_scope text not null check (grant_scope in ('read', 'search', 'submit', 'review', 'admin')),
  status text not null check (status in ('active', 'revoked', 'expired')),
  created_at timestamptz not null default now(),
  valid_from timestamptz not null,
  expires_at timestamptz null,
  revoked_at timestamptz null,
  effective_until timestamptz null,
  grant_version bigint not null default 1,
  primary key (tenant_id, id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict
);
create unique index if not exists namespace_grants_open_uidx
  on namespace_grants(tenant_id, namespace_id, principal_id, grant_scope)
  where status = 'active' and revoked_at is null and effective_until is null;

create table if not exists worker_identities (
  id uuid primary key,
  principal_id uuid not null references principals(id) on delete restrict,
  worker_role text not null references actor_roles(key),
  purpose text not null,
  allowed_operations text[] not null check (array_length(allowed_operations, 1) is not null),
  created_at timestamptz not null default now(),
  disabled_at timestamptz null
);

create table if not exists tenant_revocation_epochs (
  tenant_id uuid primary key references tenants(id) on delete restrict,
  last_epoch bigint not null default 0 check (last_epoch >= 0),
  updated_at timestamptz not null default now()
);

create table if not exists break_glass_cases (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  status text not null check (status in ('open', 'active', 'expired', 'closed', 'rejected')),
  target_type text not null check (target_type in ('tenant', 'namespace', 'card', 'card_version')),
  target_id uuid not null,
  permitted_operations text[] not null check (array_length(permitted_operations, 1) is not null),
  reason_code text not null,
  approved_by_1 uuid not null references principals(id) on delete restrict,
  approved_by_2 uuid not null references principals(id) on delete restrict,
  requested_by uuid not null references principals(id) on delete restrict,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  closed_at timestamptz null,
  post_access_reviewed_at timestamptz null,
  primary key (tenant_id, id),
  check (approved_by_1 <> approved_by_2),
  check (expires_at > created_at)
);

create table if not exists verification_records (
  tenant_id uuid not null,
  id uuid not null,
  card_id uuid not null,
  card_version_id uuid not null,
  verification_status text not null references verification_statuses(key),
  reviewer_id uuid not null references principals(id) on delete restrict,
  activity_id uuid not null,
  environment_digest text not null,
  input_digest text not null,
  output_digest text not null,
  version_bounds jsonb not null,
  risk_class text not null,
  external_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz null,
  superseded_at timestamptz null,
  primary key (tenant_id, id),
  unique (tenant_id, card_id, card_version_id, id)
);
create unique index if not exists verification_records_open_active_uidx
  on verification_records(tenant_id, card_id, card_version_id)
  where verification_status = 'active' and revoked_at is null and superseded_at is null;

create table if not exists experience_cards (
  tenant_id uuid not null,
  id uuid not null,
  namespace_id uuid not null,
  current_version_id uuid not null,
  active_verification_record_id uuid null,
  status text not null references card_statuses(key),
  outcome_type text not null references outcome_types(key),
  quality_state text not null references quality_states(key),
  evidence_strength text not null references evidence_strengths(key),
  created_by uuid not null references principals(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, id),
  unique (tenant_id, id, current_version_id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict,
  foreign key (tenant_id, active_verification_record_id) references verification_records(tenant_id, id) on delete restrict,
  check ((quality_state <> 'verified' and active_verification_record_id is null) or (quality_state = 'verified' and active_verification_record_id is not null))
);

create or replace function knudg_private.jsonb_string_array_is_nonempty_strings(row_value jsonb, require_nonempty boolean default false)
returns boolean
language sql
immutable
set search_path = pg_catalog, pg_temp
as $$
  select jsonb_typeof(row_value) = 'array'
    and (not require_nonempty or jsonb_array_length(row_value) > 0)
    and not exists (
      select 1
      from jsonb_array_elements(row_value) as item(value)
      where jsonb_typeof(item.value) <> 'string' or item.value #>> '{}' = ''
    );
$$;

create or replace function knudg_private.jsonb_has_non_ascii_keys(row_json jsonb)
returns boolean
language plpgsql
immutable
set search_path = pg_catalog, pg_temp
as $$
declare
  row_type text;
  child jsonb;
  child_key text;
begin
  row_type := jsonb_typeof(row_json);
  if row_type = 'object' then
    for child_key, child in select key, value from jsonb_each(row_json) loop
      if child_key !~ '^[\u0000-\u007f]+$' then
        return true;
      end if;
      if knudg_private.jsonb_has_non_ascii_keys(child) then
        return true;
      end if;
    end loop;
  elsif row_type = 'array' then
    for child in select value from jsonb_array_elements(row_json) loop
      if knudg_private.jsonb_has_non_ascii_keys(child) then
        return true;
      end if;
    end loop;
  end if;
  return false;
end;
$$;

create or replace function knudg_private.jsonb_has_non_portable_numbers(row_json jsonb)
returns boolean
language plpgsql
immutable
set search_path = pg_catalog, pg_temp
as $$
declare
  row_type text;
  raw_number text;
  child jsonb;
begin
  row_type := jsonb_typeof(row_json);
  if row_type = 'number' then
    raw_number := row_json::text;
    if raw_number ~ '[\.eE]' then
      return true;
    end if;
    return raw_number::numeric < -9007199254740991 or raw_number::numeric > 9007199254740991;
  elsif row_type = 'object' then
    for child in select value from jsonb_each(row_json) loop
      if knudg_private.jsonb_has_non_portable_numbers(child) then
        return true;
      end if;
    end loop;
  elsif row_type = 'array' then
    for child in select value from jsonb_array_elements(row_json) loop
      if knudg_private.jsonb_has_non_portable_numbers(child) then
        return true;
      end if;
    end loop;
  end if;
  return false;
end;
$$;

create or replace function knudg_private.card_payload_v1_is_valid(row_payload jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select jsonb_typeof(row_payload) = 'object'
    and not knudg_private.jsonb_has_non_ascii_keys(row_payload)
    and not knudg_private.jsonb_has_non_portable_numbers(row_payload)
    and not (row_payload ?| array['card_id','tenant_id','namespace_id','visibility','visibility_view','status','current_version_id','created_at','updated_at','quality_score','card_schema_version'])
    and not exists (
      select 1
      from jsonb_object_keys(row_payload) as key
      where key not in (
        'outcome_type','goal','symptom','environment','context_fingerprint',
        'successful_path','failed_paths','known_unknowns','scope_limits',
        'evidence_strength','twist','quality_state','safety','privacy','provenance',
        'deprecation','supersession','contradictions','embedding_refs'
      )
    )
    and row_payload ? 'outcome_type'
    and row_payload ? 'goal'
    and row_payload ? 'symptom'
    and row_payload ? 'environment'
    and row_payload ? 'context_fingerprint'
    and row_payload ? 'failed_paths'
    and row_payload ? 'known_unknowns'
    and row_payload ? 'scope_limits'
    and row_payload ? 'evidence_strength'
    and row_payload ? 'quality_state'
    and row_payload ? 'safety'
    and row_payload ? 'privacy'
    and row_payload ? 'provenance'
    and row_payload->>'outcome_type' in ('solved','failed_only','inconclusive','unknown_clarified')
    and row_payload->>'evidence_strength' in ('single_session','multi_session','reproduced','external_reference','operator_judgment')
    and row_payload->>'quality_state' in ('unreviewed','solved_once','solved_many','verified','disputed')
    and jsonb_typeof(row_payload->'goal') = 'string'
    and jsonb_typeof(row_payload->'symptom') = 'string'
    and nullif(row_payload->>'goal', '') is not null
    and nullif(row_payload->>'symptom', '') is not null
    and jsonb_typeof(row_payload->'environment') = 'object'
    and jsonb_typeof(row_payload->'context_fingerprint') = 'object'
    and (not (row_payload ? 'successful_path') or row_payload->'successful_path' = 'null'::jsonb or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'successful_path', row_payload->>'outcome_type' = 'solved'))
    and (row_payload->>'outcome_type' <> 'solved' or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'successful_path', true))
    and (row_payload->>'outcome_type' <> 'failed_only' or (
      (not (row_payload ? 'successful_path') or row_payload->'successful_path' = 'null'::jsonb or (jsonb_typeof(row_payload->'successful_path') = 'array' and jsonb_array_length(row_payload->'successful_path') = 0))
      and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'failed_paths', true)
    ))
    and (row_payload->>'outcome_type' <> 'unknown_clarified' or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'known_unknowns', true))
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'failed_paths')
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'known_unknowns')
    and knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'scope_limits')
    and jsonb_typeof(row_payload->'safety') = 'object'
    and not exists (
      select 1
      from jsonb_object_keys(row_payload->'safety') as key
      where key not in (
        'safety_class','review_state','executable_advice','mentions_urls',
        'mentions_packages','mentions_repositories','credential_risk','billing_risk',
        'deletion_risk','network_call_risk','verification_state','withheld_reason'
      )
    )
    and row_payload->'safety' ?& array[
      'safety_class','review_state','executable_advice','mentions_urls',
      'mentions_packages','mentions_repositories','credential_risk','billing_risk',
      'deletion_risk','network_call_risk','verification_state','withheld_reason'
    ]
    and row_payload->'safety'->>'safety_class' in ('low','medium','high')
    and row_payload->'safety'->>'review_state' in ('unreviewed','quarantined','cleared','blocked')
    and jsonb_typeof(row_payload->'safety'->'executable_advice') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_urls') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_packages') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'mentions_repositories') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'credential_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'billing_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'deletion_risk') = 'boolean'
    and jsonb_typeof(row_payload->'safety'->'network_call_risk') = 'boolean'
    and row_payload->'safety'->>'verification_state' in ('unverified','single_session','reproduced','external_reference')
    and (row_payload->'safety'->'withheld_reason' = 'null'::jsonb or jsonb_typeof(row_payload->'safety'->'withheld_reason') = 'string')
    and jsonb_typeof(row_payload->'privacy') = 'object'
    and jsonb_typeof(row_payload->'provenance') = 'object'
    and row_payload->'privacy'->>'source_class' = 'synthetic'
    and row_payload->'provenance'->>'source_class' = 'synthetic'
    and (not (row_payload ? 'twist') or row_payload->'twist' = 'null'::jsonb or jsonb_typeof(row_payload->'twist') = 'string')
    and (not (row_payload ? 'deprecation') or jsonb_typeof(row_payload->'deprecation') = 'object')
    and (not (row_payload ? 'supersession') or jsonb_typeof(row_payload->'supersession') = 'object')
    and (not (row_payload ? 'contradictions') or knudg_private.jsonb_string_array_is_nonempty_strings(row_payload->'contradictions'))
    and (
      not (row_payload ? 'embedding_refs')
      or (
        jsonb_typeof(row_payload->'embedding_refs') = 'array'
        and not exists (
          select 1
          from jsonb_array_elements(row_payload->'embedding_refs') as item(value)
          where jsonb_typeof(item.value) <> 'object'
        )
      )
    );
$$;

create or replace function knudg_private.canonical_jsonb(row_json jsonb)
returns text
language plpgsql
immutable
set search_path = pg_catalog, pg_temp
as $$
declare
  row_type text;
  result text;
begin
  row_type := jsonb_typeof(row_json);
  if row_type = 'object' then
    select '{' || coalesce(string_agg(to_json(key)::text || ':' || knudg_private.canonical_jsonb(value), ',' order by key collate "C"), '') || '}'
    into result
    from jsonb_each(row_json);
    return result;
  elsif row_type = 'array' then
    select '[' || coalesce(string_agg(knudg_private.canonical_jsonb(value), ',' order by ordinality), '') || ']'
    into result
    from jsonb_array_elements(row_json) with ordinality;
    return result;
  else
    return row_json::text;
  end if;
end;
$$;

create table if not exists card_versions (
  tenant_id uuid not null,
  id uuid not null,
  card_id uuid not null,
  version_number integer not null check (version_number > 0),
  card_schema_version integer not null check (card_schema_version = 1),
  payload_json jsonb not null,
  payload_digest_alg text not null default 'sha256:jcs-rfc8785:v1',
  payload_digest text not null,
  created_by uuid not null references principals(id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id),
  unique (tenant_id, card_id, version_number),
  unique (tenant_id, card_id, id),
  foreign key (tenant_id, card_id) references experience_cards(tenant_id, id) on delete restrict deferrable initially deferred,
  check (jsonb_typeof(payload_json) = 'object'),
  check (payload_digest_alg = 'sha256:jcs-rfc8785:v1'),
  check (payload_digest ~ '^[0-9a-f]{64}$'),
  check (payload_digest = encode(knudg_crypto.digest(knudg_private.canonical_jsonb(payload_json), 'sha256'), 'hex')),
  check (knudg_private.card_payload_v1_is_valid(payload_json))
);

alter table experience_cards
  add constraint experience_cards_current_version_fk
  foreign key (tenant_id, id, current_version_id)
  references card_versions(tenant_id, card_id, id)
  on delete restrict
  deferrable initially deferred;

alter table verification_records
  add constraint verification_records_card_version_fk
  foreign key (tenant_id, card_id, card_version_id)
  references card_versions(tenant_id, card_id, id)
  on delete restrict
  deferrable initially deferred;

create table if not exists domain_events (
  tenant_id uuid not null references tenants(id) on delete restrict,
  event_id uuid not null,
  event_type text not null references domain_event_types(key),
  actor_id uuid not null references principals(id) on delete restrict,
  actor_role text not null references actor_roles(key),
  target_type text not null,
  target_id uuid not null,
  event_payload_schema_version integer not null,
  event_payload_json jsonb not null,
  event_payload_digest text not null,
  causation_event_id uuid null,
  correlation_id uuid not null,
  idempotency_key text not null,
  event_stream_position bigint not null default nextval('event_stream_position_seq'),
  created_at timestamptz not null default now(),
  primary key (tenant_id, event_id),
  unique (event_stream_position),
  unique (tenant_id, event_id, event_stream_position),
  check (jsonb_typeof(event_payload_json) = 'object'),
  check (event_payload_digest <> '')
);

create table if not exists card_events (
  tenant_id uuid not null,
  card_id uuid not null,
  event_id uuid not null,
  event_stream_position bigint not null default nextval('event_stream_position_seq'),
  event_seq bigint not null check (event_seq > 0),
  event_type text not null references card_event_types(key),
  actor_id uuid not null references principals(id) on delete restrict,
  actor_role text not null references actor_roles(key),
  previous_status text null references card_statuses(key),
  next_status text not null references card_statuses(key),
  expected_current_version uuid null,
  causation_event_id uuid null,
  correlation_id uuid not null,
  idempotency_key text not null,
  event_payload_schema_version integer not null,
  event_payload_json jsonb not null,
  event_payload_digest text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, event_id),
  unique (event_id),
  unique (tenant_id, card_id, event_seq),
  unique (event_stream_position),
  unique (tenant_id, event_id, event_stream_position),
  foreign key (tenant_id, card_id) references experience_cards(tenant_id, id) on delete restrict,
  check ((event_type = 'card_created' and previous_status is null and next_status = 'candidate_created' and event_seq = 1)
    or (event_type <> 'card_created' and previous_status is not null)),
  check (jsonb_typeof(event_payload_json) = 'object'),
  check (event_payload_digest <> '')
);

alter table event_stream_positions
  add constraint event_stream_positions_card_event_fk
  foreign key (tenant_id, card_event_id)
  references card_events(tenant_id, event_id)
  on delete restrict
  deferrable initially deferred;
alter table event_stream_positions
  add constraint event_stream_positions_domain_event_fk
  foreign key (tenant_id, domain_event_id)
  references domain_events(tenant_id, event_id)
  on delete restrict
  deferrable initially deferred;

create table if not exists card_edges (
  tenant_id uuid not null,
  id uuid not null,
  source_card_id uuid not null,
  target_card_id uuid not null,
  source_card_version_id uuid not null,
  target_card_version_id uuid not null,
  edge_type text not null references card_edge_types(key),
  created_by uuid not null references principals(id) on delete restrict,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id),
  unique (tenant_id, source_card_version_id, edge_type, target_card_version_id),
  foreign key (tenant_id, source_card_id) references experience_cards(tenant_id, id) on delete restrict,
  foreign key (tenant_id, target_card_id) references experience_cards(tenant_id, id) on delete restrict,
  foreign key (tenant_id, source_card_id, source_card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  foreign key (tenant_id, target_card_id, target_card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  check (source_card_version_id <> target_card_version_id)
);

create table if not exists card_state_transitions (
  from_status text not null references card_statuses(key),
  to_status text not null references card_statuses(key),
  event_type text not null references card_event_types(key),
  actor_role text not null references actor_roles(key),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (from_status, to_status, event_type, actor_role)
);

create table if not exists revocation_tombstones (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  subject_type text not null references revocation_subject_types(key),
  subject_id uuid not null,
  tenant_subject_id uuid null,
  namespace_id uuid null,
  card_id uuid null,
  card_version_id uuid null,
  source_artifact_id uuid null,
  derived_artifact_id uuid null,
  search_index_manifest_id uuid null,
  revocation_epoch bigint not null check (revocation_epoch > 0),
  revocation_event_source_type text not null check (revocation_event_source_type in ('card', 'domain')),
  card_revocation_event_id uuid null,
  domain_revocation_event_id uuid null,
  revoked_by uuid not null references principals(id) on delete restrict,
  reason text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_id) references experience_cards(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_version_id) references card_versions(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_id, card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  foreign key (tenant_id, card_revocation_event_id) references card_events(tenant_id, event_id) on delete restrict,
  foreign key (tenant_id, domain_revocation_event_id) references domain_events(tenant_id, event_id) on delete restrict,
  unique (tenant_id, subject_type, subject_id, revocation_epoch),
  unique (tenant_id, card_id, card_version_id, revocation_epoch),
  check (
    (subject_type = 'tenant' and subject_id = tenant_subject_id and tenant_subject_id = tenant_id and namespace_id is null and card_id is null and card_version_id is null)
    or (subject_type = 'namespace' and subject_id = namespace_id and namespace_id is not null and card_id is null and card_version_id is null)
    or (subject_type = 'card' and subject_id = card_id and card_id is not null and card_version_id is not null)
    or (subject_type = 'card_version' and subject_id = card_version_id and card_id is not null and card_version_id is not null)
    or (subject_type = 'source_artifact' and subject_id = source_artifact_id and source_artifact_id is not null)
    or (subject_type = 'derived_artifact' and subject_id = derived_artifact_id and derived_artifact_id is not null)
    or (subject_type = 'search_index_manifest' and subject_id = search_index_manifest_id and search_index_manifest_id is not null)
  ),
  check (
    (revocation_event_source_type = 'card' and card_revocation_event_id is not null and domain_revocation_event_id is null and subject_type in ('card','card_version'))
    or (revocation_event_source_type = 'domain' and domain_revocation_event_id is not null and card_revocation_event_id is null and subject_type in ('tenant','namespace','source_artifact','derived_artifact','search_index_manifest'))
  )
);

create table if not exists consent_records (
  tenant_id uuid not null,
  id uuid not null,
  subject_id uuid not null references principals(id) on delete restrict,
  scope text not null references consent_scopes(key),
  namespace_id uuid null,
  artifact_type text not null references artifact_types(key),
  artifact_id uuid not null,
  card_version_id uuid null,
  artifact_digest text not null,
  policy_version text not null,
  policy_digest text not null,
  challenge_id uuid null,
  challenge_digest text null,
  granted_at timestamptz not null default now(),
  expires_at timestamptz null,
  revoked_at timestamptz null,
  termination_reason text null,
  terminated_by uuid null references principals(id) on delete restrict,
  grant_card_event_id uuid null,
  grant_domain_event_id uuid null,
  termination_card_event_id uuid null,
  termination_domain_event_id uuid null,
  retention_policy text not null,
  retention_purpose text not null,
  primary key (tenant_id, id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_version_id) references card_versions(tenant_id, id) on delete restrict,
  foreign key (tenant_id, challenge_id) references approval_challenges(tenant_id, id) on delete restrict,
  foreign key (tenant_id, grant_card_event_id) references card_events(tenant_id, event_id) on delete restrict,
  foreign key (tenant_id, grant_domain_event_id) references domain_events(tenant_id, event_id) on delete restrict,
  foreign key (tenant_id, termination_card_event_id) references card_events(tenant_id, event_id) on delete restrict,
  foreign key (tenant_id, termination_domain_event_id) references domain_events(tenant_id, event_id) on delete restrict,
  check (artifact_type <> 'card_version' or artifact_id = card_version_id),
  check (scope <> 'public_publication' or (artifact_type = 'card_version' and expires_at is null)),
  check ((grant_card_event_id is not null and grant_domain_event_id is null) or (grant_card_event_id is null and grant_domain_event_id is not null)),
  check (
    (revoked_at is null and termination_card_event_id is null and termination_domain_event_id is null)
    or (revoked_at is not null and ((termination_card_event_id is not null and termination_domain_event_id is null) or (termination_card_event_id is null and termination_domain_event_id is not null)))
  )
);
alter table approval_challenges
  add constraint approval_challenges_used_by_consent_fk
  foreign key (tenant_id, used_by_consent_id) references consent_records(tenant_id, id) on delete restrict
  deferrable initially deferred;
alter table approval_challenges
  add constraint approval_challenges_consent_scope_fk
  foreign key (consent_scope) references consent_scopes(key) on delete restrict;
create unique index if not exists approval_challenges_used_once_uidx
  on approval_challenges(tenant_id, used_by_consent_id)
  where used_by_consent_id is not null;
create unique index if not exists consent_records_one_active_public_approval_uidx
  on consent_records(tenant_id, card_version_id, scope)
  where revoked_at is null and scope = 'public_publication' and artifact_type = 'card_version';
create index if not exists consent_records_exact_active_approval_idx
  on consent_records(tenant_id, artifact_type, artifact_id, artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest)
  where revoked_at is null;

create table if not exists approval_handoffs (
  tenant_id uuid not null,
  id uuid not null,
  challenge_id uuid not null,
  subject_id uuid not null references principals(id) on delete restrict,
  namespace_id uuid not null,
  consent_scope text not null references consent_scopes(key),
  artifact_type text not null references artifact_types(key),
  artifact_id uuid not null,
  card_version_id uuid not null,
  artifact_digest text not null,
  policy_version text not null,
  policy_digest text not null,
  challenge_digest text not null,
  handoff_digest text not null,
  origin text not null,
  expires_at timestamptz not null,
  created_by uuid not null references principals(id) on delete restrict,
  created_at timestamptz not null default now(),
  invalidated_at timestamptz null,
  primary key (tenant_id, id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict,
  foreign key (tenant_id, challenge_id) references approval_challenges(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_version_id) references card_versions(tenant_id, id) on delete restrict,
  check (artifact_type = 'card_version'),
  check (artifact_id = card_version_id),
  check (consent_scope = 'private_retention'),
  check (artifact_digest <> ''),
  check (policy_version <> ''),
  check (policy_digest <> ''),
  check (challenge_digest <> ''),
  check (handoff_digest <> ''),
  check (origin <> ''),
  unique (tenant_id, challenge_id)
);
create index if not exists approval_handoffs_active_idx
  on approval_handoffs(tenant_id, namespace_id, expires_at)
  where invalidated_at is null;

create table if not exists idempotency_keys (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  operation text not null,
  logical_object_type text not null,
  logical_object_id uuid not null,
  operation_version integer not null,
  idempotency_key text not null,
  request_digest text not null,
  response_digest text not null,
  effect_event_source_type text not null check (effect_event_source_type in ('card', 'domain')),
  effect_card_event_id uuid null,
  effect_domain_event_id uuid null,
  created_at timestamptz not null default now(),
  expires_at timestamptz null,
  primary key (tenant_id, id),
  unique (tenant_id, operation, logical_object_type, logical_object_id, operation_version, idempotency_key),
  foreign key (tenant_id, effect_card_event_id) references card_events(tenant_id, event_id) on delete restrict,
  foreign key (tenant_id, effect_domain_event_id) references domain_events(tenant_id, event_id) on delete restrict,
  check (
    (effect_event_source_type = 'card' and effect_card_event_id is not null and effect_domain_event_id is null)
    or (effect_event_source_type = 'domain' and effect_domain_event_id is not null and effect_card_event_id is null)
  )
);

create or replace function knudg_private.audit_detail_is_sanitized(row_detail text)
returns boolean
language sql
immutable
set search_path = pg_catalog, pg_temp
as $$
  select row_detail is not null
    and length(row_detail) <= 2048
    and row_detail !~ '[\r\n]'
    and row_detail !~* '(secret|password|credential|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|auth[_ -]?token|(^|[^[:alpha:]])token[[:space:]]*[=:]|authorization[[:space:]]*[=:][[:space:]]*(bearer|token)|bearer[[:space:]]+[A-Za-z0-9._~+/-]+|github_pat_|ghp_[A-Za-z0-9_]+|-----BEGIN)'
    and row_detail !~ '([A-Za-z]:\\|\\\\|/(Users|home|etc|var|tmp|mnt|working)(/|$))'
    and row_detail !~ '(```|<[^>]+>|[{][^}]{24,}[}])';
$$;

create table if not exists outbox_events (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  event_stream_position bigint not null,
  lane text not null,
  status text not null default 'pending' check (status in ('pending','job_enqueued','completed','dead')),
  payload_json jsonb not null,
  payload_digest text not null,
  idempotency_key text not null,
  job_id uuid null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, id),
  foreign key (tenant_id, event_stream_position) references event_stream_positions(tenant_id, event_stream_position) on delete restrict,
  check (lane in ('revocation','approval_publish','consent','tombstone','event_projection','redaction','review','index','compaction','embedding','rerank','public_candidate_ingest','dedupe','analytics')),
  check (jsonb_typeof(payload_json) = 'object'),
  check (payload_digest <> ''),
  unique (tenant_id, event_stream_position, lane),
  unique (tenant_id, lane, idempotency_key)
);

create table if not exists jobs (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  lane text not null,
  status text not null default 'ready' check (status in ('ready','leased','succeeded','dead','cancelled')),
  priority integer not null default 0,
  payload_json jsonb not null,
  payload_digest text not null,
  idempotency_key text not null,
  outbox_event_id uuid null,
  attempts integer not null default 0 check (attempts >= 0),
  max_attempts integer not null default 3 check (max_attempts > 0),
  available_at timestamptz not null default now(),
  leased_by uuid null references principals(id) on delete restrict,
  lease_expires_at timestamptz null,
  last_error_class text null,
  last_error_detail text null check (last_error_detail is null or knudg_private.audit_detail_is_sanitized(last_error_detail)),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz null,
  primary key (tenant_id, id),
  foreign key (tenant_id, outbox_event_id) references outbox_events(tenant_id, id) on delete restrict,
  check (lane in ('revocation','approval_publish','consent','tombstone','event_projection','redaction','review','index','compaction','embedding','rerank','public_candidate_ingest','dedupe','analytics')),
  check (jsonb_typeof(payload_json) = 'object'),
  check (payload_digest <> ''),
  unique (tenant_id, lane, idempotency_key),
  check (
    (status = 'leased' and leased_by is not null and lease_expires_at is not null)
    or (status <> 'leased' and lease_expires_at is null)
  )
);

alter table outbox_events
  add constraint outbox_events_job_fk
  foreign key (tenant_id, job_id) references jobs(tenant_id, id)
  on delete restrict
  deferrable initially deferred;

create table if not exists job_attempts (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  job_id uuid not null,
  attempt_number integer not null check (attempt_number > 0),
  worker_id uuid not null references principals(id) on delete restrict,
  worker_role text not null references actor_roles(key),
  status text not null check (status in ('leased','succeeded','retry_scheduled','dead')),
  error_class text null,
  sanitized_error_detail text null check (sanitized_error_detail is null or knudg_private.audit_detail_is_sanitized(sanitized_error_detail)),
  started_at timestamptz not null default now(),
  finished_at timestamptz null,
  primary key (tenant_id, id),
  foreign key (tenant_id, job_id) references jobs(tenant_id, id) on delete restrict,
  unique (tenant_id, job_id, attempt_number)
);

create index if not exists jobs_ready_lane_idx on jobs(tenant_id, lane, priority desc, available_at, created_at)
  where status = 'ready';
create index if not exists jobs_dead_lane_idx on jobs(tenant_id, lane, created_at)
  where status = 'dead';
create index if not exists outbox_events_status_lane_idx on outbox_events(tenant_id, status, lane, event_stream_position);

create table if not exists audit_events (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  actor_id uuid not null references principals(id) on delete restrict,
  actor_role text not null references actor_roles(key),
  action text not null,
  target_type text not null,
  target_id uuid not null,
  reason_code text not null,
  sanitized_detail text not null check (knudg_private.audit_detail_is_sanitized(sanitized_detail)),
  correlation_id uuid not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, id)
);

create index if not exists event_stream_positions_tenant_source_idx on event_stream_positions(tenant_id, event_source_type, event_stream_position);
create index if not exists card_events_card_seq_desc_idx on card_events(tenant_id, card_id, event_seq desc);
create index if not exists audit_events_target_idx on audit_events(tenant_id, target_type, target_id);
create index if not exists audit_events_correlation_idx on audit_events(tenant_id, correlation_id);
create index if not exists idempotency_keys_replay_idx on idempotency_keys(tenant_id, operation, logical_object_type, logical_object_id, operation_version, idempotency_key);

create or replace function knudg_private.reject_update_delete()
returns trigger
language plpgsql
as $$
begin
  raise exception '% is append-only', tg_table_name using errcode = '55000';
end;
$$;

drop trigger if exists card_versions_append_only on card_versions;
create trigger card_versions_append_only before update or delete on card_versions
for each row execute function knudg_private.reject_update_delete();
drop trigger if exists card_events_append_only on card_events;
create trigger card_events_append_only before update or delete on card_events
for each row execute function knudg_private.reject_update_delete();
drop trigger if exists domain_events_append_only on domain_events;
create trigger domain_events_append_only before update or delete on domain_events
for each row execute function knudg_private.reject_update_delete();
drop trigger if exists audit_events_append_only on audit_events;
create trigger audit_events_append_only before update or delete on audit_events
for each row execute function knudg_private.reject_update_delete();
drop trigger if exists revocation_tombstones_append_only on revocation_tombstones;
create trigger revocation_tombstones_append_only before update or delete on revocation_tombstones
for each row execute function knudg_private.reject_update_delete();

create or replace function knudg_private.enforce_revocation_tombstone_event_consistency()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  if new.revocation_event_source_type = 'card' then
    if not exists (
      select 1
      from public.card_events ce
      where ce.tenant_id = new.tenant_id
        and ce.event_id = new.card_revocation_event_id
        and ce.event_type = 'revoked'
        and ce.card_id = new.card_id
        and ce.actor_id = new.revoked_by
        and ce.expected_current_version = new.card_version_id
    ) then
      raise exception 'card revocation tombstone must reference matching revoked card event and actor' using errcode = '23514';
    end if;
  elsif new.revocation_event_source_type = 'domain' then
    if not exists (
      select 1
      from public.domain_events de
      where de.tenant_id = new.tenant_id
        and de.event_id = new.domain_revocation_event_id
        and de.actor_id = new.revoked_by
        and (
          (new.subject_type = 'tenant' and de.event_type = 'tenant_revoked' and de.target_type = 'tenant' and de.target_id = new.tenant_subject_id)
          or (new.subject_type = 'namespace' and de.event_type = 'namespace_revoked' and de.target_type = 'namespace' and de.target_id = new.namespace_id)
          or (new.subject_type = 'source_artifact' and de.event_type = 'source_artifact_revoked' and de.target_type = 'source_artifact' and de.target_id = new.source_artifact_id)
          or (new.subject_type = 'derived_artifact' and de.event_type = 'derived_artifact_revoked' and de.target_type = 'derived_artifact' and de.target_id = new.derived_artifact_id)
          or (new.subject_type = 'search_index_manifest' and de.event_type = 'search_index_manifest_revoked' and de.target_type = 'search_index_manifest' and de.target_id = new.search_index_manifest_id)
        )
    ) then
      raise exception 'domain revocation tombstone must reference matching domain revocation event and actor' using errcode = '23514';
    end if;
  end if;
  return new;
end;
$$;
drop trigger if exists revocation_tombstones_event_consistency on revocation_tombstones;
create constraint trigger revocation_tombstones_event_consistency
after insert on revocation_tombstones deferrable initially deferred
for each row execute function knudg_private.enforce_revocation_tombstone_event_consistency();

create or replace function knudg_private.enforce_card_transition()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  if new.event_type = 'card_created' then
    return new;
  end if;
  if not exists (
    select 1
    from public.card_state_transitions t
    where t.from_status = new.previous_status
      and t.to_status = new.next_status
      and t.event_type = new.event_type
      and t.actor_role = new.actor_role
      and t.is_active
  ) then
    raise exception 'invalid card transition % -> % via % role %',
      new.previous_status, new.next_status, new.event_type, new.actor_role
      using errcode = '23514';
  end if;
  return new;
end;
$$;
drop trigger if exists card_events_transition_guard on card_events;
create trigger card_events_transition_guard before insert on card_events
for each row execute function knudg_private.enforce_card_transition();

create or replace function knudg_private.enforce_event_position_bijection()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  missing_count integer;
begin
  select count(*) into missing_count
  from public.card_events e
  where not exists (
    select 1 from public.event_stream_positions p
    where p.event_source_type = 'card'
      and p.tenant_id = e.tenant_id
      and p.card_event_id = e.event_id
      and p.event_stream_position = e.event_stream_position
  );
  if missing_count <> 0 then
    raise exception 'card event missing matching event_stream_positions row' using errcode = '23514';
  end if;

  select count(*) into missing_count
  from public.domain_events e
  where not exists (
    select 1 from public.event_stream_positions p
    where p.event_source_type = 'domain'
      and p.tenant_id = e.tenant_id
      and p.domain_event_id = e.event_id
      and p.event_stream_position = e.event_stream_position
  );
  if missing_count <> 0 then
    raise exception 'domain event missing matching event_stream_positions row' using errcode = '23514';
  end if;

  select count(*) into missing_count
  from public.event_stream_positions p
  where (p.event_source_type = 'card' and not exists (
      select 1 from public.card_events e
      where e.tenant_id = p.tenant_id and e.event_id = p.card_event_id and e.event_stream_position = p.event_stream_position
    ))
    or (p.event_source_type = 'domain' and not exists (
      select 1 from public.domain_events e
      where e.tenant_id = p.tenant_id and e.event_id = p.domain_event_id and e.event_stream_position = p.event_stream_position
    ));
  if missing_count <> 0 then
    raise exception 'event_stream_positions row missing matching event row' using errcode = '23514';
  end if;
  return null;
end;
$$;
drop trigger if exists card_events_position_bijection on card_events;
create constraint trigger card_events_position_bijection
after insert or update on card_events deferrable initially deferred
for each row execute function knudg_private.enforce_event_position_bijection();
drop trigger if exists domain_events_position_bijection on domain_events;
create constraint trigger domain_events_position_bijection
after insert or update on domain_events deferrable initially deferred
for each row execute function knudg_private.enforce_event_position_bijection();
drop trigger if exists event_stream_positions_position_bijection on event_stream_positions;
create constraint trigger event_stream_positions_position_bijection
after insert or update on event_stream_positions deferrable initially deferred
for each row execute function knudg_private.enforce_event_position_bijection();

create or replace function knudg_private.enforce_consent_challenge_binding()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  challenge public.approval_challenges%rowtype;
begin
  if new.challenge_id is null then
    return new;
  end if;
  select * into challenge
  from public.approval_challenges
  where tenant_id = new.tenant_id and id = new.challenge_id
  for update;
  if not found then
    raise exception 'missing approval challenge' using errcode = '23503';
  end if;
  if challenge.used_by_consent_id is not null and challenge.used_by_consent_id <> new.id then
    raise exception 'approval challenge already used' using errcode = '23505';
  end if;
  if challenge.invalidated_at is not null or challenge.expires_at <= now() then
    raise exception 'approval challenge inactive' using errcode = '23514';
  end if;
  if challenge.subject_id <> new.subject_id
    or challenge.namespace_id is distinct from new.namespace_id
    or challenge.consent_scope <> new.scope
    or challenge.artifact_type <> new.artifact_type
    or challenge.artifact_id <> new.artifact_id
    or challenge.card_version_id is distinct from new.card_version_id
    or challenge.artifact_digest <> new.artifact_digest
    or challenge.policy_version <> new.policy_version
    or challenge.policy_digest <> new.policy_digest
    or challenge.challenge_digest <> new.challenge_digest then
    raise exception 'consent does not match approval challenge' using errcode = '23514';
  end if;
  update public.approval_challenges
  set used_at = coalesce(used_at, now()), used_by_consent_id = new.id
  where tenant_id = new.tenant_id and id = new.challenge_id;
  return new;
end;
$$;
drop trigger if exists consent_records_challenge_binding on consent_records;
create trigger consent_records_challenge_binding before insert on consent_records
for each row execute function knudg_private.enforce_consent_challenge_binding();

create or replace function knudg_private.enforce_verified_card_record()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  if new.quality_state <> 'verified' then
    return new;
  end if;
  if not exists (
    select 1 from public.verification_records vr
    where vr.tenant_id = new.tenant_id
      and vr.id = new.active_verification_record_id
      and vr.card_id = new.id
      and vr.card_version_id = new.current_version_id
      and vr.verification_status = 'active'
      and vr.revoked_at is null
      and vr.superseded_at is null
      and vr.expires_at > now()
  ) then
    raise exception 'verified card requires active verification for current version' using errcode = '23514';
  end if;
  return new;
end;
$$;
drop trigger if exists experience_cards_verified_record_guard on experience_cards;
create constraint trigger experience_cards_verified_record_guard
after insert or update on experience_cards deferrable initially deferred
for each row execute function knudg_private.enforce_verified_card_record();

create or replace function knudg_private.enforce_idempotency_digest()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  if exists (
    select 1 from public.idempotency_keys existing
    where existing.tenant_id = new.tenant_id
      and existing.operation = new.operation
      and existing.logical_object_type = new.logical_object_type
      and existing.logical_object_id = new.logical_object_id
      and existing.operation_version = new.operation_version
      and existing.idempotency_key = new.idempotency_key
      and existing.request_digest <> new.request_digest
  ) then
    raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
  end if;
  return new;
end;
$$;
drop trigger if exists idempotency_keys_digest_guard on idempotency_keys;
create trigger idempotency_keys_digest_guard before insert on idempotency_keys
for each row execute function knudg_private.enforce_idempotency_digest();

create or replace function knudg_private.current_claims_json()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  rid uuid;
  ctx public.request_claim_contexts%rowtype;
begin
  rid := nullif(current_setting('knudg.trusted_request_id', true), '')::uuid;
  if rid is null then
    raise exception 'missing trusted request claims' using errcode = '28000';
  end if;
  select * into ctx
  from public.request_claim_contexts
  where backend_pid = pg_backend_pid()
    and transaction_id = pg_current_xact_id()
    and request_id = rid;
  if not found or ctx.expires_at <= now() then
    raise exception 'expired or missing trusted request claims' using errcode = '28000';
  end if;
  if not exists (
    select 1
    from public.principals p
    join public.tenant_memberships tm on tm.principal_id = p.id and tm.tenant_id = ctx.tenant_id
    where p.id = ctx.principal_id
      and p.disabled_at is null
      and tm.status = 'active'
      and tm.revoked_at is null
      and tm.effective_until is null
      and tm.valid_from <= now()
      and (tm.expires_at is null or tm.expires_at > now())
  ) then
    raise exception 'trusted claims no longer eligible' using errcode = '28000';
  end if;
  if exists (
    select 1
    from unnest(ctx.namespace_ids) as requested_namespace_id
    where not exists (
      select 1
      from public.namespace_grants ng
      where ng.tenant_id = ctx.tenant_id
        and ng.namespace_id = requested_namespace_id
        and ng.principal_id = ctx.principal_id
        and ng.status = 'active'
        and ng.revoked_at is null
        and ng.effective_until is null
        and ng.valid_from <= now()
        and (ng.expires_at is null or ng.expires_at > now())
    )
  ) then
    raise exception 'trusted claims include namespace without active grant' using errcode = '28000';
  end if;
  return jsonb_build_object(
    'request_id', ctx.request_id,
    'tenant_id', ctx.tenant_id,
    'principal_id', ctx.principal_id,
    'actor_role', ctx.actor_role,
    'namespace_ids', to_jsonb(ctx.namespace_ids)
  );
end;
$$;

create or replace function knudg_current_claims()
returns jsonb
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select knudg_private.current_claims_json();
$$;

create or replace function knudg_private.current_tenant_id()
returns uuid
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select (knudg_private.current_claims_json()->>'tenant_id')::uuid;
$$;

create or replace function knudg_private.current_namespace_ids()
returns uuid[]
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select coalesce(array_agg(value::uuid), '{}'::uuid[])
  from jsonb_array_elements_text(knudg_private.current_claims_json()->'namespace_ids') as value;
$$;

create or replace function knudg_set_claims(signed_context jsonb)
returns void
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, knudg_crypto, pg_temp
as $$
declare
  key_row public.claim_signing_keys%rowtype;
  payload_text text;
  payload jsonb;
  signature text;
  computed text;
  claim_principal_id uuid;
  claim_tenant_id uuid;
  claim_actor_role text;
  claim_request_id uuid;
  claim_namespace_ids uuid[];
  claim_expires_at timestamptz;
begin
  if signed_context->>'alg' <> 'HS256' then
    raise exception 'unsupported claim signing algorithm' using errcode = '28000';
  end if;
  payload_text := signed_context->>'payload';
  signature := signed_context->>'signature';
  if payload_text is null or signature is null then
    raise exception 'malformed signed context' using errcode = '28000';
  end if;
  select * into key_row
  from public.claim_signing_keys
  where kid = signed_context->>'kid'
    and alg = 'HS256'
    and disabled_at is null
    and not_before <= now()
    and (not_after is null or not_after > now());
  if not found then
    raise exception 'unknown or inactive claim signing key' using errcode = '28000';
  end if;
  computed := encode(knudg_crypto.hmac(convert_to(payload_text, 'UTF8'), key_row.verify_secret, 'sha256'), 'hex');
  if computed <> lower(signature) then
    raise exception 'bad claim signature' using errcode = '28000';
  end if;
  payload := payload_text::jsonb;
  if payload->>'audience' <> 'knudg-db-local-m0' then
    raise exception 'wrong claim audience' using errcode = '28000';
  end if;
  claim_request_id := (payload->>'request_id')::uuid;
  claim_principal_id := (payload->>'principal_id')::uuid;
  claim_tenant_id := (payload->>'tenant_id')::uuid;
  claim_actor_role := payload->>'actor_role';
  claim_expires_at := (payload->>'expires_at')::timestamptz;
  if claim_expires_at <= now() then
    raise exception 'expired signed context' using errcode = '28000';
  end if;
  select coalesce(array_agg(value::uuid), '{}'::uuid[]) into claim_namespace_ids
  from jsonb_array_elements_text(payload->'namespace_ids') as value;
  if not exists (
    select 1
    from public.principals p
    join public.tenant_memberships tm on tm.principal_id = p.id and tm.tenant_id = claim_tenant_id
    where p.id = claim_principal_id
      and p.disabled_at is null
      and tm.status = 'active'
      and tm.revoked_at is null
      and tm.effective_until is null
      and tm.valid_from <= now()
      and (tm.expires_at is null or tm.expires_at > now())
  ) then
    raise exception 'principal is not eligible for tenant claims' using errcode = '28000';
  end if;
  if exists (
    select 1
    from unnest(claim_namespace_ids) as requested_namespace_id
    where not exists (
      select 1
      from public.namespace_grants ng
      where ng.tenant_id = claim_tenant_id
        and ng.namespace_id = requested_namespace_id
        and ng.principal_id = claim_principal_id
        and ng.status = 'active'
        and ng.revoked_at is null
        and ng.effective_until is null
        and ng.valid_from <= now()
        and (ng.expires_at is null or ng.expires_at > now())
    )
  ) then
    raise exception 'principal is not eligible for requested namespace claims' using errcode = '28000';
  end if;
  if claim_actor_role like '%worker' and not exists (
    select 1 from public.worker_identities w
    where w.principal_id = claim_principal_id
      and w.worker_role = claim_actor_role
      and w.disabled_at is null
  ) then
    raise exception 'worker role is not eligible for tenant claims' using errcode = '28000';
  end if;
  insert into public.request_claim_contexts(
    backend_pid, transaction_id, request_id, claims_digest, principal_id,
    tenant_id, actor_role, namespace_ids, grant_snapshot_version, expires_at
  )
  values (
    pg_backend_pid(), pg_current_xact_id(), claim_request_id,
    encode(knudg_crypto.digest(convert_to(payload_text, 'UTF8'), 'sha256'), 'hex'),
    claim_principal_id, claim_tenant_id, claim_actor_role, claim_namespace_ids, 1, claim_expires_at
  )
  on conflict (backend_pid, transaction_id, request_id) do update
  set claims_digest = excluded.claims_digest,
      principal_id = excluded.principal_id,
      tenant_id = excluded.tenant_id,
      actor_role = excluded.actor_role,
      namespace_ids = excluded.namespace_ids,
      expires_at = excluded.expires_at,
      created_at = now();
  perform set_config('knudg.trusted_request_id', claim_request_id::text, true);
end;
$$;

revoke all on function knudg_set_claims(jsonb) from public;
revoke all on function knudg_current_claims() from public;
grant execute on function knudg_set_claims(jsonb) to knudg_app, knudg_worker;
grant execute on function knudg_current_claims() to knudg_app, knudg_worker, knudg_readonly_ops;

create or replace function knudg_private.card_not_revoked(row_tenant_id uuid, row_namespace_id uuid, row_card_id uuid, row_card_version_id uuid)
returns boolean
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select not exists (
    select 1 from public.revocation_tombstones rt
    where rt.tenant_id = row_tenant_id
      and (
        rt.subject_type = 'tenant'
        or (rt.subject_type = 'namespace' and rt.namespace_id = row_namespace_id)
        or (rt.subject_type = 'card' and rt.card_id = row_card_id)
        or (rt.subject_type = 'card_version' and rt.card_version_id = row_card_version_id)
    )
  );
$$;

create or replace function knudg_private.card_event_visible_not_revoked(
  row_tenant_id uuid,
  row_namespace_id uuid,
  row_card_id uuid,
  row_card_current_version_id uuid,
  row_event_expected_version_id uuid
)
returns boolean
language sql
stable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select knudg_private.card_not_revoked(row_tenant_id, row_namespace_id, row_card_id, row_card_current_version_id)
    and (
      row_event_expected_version_id is null
      or knudg_private.card_not_revoked(row_tenant_id, row_namespace_id, row_card_id, row_event_expected_version_id)
    );
$$;

create or replace function knudg_private.approval_artifact_not_revoked(
  row_tenant_id uuid,
  row_namespace_id uuid,
  row_artifact_type text,
  row_artifact_id uuid,
  row_card_version_id uuid
)
returns boolean
language sql
stable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select case
    when row_artifact_type = 'card_version' and row_card_version_id is not null then exists (
      select 1
      from public.card_versions cv
      join public.experience_cards c on c.tenant_id = cv.tenant_id and c.id = cv.card_id
      where cv.tenant_id = row_tenant_id
        and cv.id = row_card_version_id
        and c.namespace_id = row_namespace_id
        and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, cv.id)
    )
    else not exists (
      select 1
      from public.revocation_tombstones rt
      where rt.tenant_id = row_tenant_id
        and (
          rt.subject_type = 'tenant'
          or (row_namespace_id is not null and rt.subject_type = 'namespace' and rt.namespace_id = row_namespace_id)
          or rt.subject_id = row_artifact_id
        )
    )
  end;
$$;

create or replace function knudg_private.principal_has_namespace_scope(
  row_tenant_id uuid,
  row_namespace_id uuid,
  row_principal_id uuid,
  required_scopes text[]
)
returns boolean
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select exists (
    select 1
    from public.namespace_grants ng
    where ng.tenant_id = row_tenant_id
      and ng.namespace_id = row_namespace_id
      and ng.principal_id = row_principal_id
      and ng.grant_scope = any(required_scopes)
      and ng.status = 'active'
      and ng.revoked_at is null
      and ng.effective_until is null
      and ng.valid_from <= now()
      and (ng.expires_at is null or ng.expires_at > now())
  );
$$;

create or replace function knudg_private.break_glass_case_allows(
  row_tenant_id uuid,
  row_case_id uuid,
  row_operation text,
  row_namespace_id uuid,
  row_card_id uuid,
  row_card_version_id uuid
)
returns boolean
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select exists (
    select 1
    from public.break_glass_cases bg
    where bg.tenant_id = row_tenant_id
      and bg.id = row_case_id
      and bg.status = 'active'
      and bg.closed_at is null
      and bg.expires_at > now()
      and row_operation = any(bg.permitted_operations)
      and (
        (bg.target_type = 'tenant' and bg.target_id = row_tenant_id)
        or (bg.target_type = 'namespace' and bg.target_id = row_namespace_id)
        or (bg.target_type = 'card' and bg.target_id = row_card_id)
        or (bg.target_type = 'card_version' and bg.target_id = row_card_version_id)
      )
  );
$$;

create or replace function knudg_private.current_worker_allows(row_operation text)
returns boolean
language sql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select exists (
    select 1
    from public.worker_identities w
    where w.principal_id = (knudg_private.current_claims_json()->>'principal_id')::uuid
      and w.worker_role = knudg_private.current_claims_json()->>'actor_role'
      and w.disabled_at is null
      and row_operation = any(w.allowed_operations)
  );
$$;

create or replace function knudg_private.json_has_duplicate_keys(row_json json)
returns boolean
language plpgsql
immutable
set search_path = pg_catalog, pg_temp
as $$
declare
  row_type text;
  key_count integer;
  distinct_key_count integer;
  child json;
begin
  row_type := json_typeof(row_json);
  if row_type = 'object' then
    select count(*), count(distinct key)
    into key_count, distinct_key_count
    from json_each(row_json);
    if key_count <> distinct_key_count then
      return true;
    end if;
    for child in select value from json_each(row_json) loop
      if knudg_private.json_has_duplicate_keys(child) then
        return true;
      end if;
    end loop;
  elsif row_type = 'array' then
    for child in select value from json_array_elements(row_json) loop
      if knudg_private.json_has_duplicate_keys(child) then
        return true;
      end if;
    end loop;
  end if;
  return false;
end;
$$;

create or replace function knudg_private.json_has_non_ascii_keys(row_json json)
returns boolean
language plpgsql
immutable
set search_path = pg_catalog, pg_temp
as $$
declare
  row_type text;
  child json;
  child_key text;
begin
  row_type := json_typeof(row_json);
  if row_type = 'object' then
    for child_key, child in select key, value from json_each(row_json) loop
      if child_key !~ '^[\u0000-\u007f]+$' then
        return true;
      end if;
      if knudg_private.json_has_non_ascii_keys(child) then
        return true;
      end if;
    end loop;
  elsif row_type = 'array' then
    for child in select value from json_array_elements(row_json) loop
      if knudg_private.json_has_non_ascii_keys(child) then
        return true;
      end if;
    end loop;
  end if;
  return false;
end;
$$;

create or replace function knudg_private.json_has_non_portable_numbers(row_json json)
returns boolean
language plpgsql
immutable
set search_path = pg_catalog, pg_temp
as $$
declare
  row_type text;
  raw_number text;
  child json;
begin
  row_type := json_typeof(row_json);
  if row_type = 'number' then
    raw_number := row_json::text;
    if raw_number ~ '[\.eE]' then
      return true;
    end if;
    return raw_number::numeric < -9007199254740991 or raw_number::numeric > 9007199254740991;
  elsif row_type = 'object' then
    for child in select value from json_each(row_json) loop
      if knudg_private.json_has_non_portable_numbers(child) then
        return true;
      end if;
    end loop;
  elsif row_type = 'array' then
    for child in select value from json_array_elements(row_json) loop
      if knudg_private.json_has_non_portable_numbers(child) then
        return true;
      end if;
    end loop;
  end if;
  return false;
end;
$$;

create or replace function knudg_submit_candidate(
  row_namespace_id uuid,
  row_card_id uuid,
  row_card_version_id uuid,
  row_payload_raw text,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  existing_idempotency public.idempotency_keys%rowtype;
  namespace_row public.namespaces%rowtype;
  row_payload_json_source json;
  row_payload_json jsonb;
  row_payload_digest text;
  new_event_id uuid;
  new_position bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_payload_raw is null or row_payload_raw = '' then
    raise exception 'payload raw json is required' using errcode = '23514';
  end if;
  begin
    row_payload_json_source := row_payload_raw::json;
  exception when others then
    raise exception 'payload must be valid json' using errcode = '22P02';
  end;
  if json_typeof(row_payload_json_source) <> 'object' then
    raise exception 'payload must be a json object' using errcode = '23514';
  end if;
  if knudg_private.json_has_duplicate_keys(row_payload_json_source) then
    raise exception 'payload contains duplicate object keys' using errcode = '23514';
  end if;
  if knudg_private.json_has_non_ascii_keys(row_payload_json_source) then
    raise exception 'payload object keys must be ASCII for M0 canonical digesting' using errcode = '23514';
  end if;
  if knudg_private.json_has_non_portable_numbers(row_payload_json_source) then
    raise exception 'payload contains non-portable JSON numbers' using errcode = '23514';
  end if;
  row_payload_json := row_payload_raw::jsonb;
  if not knudg_private.card_payload_v1_is_valid(row_payload_json) then
    raise exception 'payload does not satisfy card payload schema v1' using errcode = '23514';
  end if;
  if coalesce(row_payload_json #>> '{privacy,source_class}', '') <> 'synthetic'
    or coalesce(row_payload_json #>> '{provenance,source_class}', '') <> 'synthetic' then
    raise exception 'submit_candidate is synthetic-only until PR-006 intake safety gate is active' using errcode = '23514';
  end if;
  row_payload_digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(row_payload_json), 'sha256'), 'hex');
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;
  if claim_actor_role <> 'app_user' then
    raise exception 'submit_candidate requires app_user actor role' using errcode = '28000';
  end if;
  if row_namespace_id <> all(knudg_private.current_namespace_ids()) then
    raise exception 'namespace not present in trusted claims' using errcode = '28000';
  end if;
  if not knudg_private.principal_has_namespace_scope(
    claim_tenant_id, row_namespace_id, claim_principal_id, array['submit','admin']
  ) then
    raise exception 'submit_candidate requires submit or admin namespace grant' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'submit_candidate'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      ce.previous_status, ce.next_status, c.current_version_id
    into event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    return next;
    return;
  end if;

  select *
  into namespace_row
  from public.namespaces n
  where n.tenant_id = claim_tenant_id
    and n.id = row_namespace_id
  for update;
  if not found then
    raise exception 'namespace not found or not authorized' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'submit_candidate'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;
  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      ce.previous_status, ce.next_status, c.current_version_id
    into event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    return next;
    return;
  end if;

  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.experience_cards(
    tenant_id, id, namespace_id, current_version_id, status,
    outcome_type, quality_state, evidence_strength, created_by
  )
  values (
    claim_tenant_id, row_card_id, row_namespace_id, row_card_version_id, 'candidate_created',
    row_payload_json->>'outcome_type', row_payload_json->>'quality_state',
    row_payload_json->>'evidence_strength', claim_principal_id
  );

  insert into public.card_versions(
    tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by
  )
  values (
    claim_tenant_id, row_card_version_id, row_card_id, 1, 1,
    row_payload_json, row_payload_digest, claim_principal_id
  );

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, 1, 'card_created',
    claim_principal_id, claim_actor_role, null, 'candidate_created', null,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'submit_candidate', 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := 1;
  card_id := row_card_id;
  previous_status := null;
  next_status := 'candidate_created';
  current_version_id := row_card_version_id;
  return next;
end;
$$;
revoke all on function knudg_submit_candidate(uuid, uuid, uuid, text, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_submit_candidate(uuid, uuid, uuid, text, text, text, uuid, jsonb, text) to knudg_app;

create or replace function knudg_append_card_event(
  row_card_id uuid,
  row_event_type text,
  row_expected_current_version uuid,
  row_previous_status text,
  row_next_status text,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;
  if row_event_type not in ('discard_requested','discard_restored','approval_digest_invalidated') then
    raise exception 'event type requires an operation-specific command function' using errcode = '23514';
  end if;
  if claim_actor_role <> 'app_user' then
    raise exception 'append_card_event requires app_user actor role for supported event types' using errcode = '28000';
  end if;

  select *
  into card_row
  from public.experience_cards c
  where c.tenant_id = claim_tenant_id
    and c.id = row_card_id
    and c.namespace_id = any(knudg_private.current_namespace_ids())
    and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
  for update;

  if not found then
    raise exception 'card not found or not authorized' using errcode = '28000';
  end if;
  if not knudg_private.principal_has_namespace_scope(
    claim_tenant_id, card_row.namespace_id, claim_principal_id, array['submit','admin']
  ) then
    raise exception 'append_card_event requires submit or admin namespace grant' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'append_card_event'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      ce.previous_status, ce.next_status, c.current_version_id
    into event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    return next;
    return;
  end if;
  if card_row.current_version_id <> row_expected_current_version then
    raise exception 'stale expected current version' using errcode = '40001';
  end if;
  if card_row.status <> row_previous_status then
    raise exception 'previous status does not match current card status' using errcode = '40001';
  end if;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = row_card_id;

  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, new_seq, row_event_type,
    claim_principal_id, claim_actor_role, row_previous_status, row_next_status,
    row_expected_current_version, row_correlation_id, row_idempotency_key, 1,
    row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  update public.experience_cards
  set status = row_next_status, updated_at = now()
  where tenant_id = claim_tenant_id and id = row_card_id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'append_card_event', 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := row_card_id;
  previous_status := row_previous_status;
  next_status := row_next_status;
  current_version_id := row_expected_current_version;
  return next;
end;
$$;
revoke all on function knudg_append_card_event(uuid, text, uuid, text, text, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_append_card_event(uuid, text, uuid, text, text, text, text, uuid, jsonb, text) to knudg_app;

create or replace function knudg_private.worker_advance_card(
  row_operation text,
  row_required_role text,
  row_event_type text,
  row_allowed_previous_statuses text[],
  row_next_status text,
  row_card_id uuid,
  row_expected_current_version uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb,
  row_event_payload_digest text
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role <> row_required_role then
    raise exception '% requires % actor role', row_operation, row_required_role using errcode = '28000';
  end if;
  if not knudg_private.current_worker_allows(row_operation) then
    raise exception 'worker is not allowed to perform %', row_operation using errcode = '28000';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;

  select *
  into card_row
  from public.experience_cards c
  where c.tenant_id = claim_tenant_id
    and c.id = row_card_id
    and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
  for update;
  if not found then
    raise exception 'card not found or not authorized' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = row_operation
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;
  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      ce.previous_status, ce.next_status, c.current_version_id
    into event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    return next;
    return;
  end if;

  if card_row.current_version_id <> row_expected_current_version then
    raise exception 'stale expected current version' using errcode = '40001';
  end if;
  if card_row.status <> all(row_allowed_previous_statuses) then
    raise exception 'previous status does not match current card status' using errcode = '40001';
  end if;
  if not exists (
    select 1
    from public.card_state_transitions t
    where t.from_status = card_row.status
      and t.to_status = row_next_status
      and t.event_type = row_event_type
      and t.actor_role = claim_actor_role
  ) then
    raise exception 'card state transition is not allowed' using errcode = '23514';
  end if;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = row_card_id;
  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, new_seq, row_event_type,
    claim_principal_id, claim_actor_role, card_row.status, row_next_status, row_expected_current_version,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  update public.experience_cards
  set status = row_next_status, updated_at = now()
  where tenant_id = claim_tenant_id and id = row_card_id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), row_operation, 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := row_card_id;
  previous_status := card_row.status;
  next_status := row_next_status;
  current_version_id := row_expected_current_version;
  return next;
end;
$$;
revoke all on function knudg_private.worker_advance_card(text, text, text, text[], text, uuid, uuid, text, text, uuid, jsonb, text) from public;

create or replace function knudg_accept_admission(
  row_card_id uuid,
  row_expected_current_version uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  return query
  select *
  from knudg_private.worker_advance_card(
    'accept_admission', 'ingestion_worker', 'admission_accepted',
    array['candidate_created','deferred'], 'pending_admission',
    row_card_id, row_expected_current_version, row_idempotency_key, row_request_digest,
    row_correlation_id, row_event_payload_json, row_event_payload_digest
  );
end;
$$;
revoke all on function knudg_accept_admission(uuid, uuid, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_accept_admission(uuid, uuid, text, text, uuid, jsonb, text) to knudg_worker;

create or replace function knudg_request_redaction(
  row_card_id uuid,
  row_expected_current_version uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  return query
  select *
  from knudg_private.worker_advance_card(
    'request_redaction', 'ingestion_worker', 'redaction_requested',
    array['pending_admission'], 'pending_redaction',
    row_card_id, row_expected_current_version, row_idempotency_key, row_request_digest,
    row_correlation_id, row_event_payload_json, row_event_payload_digest
  );
end;
$$;
revoke all on function knudg_request_redaction(uuid, uuid, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_request_redaction(uuid, uuid, text, text, uuid, jsonb, text) to knudg_worker;

create or replace function knudg_complete_redaction(
  row_card_id uuid,
  row_expected_current_version uuid,
  row_new_card_version_id uuid,
  row_redacted_payload_raw text,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  current_version_row public.card_versions%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  redacted_payload_json_source json;
  redacted_payload_json jsonb;
  redacted_payload_digest text;
  effective_version_id uuid;
  new_version_number integer;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role <> 'redaction_worker' then
    raise exception 'complete_redaction requires redaction_worker actor role' using errcode = '28000';
  end if;
  if not knudg_private.current_worker_allows('complete_redaction') then
    raise exception 'worker is not allowed to perform complete_redaction' using errcode = '28000';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;

  select *
  into card_row
  from public.experience_cards c
  where c.tenant_id = claim_tenant_id
    and c.id = row_card_id
    and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
  for update;
  if not found then
    raise exception 'card not found or not authorized' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'complete_redaction'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;
  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      ce.previous_status, ce.next_status, c.current_version_id
    into event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    return next;
    return;
  end if;

  if card_row.current_version_id <> row_expected_current_version then
    raise exception 'stale expected current version' using errcode = '40001';
  end if;
  if card_row.status <> 'pending_redaction' then
    raise exception 'previous status does not match current card status' using errcode = '40001';
  end if;
  if not exists (
    select 1 from public.card_state_transitions t
    where t.from_status = 'pending_redaction'
      and t.to_status = 'pending_review'
      and t.event_type = 'redaction_completed'
      and t.actor_role = claim_actor_role
  ) then
    raise exception 'card state transition is not allowed' using errcode = '23514';
  end if;

  select *
  into current_version_row
  from public.card_versions cv
  where cv.tenant_id = claim_tenant_id and cv.id = row_expected_current_version
  for update;
  if not found then
    raise exception 'current card version not found' using errcode = '23503';
  end if;
  effective_version_id := row_expected_current_version;

  if row_redacted_payload_raw is not null and row_redacted_payload_raw <> '' then
    begin
      redacted_payload_json_source := row_redacted_payload_raw::json;
    exception when others then
      raise exception 'redacted payload must be valid json' using errcode = '22P02';
    end;
    if json_typeof(redacted_payload_json_source) <> 'object' then
      raise exception 'redacted payload must be a json object' using errcode = '23514';
    end if;
    if knudg_private.json_has_duplicate_keys(redacted_payload_json_source) then
      raise exception 'redacted payload contains duplicate object keys' using errcode = '23514';
    end if;
    if knudg_private.json_has_non_ascii_keys(redacted_payload_json_source) then
      raise exception 'redacted payload object keys must be ASCII for M0 canonical digesting' using errcode = '23514';
    end if;
    if knudg_private.json_has_non_portable_numbers(redacted_payload_json_source) then
      raise exception 'redacted payload contains non-portable JSON numbers' using errcode = '23514';
    end if;
    redacted_payload_json := row_redacted_payload_raw::jsonb;
    if not knudg_private.card_payload_v1_is_valid(redacted_payload_json) then
      raise exception 'redacted payload does not satisfy card payload schema v1' using errcode = '23514';
    end if;
    redacted_payload_digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(redacted_payload_json), 'sha256'), 'hex');
    if redacted_payload_digest <> current_version_row.payload_digest then
      if row_new_card_version_id is null then
        raise exception 'new card version id is required when redacted payload changes' using errcode = '23514';
      end if;
      select coalesce(max(cv.version_number), 0) + 1
      into new_version_number
      from public.card_versions cv
      where cv.tenant_id = claim_tenant_id and cv.card_id = row_card_id;
      insert into public.card_versions(
        tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by
      )
      values (
        claim_tenant_id, row_new_card_version_id, row_card_id, new_version_number, 1,
        redacted_payload_json, redacted_payload_digest, claim_principal_id
      );
      effective_version_id := row_new_card_version_id;
    end if;
  end if;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = row_card_id;
  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, new_seq, 'redaction_completed',
    claim_principal_id, claim_actor_role, 'pending_redaction', 'pending_review', row_expected_current_version,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  update public.experience_cards
  set status = 'pending_review', current_version_id = effective_version_id, updated_at = now()
  where tenant_id = claim_tenant_id and id = row_card_id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'complete_redaction', 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := row_card_id;
  previous_status := 'pending_redaction';
  next_status := 'pending_review';
  current_version_id := effective_version_id;
  return next;
end;
$$;
revoke all on function knudg_complete_redaction(uuid, uuid, uuid, text, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_complete_redaction(uuid, uuid, uuid, text, text, text, uuid, jsonb, text) to knudg_worker;

create or replace function knudg_request_private_approval(
  row_card_id uuid,
  row_expected_current_version uuid,
  row_challenge_id uuid,
  row_policy_version text,
  row_policy_digest text,
  row_challenge_digest text,
  row_origin text,
  row_expires_at timestamptz,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid,
  challenge_id uuid,
  challenge_digest text
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  version_row public.card_versions%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role <> 'review_worker' then
    raise exception 'request_private_approval requires review_worker actor role' using errcode = '28000';
  end if;
  if not knudg_private.current_worker_allows('request_private_approval') then
    raise exception 'worker is not allowed to perform request_private_approval' using errcode = '28000';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;
  if row_challenge_id is null then
    raise exception 'challenge id is required' using errcode = '23514';
  end if;
  if row_policy_version is null or row_policy_version = '' then
    raise exception 'policy version is required' using errcode = '23514';
  end if;
  if row_policy_digest is null or row_policy_digest = '' then
    raise exception 'policy digest is required' using errcode = '23514';
  end if;
  if row_challenge_digest is null or row_challenge_digest = '' then
    raise exception 'challenge digest is required' using errcode = '23514';
  end if;
  if row_origin is null or row_origin = '' then
    raise exception 'challenge origin is required' using errcode = '23514';
  end if;
  if row_expires_at is null or row_expires_at <= now() then
    raise exception 'challenge expiry must be in the future' using errcode = '23514';
  end if;

  select *
  into card_row
  from public.experience_cards c
  where c.tenant_id = claim_tenant_id
    and c.id = row_card_id
    and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
  for update;
  if not found then
    raise exception 'card not found or not authorized' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'request_private_approval'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;
  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      ce.previous_status, ce.next_status, c.current_version_id, ac.id, ac.challenge_digest
    into event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id, challenge_id, challenge_digest
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    join public.approval_challenges ac
      on ac.tenant_id = ce.tenant_id
      and ac.id = row_challenge_id
      and ac.subject_id = c.created_by
      and ac.namespace_id is not distinct from c.namespace_id
      and ac.consent_scope = 'private_retention'
      and ac.artifact_type = 'card_version'
      and ac.artifact_id = c.current_version_id
      and ac.card_version_id is not distinct from c.current_version_id
      and ac.policy_version = row_policy_version
      and ac.policy_digest = row_policy_digest
      and ac.challenge_digest = row_challenge_digest
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    if not found then
      raise exception 'idempotency replay does not match persisted private approval challenge' using errcode = '23505';
    end if;
    return next;
    return;
  end if;

  if card_row.current_version_id <> row_expected_current_version then
    raise exception 'stale expected current version' using errcode = '40001';
  end if;
  if card_row.status <> 'pending_review' then
    raise exception 'previous status does not match current card status' using errcode = '40001';
  end if;

  select *
  into version_row
  from public.card_versions cv
  where cv.tenant_id = claim_tenant_id and cv.id = row_expected_current_version;
  if not found then
    raise exception 'current card version not found' using errcode = '23503';
  end if;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = row_card_id;
  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.approval_challenges(
    tenant_id, id, subject_id, namespace_id, consent_scope, artifact_type, artifact_id,
    card_version_id, artifact_digest, policy_version, policy_digest, challenge_digest,
    origin, expires_at, created_by
  )
  values (
    claim_tenant_id, row_challenge_id, card_row.created_by, card_row.namespace_id,
    'private_retention', 'card_version', row_expected_current_version, row_expected_current_version,
    version_row.payload_digest, row_policy_version, row_policy_digest, row_challenge_digest,
    row_origin, row_expires_at, claim_principal_id
  );

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, new_seq, 'user_approval_requested',
    claim_principal_id, claim_actor_role, 'pending_review', 'awaiting_user_approval', row_expected_current_version,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  update public.experience_cards
  set status = 'awaiting_user_approval', updated_at = now()
  where tenant_id = claim_tenant_id and id = row_card_id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'request_private_approval', 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := row_card_id;
  previous_status := 'pending_review';
  next_status := 'awaiting_user_approval';
  current_version_id := row_expected_current_version;
  challenge_id := row_challenge_id;
  challenge_digest := row_challenge_digest;
  return next;
end;
$$;
revoke all on function knudg_request_private_approval(uuid, uuid, uuid, text, text, text, text, timestamptz, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_request_private_approval(uuid, uuid, uuid, text, text, text, text, timestamptz, text, text, uuid, jsonb, text) to knudg_worker;

create or replace function knudg_approve_private_retention(
  row_card_id uuid,
  row_challenge_id uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  consent_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  version_row public.card_versions%rowtype;
  challenge_row public.approval_challenges%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_consent_id uuid;
  new_position bigint;
  new_seq bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role <> 'app_user' then
    raise exception 'approve_private_retention requires app_user actor role' using errcode = '28000';
  end if;
  if row_challenge_id is null then
    raise exception 'challenge id is required' using errcode = '23514';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;

  select *
  into card_row
  from public.experience_cards c
  where c.tenant_id = claim_tenant_id
    and c.id = row_card_id
    and c.namespace_id = any(knudg_private.current_namespace_ids())
    and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
  for update;
  if not found then
    raise exception 'card not found or not authorized' using errcode = '28000';
  end if;
  if not knudg_private.principal_has_namespace_scope(
    claim_tenant_id, card_row.namespace_id, claim_principal_id, array['submit','admin']
  ) then
    raise exception 'approve_private_retention requires submit or admin namespace grant' using errcode = '28000';
  end if;

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'approve_private_retention'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;
  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      cr.id, ce.previous_status, ce.next_status, c.current_version_id
    into event_id, event_stream_position, event_seq, card_id, consent_id, previous_status, next_status, current_version_id
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    join public.consent_records cr
      on cr.tenant_id = ce.tenant_id
      and cr.grant_card_event_id = ce.event_id
      and cr.challenge_id = row_challenge_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id;
    if not found then
      raise exception 'idempotency replay does not match persisted private retention consent' using errcode = '23505';
    end if;
    return next;
    return;
  end if;

  if card_row.status <> 'awaiting_user_approval' then
    raise exception 'previous status does not match current card status' using errcode = '40001';
  end if;

  select *
  into version_row
  from public.card_versions cv
  where cv.tenant_id = claim_tenant_id and cv.id = card_row.current_version_id;
  if not found then
    raise exception 'current card version not found' using errcode = '23503';
  end if;

  select *
  into challenge_row
  from public.approval_challenges ac
  where ac.tenant_id = claim_tenant_id and ac.id = row_challenge_id
  for update;
  if not found then
    raise exception 'approval challenge not found' using errcode = '23503';
  end if;
  if challenge_row.subject_id <> claim_principal_id
    or challenge_row.namespace_id is distinct from card_row.namespace_id
    or challenge_row.consent_scope <> 'private_retention'
    or challenge_row.artifact_type <> 'card_version'
    or challenge_row.artifact_id <> card_row.current_version_id
    or challenge_row.card_version_id is distinct from card_row.current_version_id
    or challenge_row.artifact_digest <> version_row.payload_digest
    or challenge_row.invalidated_at is not null
    or challenge_row.used_by_consent_id is not null
    or challenge_row.expires_at <= now() then
    raise exception 'approval challenge is not active for current private retention artifact' using errcode = '23514';
  end if;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = row_card_id;
  new_event_id := knudg_crypto.gen_random_uuid();
  new_consent_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, new_seq, 'private_approved',
    claim_principal_id, claim_actor_role, 'awaiting_user_approval', 'approved_private', card_row.current_version_id,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  insert into public.consent_records(
    tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
    artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
    grant_card_event_id, retention_policy, retention_purpose
  )
  values (
    claim_tenant_id, new_consent_id, claim_principal_id, 'private_retention', card_row.namespace_id,
    'card_version', card_row.current_version_id, card_row.current_version_id, version_row.payload_digest,
    challenge_row.policy_version, challenge_row.policy_digest, challenge_row.id, challenge_row.challenge_digest,
    new_event_id, 'private_mvp_default', 'agent_experience_reuse'
  );

  update public.experience_cards
  set status = 'approved_private', updated_at = now()
  where tenant_id = claim_tenant_id and id = row_card_id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'approve_private_retention', 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := row_card_id;
  consent_id := new_consent_id;
  previous_status := 'awaiting_user_approval';
  next_status := 'approved_private';
  current_version_id := card_row.current_version_id;
  return next;
end;
$$;
revoke all on function knudg_approve_private_retention(uuid, uuid, text, text, uuid, jsonb, text) from public;
grant execute on function knudg_approve_private_retention(uuid, uuid, text, text, uuid, jsonb, text) to knudg_app;

create or replace function knudg_insert_audit_event(
  row_action text,
  row_target_type text,
  row_target_id uuid,
  row_reason_code text,
  row_sanitized_detail text,
  row_correlation_id uuid
)
returns table (
  audit_event_id uuid,
  created_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  new_audit_event_id uuid;
  new_created_at timestamptz;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_action is null or row_action = '' then
    raise exception 'audit action is required' using errcode = '23514';
  end if;
  if row_target_type is null or row_target_type = '' then
    raise exception 'audit target type is required' using errcode = '23514';
  end if;
  if row_reason_code is null or row_reason_code = '' then
    raise exception 'audit reason code is required' using errcode = '23514';
  end if;
  if not knudg_private.audit_detail_is_sanitized(row_sanitized_detail) then
    raise exception 'audit detail is not sanitized' using errcode = '23514';
  end if;

  new_audit_event_id := knudg_crypto.gen_random_uuid();
  insert into public.audit_events(
    tenant_id, id, actor_id, actor_role, action, target_type, target_id,
    reason_code, sanitized_detail, correlation_id
  )
  values (
    claim_tenant_id, new_audit_event_id, claim_principal_id, claim_actor_role,
    row_action, row_target_type, row_target_id, row_reason_code,
    row_sanitized_detail, row_correlation_id
  )
  returning id, audit_events.created_at into audit_event_id, created_at;

  return next;
end;
$$;
revoke all on function knudg_insert_audit_event(text, text, uuid, text, text, uuid) from public;
grant execute on function knudg_insert_audit_event(text, text, uuid, text, text, uuid) to knudg_app, knudg_worker;

create or replace function knudg_revoke_subject(
  row_subject_type text,
  row_subject_id uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_reason text,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  card_version_id uuid,
  revocation_epoch bigint
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  target_version_id uuid;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
  new_epoch bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_subject_type not in ('card', 'card_version') then
    raise exception 'M0 revoke_subject supports only card and card_version' using errcode = '23514';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_reason is null or row_reason = '' then
    raise exception 'revocation reason is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;
  if claim_actor_role <> 'app_user' then
    raise exception 'revoke_subject requires app_user actor role for M0 card revocation' using errcode = '28000';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    'knudg:revoke_subject:' || claim_tenant_id::text || ':' || row_subject_type || ':' ||
    row_subject_id::text || ':v1:' || row_idempotency_key,
    0
  ));

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'revoke_subject'
    and ik.logical_object_type = row_subject_type
    and ik.logical_object_id = row_subject_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      rt.card_version_id, rt.revocation_epoch
    into event_id, event_stream_position, event_seq, card_id, card_version_id, revocation_epoch
    from public.card_events ce
    join public.revocation_tombstones rt
      on rt.tenant_id = ce.tenant_id and rt.card_revocation_event_id = ce.event_id
    join public.experience_cards c
      on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id
      and rt.subject_type = row_subject_type
      and rt.subject_id = row_subject_id
      and rt.revoked_by = claim_principal_id
      and c.namespace_id = any(knudg_private.current_namespace_ids())
      and knudg_private.principal_has_namespace_scope(
        claim_tenant_id, c.namespace_id, claim_principal_id, array['submit','admin']
      )
    limit 1;
    if not found then
      raise exception 'idempotent revoke_subject replay is not authorized' using errcode = '28000';
    end if;
    return next;
    return;
  end if;

  if row_subject_type = 'card' then
    select *
    into card_row
    from public.experience_cards c
    where c.tenant_id = claim_tenant_id
      and c.id = row_subject_id
      and c.namespace_id = any(knudg_private.current_namespace_ids())
      and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
    for update;
    target_version_id := card_row.current_version_id;
  else
    select c.*
    into card_row
    from public.card_versions cv
    join public.experience_cards c on c.tenant_id = cv.tenant_id and c.id = cv.card_id
    where cv.tenant_id = claim_tenant_id
      and cv.id = row_subject_id
      and c.namespace_id = any(knudg_private.current_namespace_ids())
      and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, cv.id)
    for update of c;
    target_version_id := row_subject_id;
  end if;

  if not found then
    raise exception 'subject not found or not authorized' using errcode = '28000';
  end if;
  if row_subject_type = 'card_version' and target_version_id <> card_row.current_version_id then
    raise exception 'M0 card_version revocation only supports the current card version' using errcode = '23514';
  end if;
  if not knudg_private.principal_has_namespace_scope(
    claim_tenant_id, card_row.namespace_id, claim_principal_id, array['submit','admin']
  ) then
    raise exception 'revoke_subject requires submit or admin namespace grant' using errcode = '28000';
  end if;

  insert into public.tenant_revocation_epochs(tenant_id, last_epoch)
  values (claim_tenant_id, 0)
  on conflict (tenant_id) do nothing;

  update public.tenant_revocation_epochs
  set last_epoch = last_epoch + 1, updated_at = now()
  where tenant_id = claim_tenant_id
  returning last_epoch into new_epoch;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = card_row.id;

  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, card_row.id, new_event_id, new_position, new_seq, 'revoked',
    claim_principal_id, claim_actor_role, card_row.status, 'revoked', card_row.current_version_id,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  insert into public.revocation_tombstones(
    tenant_id, id, subject_type, subject_id, card_id, card_version_id,
    revocation_epoch, revocation_event_source_type, card_revocation_event_id,
    revoked_by, reason
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), row_subject_type, row_subject_id,
    card_row.id, target_version_id, new_epoch, 'card', new_event_id,
    claim_principal_id, row_reason
  );

  update public.experience_cards
  set status = 'revoked', updated_at = now()
  where tenant_id = claim_tenant_id and id = card_row.id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'revoke_subject', row_subject_type, row_subject_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  insert into public.audit_events(
    tenant_id, id, actor_id, actor_role, action, target_type, target_id,
    reason_code, sanitized_detail, correlation_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), claim_principal_id, claim_actor_role,
    'revoke_subject', row_subject_type, row_subject_id,
    'user_requested_revocation', 'Revoked subject through M0 revoke command.', row_correlation_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := card_row.id;
  card_version_id := target_version_id;
  revocation_epoch := new_epoch;
  return next;
end;
$$;
revoke all on function knudg_revoke_subject(text, uuid, text, text, uuid, text, jsonb, text) from public;
grant execute on function knudg_revoke_subject(text, uuid, text, text, uuid, text, jsonb, text) to knudg_app;

create or replace function knudg_break_glass_revoke_subject(
  row_break_glass_case_id uuid,
  row_subject_type text,
  row_subject_id uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_reason text,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  card_version_id uuid,
  revocation_epoch bigint,
  break_glass_case_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  target_version_id uuid;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
  new_epoch bigint;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role <> 'break_glass_admin' then
    raise exception 'break-glass revoke requires break_glass_admin actor role' using errcode = '28000';
  end if;
  if not exists (
    select 1
    from public.tenant_memberships tm
    where tm.tenant_id = claim_tenant_id
      and tm.principal_id = claim_principal_id
      and tm.membership_role = 'break_glass_admin'
      and tm.status = 'active'
      and tm.revoked_at is null
      and tm.effective_until is null
      and tm.valid_from <= now()
      and (tm.expires_at is null or tm.expires_at > now())
  ) then
    raise exception 'break-glass revoke requires active break_glass_admin membership' using errcode = '28000';
  end if;
  if row_subject_type not in ('card', 'card_version') then
    raise exception 'M0 break-glass revoke supports only card and card_version' using errcode = '23514';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_reason is null or row_reason = '' then
    raise exception 'revocation reason is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    'knudg:break_glass_revoke_subject:' || claim_tenant_id::text || ':' ||
    row_subject_type || ':' || row_subject_id::text || ':v1:' || row_idempotency_key,
    0
  ));

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'break_glass_revoke_subject'
    and ik.logical_object_type = row_subject_type
    and ik.logical_object_id = row_subject_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id,
      rt.card_version_id, rt.revocation_epoch
    into event_id, event_stream_position, event_seq, card_id, card_version_id, revocation_epoch
    from public.card_events ce
    join public.revocation_tombstones rt
      on rt.tenant_id = ce.tenant_id and rt.card_revocation_event_id = ce.event_id
    join public.experience_cards c
      on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id
      and rt.subject_type = row_subject_type
      and rt.subject_id = row_subject_id
      and rt.revoked_by = claim_principal_id
      and knudg_private.break_glass_case_allows(
        claim_tenant_id, row_break_glass_case_id, 'break_glass_revoke_subject',
        c.namespace_id, c.id, rt.card_version_id
      )
    limit 1;
    if not found then
      raise exception 'idempotent break-glass revoke replay is not authorized' using errcode = '28000';
    end if;
    break_glass_case_id := row_break_glass_case_id;
    return next;
    return;
  end if;

  if row_subject_type = 'card' then
    select *
    into card_row
    from public.experience_cards c
    where c.tenant_id = claim_tenant_id
      and c.id = row_subject_id
      and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
    for update;
  else
    select c.*
    into card_row
    from public.card_versions cv
    join public.experience_cards c on c.tenant_id = cv.tenant_id and c.id = cv.card_id
    where cv.tenant_id = claim_tenant_id
      and cv.id = row_subject_id
      and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, cv.id)
    for update of c;
  end if;

  if not found then
    raise exception 'subject not found or already revoked' using errcode = '28000';
  end if;
  target_version_id := case when row_subject_type = 'card' then card_row.current_version_id else row_subject_id end;
  if row_subject_type = 'card_version' and target_version_id <> card_row.current_version_id then
    raise exception 'M0 break-glass card_version revocation only supports the current card version' using errcode = '23514';
  end if;
  if not knudg_private.break_glass_case_allows(
    claim_tenant_id, row_break_glass_case_id, 'break_glass_revoke_subject',
    card_row.namespace_id, card_row.id, target_version_id
  ) then
    raise exception 'break-glass case does not permit this revoke' using errcode = '28000';
  end if;

  insert into public.tenant_revocation_epochs(tenant_id, last_epoch)
  values (claim_tenant_id, 0)
  on conflict (tenant_id) do nothing;

  update public.tenant_revocation_epochs
  set last_epoch = last_epoch + 1, updated_at = now()
  where tenant_id = claim_tenant_id
  returning last_epoch into new_epoch;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = card_row.id;

  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, card_row.id, new_event_id, new_position, new_seq, 'revoked',
    claim_principal_id, claim_actor_role, card_row.status, 'revoked', target_version_id,
    row_correlation_id, row_idempotency_key, 1, row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  insert into public.revocation_tombstones(
    tenant_id, id, subject_type, subject_id, card_id, card_version_id,
    revocation_epoch, revocation_event_source_type, card_revocation_event_id,
    revoked_by, reason
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), row_subject_type, row_subject_id,
    card_row.id, target_version_id, new_epoch, 'card', new_event_id,
    claim_principal_id, row_reason
  );

  update public.experience_cards
  set status = 'revoked', updated_at = now()
  where tenant_id = claim_tenant_id and id = card_row.id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'break_glass_revoke_subject', row_subject_type, row_subject_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  insert into public.audit_events(
    tenant_id, id, actor_id, actor_role, action, target_type, target_id,
    reason_code, sanitized_detail, correlation_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), claim_principal_id, claim_actor_role,
    'break_glass_revoke_subject', row_subject_type, row_subject_id,
    'break_glass_emergency_revoke', 'Emergency break-glass revoke executed with active case.', row_correlation_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := card_row.id;
  card_version_id := target_version_id;
  revocation_epoch := new_epoch;
  break_glass_case_id := row_break_glass_case_id;
  return next;
end;
$$;
revoke all on function knudg_break_glass_revoke_subject(uuid, text, uuid, text, text, uuid, text, jsonb, text) from public;
grant execute on function knudg_break_glass_revoke_subject(uuid, text, uuid, text, text, uuid, text, jsonb, text) to knudg_app;

create or replace function knudg_enqueue_outbox_job(
  row_event_stream_position bigint,
  row_lane text,
  row_payload_json jsonb,
  row_payload_digest text,
  row_idempotency_key text,
  row_priority integer default 0,
  row_max_attempts integer default 3
)
returns table (
  outbox_event_id uuid,
  job_id uuid,
  event_stream_position bigint,
  lane text,
  status text
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_actor_role text;
  existing_outbox public.outbox_events%rowtype;
  new_outbox_id uuid;
  new_job_id uuid;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_lane is null or row_lane = '' then
    raise exception 'lane is required' using errcode = '23514';
  end if;
  if row_payload_json is null or jsonb_typeof(row_payload_json) <> 'object' then
    raise exception 'job payload must be a json object' using errcode = '23514';
  end if;
  if row_payload_digest is null or row_payload_digest = '' then
    raise exception 'payload digest is required' using errcode = '23514';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_max_attempts <= 0 then
    raise exception 'max attempts must be positive' using errcode = '23514';
  end if;
  if claim_actor_role like '%worker' and not knudg_private.current_worker_allows('enqueue_outbox_job') then
    raise exception 'worker is not allowed to enqueue outbox jobs' using errcode = '28000';
  end if;
  if not exists (
    select 1 from public.event_stream_positions esp
    where esp.tenant_id = claim_tenant_id
      and esp.event_stream_position = row_event_stream_position
  ) then
    raise exception 'event stream position not found for tenant' using errcode = '23503';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    'knudg:enqueue_outbox_job:' || claim_tenant_id::text || ':' ||
    row_lane || ':v1:' || row_idempotency_key,
    0
  ));

  select *
  into existing_outbox
  from public.outbox_events oe
  where oe.tenant_id = claim_tenant_id
    and oe.lane = row_lane
    and oe.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_outbox.event_stream_position <> row_event_stream_position
      or existing_outbox.payload_digest <> row_payload_digest then
      raise exception 'outbox idempotency key replayed with different request' using errcode = '23505';
    end if;
    outbox_event_id := existing_outbox.id;
    job_id := existing_outbox.job_id;
    event_stream_position := existing_outbox.event_stream_position;
    lane := existing_outbox.lane;
    status := existing_outbox.status;
    return next;
    return;
  end if;

  new_outbox_id := knudg_crypto.gen_random_uuid();
  new_job_id := knudg_crypto.gen_random_uuid();

  insert into public.outbox_events(
    tenant_id, id, event_stream_position, lane, status, payload_json,
    payload_digest, idempotency_key, job_id
  )
  values (
    claim_tenant_id, new_outbox_id, row_event_stream_position, row_lane,
    'job_enqueued', row_payload_json, row_payload_digest, row_idempotency_key,
    new_job_id
  );

  insert into public.jobs(
    tenant_id, id, lane, status, priority, payload_json, payload_digest,
    idempotency_key, outbox_event_id, max_attempts
  )
  values (
    claim_tenant_id, new_job_id, row_lane, 'ready', row_priority,
    row_payload_json, row_payload_digest, row_idempotency_key, new_outbox_id,
    row_max_attempts
  );

  outbox_event_id := new_outbox_id;
  job_id := new_job_id;
  event_stream_position := row_event_stream_position;
  lane := row_lane;
  status := 'job_enqueued';
  return next;
end;
$$;
revoke all on function knudg_enqueue_outbox_job(bigint, text, jsonb, text, text, integer, integer) from public;
grant execute on function knudg_enqueue_outbox_job(bigint, text, jsonb, text, text, integer, integer) to knudg_app, knudg_worker;

create or replace function knudg_claim_job(
  row_lane text,
  row_lease_seconds integer default 60
)
returns table (
  job_id uuid,
  lane text,
  attempt_number integer,
  payload_json jsonb,
  payload_digest text,
  lease_expires_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  claimed public.jobs%rowtype;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role not like '%worker' then
    raise exception 'claim_job requires worker actor role' using errcode = '28000';
  end if;
  if not knudg_private.current_worker_allows('claim_job') then
    raise exception 'worker is not allowed to claim jobs' using errcode = '28000';
  end if;
  if row_lease_seconds <= 0 or row_lease_seconds > 3600 then
    raise exception 'lease seconds out of range' using errcode = '23514';
  end if;

  update public.jobs j
  set status = 'leased',
      leased_by = claim_principal_id,
      lease_expires_at = now() + make_interval(secs => row_lease_seconds),
      attempts = attempts + 1,
      updated_at = now()
  where (j.tenant_id, j.id) in (
    select q.tenant_id, q.id
    from public.jobs q
    where q.tenant_id = claim_tenant_id
      and q.lane = row_lane
      and q.status = 'ready'
      and q.available_at <= now()
    order by q.priority desc, q.available_at, q.created_at
    for update skip locked
    limit 1
  )
  returning * into claimed;

  if not found then
    return;
  end if;

  insert into public.job_attempts(
    tenant_id, id, job_id, attempt_number, worker_id, worker_role, status
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), claimed.id, claimed.attempts,
    claim_principal_id, claim_actor_role, 'leased'
  );

  job_id := claimed.id;
  lane := claimed.lane;
  attempt_number := claimed.attempts;
  payload_json := claimed.payload_json;
  payload_digest := claimed.payload_digest;
  lease_expires_at := claimed.lease_expires_at;
  return next;
end;
$$;
revoke all on function knudg_claim_job(text, integer) from public;
grant execute on function knudg_claim_job(text, integer) to knudg_worker;

create or replace function knudg_claim_job_by_id(
  row_job_id uuid,
  row_lease_seconds integer default 60
)
returns table (
  job_id uuid,
  lane text,
  attempt_number integer,
  payload_json jsonb,
  payload_digest text,
  lease_expires_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  claimed public.jobs%rowtype;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if claim_actor_role not like '%worker' then
    raise exception 'claim_job requires worker actor role' using errcode = '28000';
  end if;
  if not knudg_private.current_worker_allows('claim_job') then
    raise exception 'worker is not allowed to claim jobs' using errcode = '28000';
  end if;
  if row_lease_seconds <= 0 or row_lease_seconds > 3600 then
    raise exception 'lease seconds out of range' using errcode = '23514';
  end if;

  update public.jobs j
  set status = 'leased',
      leased_by = claim_principal_id,
      lease_expires_at = now() + make_interval(secs => row_lease_seconds),
      attempts = attempts + 1,
      updated_at = now()
  where j.tenant_id = claim_tenant_id
    and j.id = row_job_id
    and j.status = 'ready'
    and j.available_at <= now()
  returning * into claimed;

  if not found then
    return;
  end if;

  insert into public.job_attempts(
    tenant_id, id, job_id, attempt_number, worker_id, worker_role, status
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), claimed.id, claimed.attempts,
    claim_principal_id, claim_actor_role, 'leased'
  );

  job_id := claimed.id;
  lane := claimed.lane;
  attempt_number := claimed.attempts;
  payload_json := claimed.payload_json;
  payload_digest := claimed.payload_digest;
  lease_expires_at := claimed.lease_expires_at;
  return next;
end;
$$;
revoke all on function knudg_claim_job_by_id(uuid, integer) from public;
grant execute on function knudg_claim_job_by_id(uuid, integer) to knudg_worker;

create or replace function knudg_complete_job(row_job_id uuid)
returns table (job_id uuid, status text)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  completed public.jobs%rowtype;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  if not knudg_private.current_worker_allows('complete_job') then
    raise exception 'worker is not allowed to complete jobs' using errcode = '28000';
  end if;

  update public.jobs j
  set status = 'succeeded',
      leased_by = null,
      lease_expires_at = null,
      completed_at = now(),
      updated_at = now()
  where j.tenant_id = claim_tenant_id
    and j.id = row_job_id
    and j.status = 'leased'
    and j.leased_by = claim_principal_id
    and j.lease_expires_at > now()
  returning * into completed;

  if not found then
    raise exception 'leased job not found for current worker' using errcode = '28000';
  end if;

  update public.job_attempts ja
  set status = 'succeeded', finished_at = now()
  where ja.tenant_id = claim_tenant_id
    and ja.job_id = row_job_id
    and ja.attempt_number = completed.attempts;

  update public.outbox_events oe
  set status = 'completed', updated_at = now()
  where oe.tenant_id = claim_tenant_id
    and oe.id = completed.outbox_event_id;

  job_id := completed.id;
  status := completed.status;
  return next;
end;
$$;
revoke all on function knudg_complete_job(uuid) from public;
grant execute on function knudg_complete_job(uuid) to knudg_worker;

create or replace function knudg_fail_job(
  row_job_id uuid,
  row_error_class text,
  row_sanitized_error_detail text,
  row_retry_delay_seconds integer default 60
)
returns table (job_id uuid, status text, attempts integer)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  current_job public.jobs%rowtype;
  next_status text;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  if not knudg_private.current_worker_allows('fail_job') then
    raise exception 'worker is not allowed to fail jobs' using errcode = '28000';
  end if;

  if row_error_class is null or row_error_class = '' then
    raise exception 'error class is required' using errcode = '23514';
  end if;
  if not knudg_private.audit_detail_is_sanitized(row_sanitized_error_detail) then
    raise exception 'job error detail is not sanitized' using errcode = '23514';
  end if;
  if row_retry_delay_seconds < 0 or row_retry_delay_seconds > 86400 then
    raise exception 'retry delay seconds out of range' using errcode = '23514';
  end if;

  select *
  into current_job
  from public.jobs j
  where j.tenant_id = claim_tenant_id
    and j.id = row_job_id
    and j.status = 'leased'
    and j.leased_by = claim_principal_id
    and j.lease_expires_at > now()
  for update;

  if not found then
    raise exception 'leased job not found for current worker' using errcode = '28000';
  end if;

  next_status := case when current_job.attempts >= current_job.max_attempts then 'dead' else 'ready' end;

  update public.jobs j
  set status = next_status,
      leased_by = null,
      lease_expires_at = null,
      available_at = case when next_status = 'ready' then now() + make_interval(secs => row_retry_delay_seconds) else j.available_at end,
      last_error_class = row_error_class,
      last_error_detail = row_sanitized_error_detail,
      updated_at = now()
  where j.tenant_id = claim_tenant_id and j.id = row_job_id;

  update public.job_attempts ja
  set status = case when next_status = 'dead' then 'dead' else 'retry_scheduled' end,
      error_class = row_error_class,
      sanitized_error_detail = row_sanitized_error_detail,
      finished_at = now()
  where ja.tenant_id = claim_tenant_id
    and ja.job_id = row_job_id
    and ja.attempt_number = current_job.attempts;

  if next_status = 'dead' then
    update public.outbox_events oe
    set status = 'dead', updated_at = now()
    where oe.tenant_id = claim_tenant_id and oe.id = current_job.outbox_event_id;
  end if;

  job_id := row_job_id;
  status := next_status;
  attempts := current_job.attempts;
  return next;
end;
$$;
revoke all on function knudg_fail_job(uuid, text, text, integer) from public;
grant execute on function knudg_fail_job(uuid, text, text, integer) to knudg_worker;

create or replace function knudg_revoke_consent_record(
  row_consent_id uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_reason text,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  consent_id uuid,
  revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  consent_row public.consent_records%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_revoked_at timestamptz;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_reason is null or row_reason = '' then
    raise exception 'termination reason is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;
  if claim_actor_role <> 'app_user' then
    raise exception 'revoke_consent_record requires app_user actor role' using errcode = '28000';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    'knudg:revoke_consent_record:' || claim_tenant_id::text || ':' || row_consent_id::text || ':v1:' || row_idempotency_key,
    0
  ));

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'revoke_consent_record'
    and ik.logical_object_type = 'consent_record'
    and ik.logical_object_id = row_consent_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select de.event_id, de.event_stream_position, cr.id, cr.revoked_at
    into event_id, event_stream_position, consent_id, revoked_at
    from public.domain_events de
    join public.consent_records cr
      on cr.tenant_id = de.tenant_id and cr.termination_domain_event_id = de.event_id
    where de.tenant_id = claim_tenant_id
      and de.event_id = existing_idempotency.effect_domain_event_id
      and cr.id = row_consent_id
      and cr.subject_id = claim_principal_id
      and (cr.namespace_id is null or cr.namespace_id = any(knudg_private.current_namespace_ids()));
    if not found then
      raise exception 'idempotent revoke_consent_record replay is not authorized' using errcode = '28000';
    end if;
    return next;
    return;
  end if;

  select *
  into consent_row
  from public.consent_records cr
  where cr.tenant_id = claim_tenant_id
    and cr.id = row_consent_id
    and cr.subject_id = claim_principal_id
    and (cr.namespace_id is null or cr.namespace_id = any(knudg_private.current_namespace_ids()))
  for update;

  if not found then
    raise exception 'consent record not found or not authorized' using errcode = '28000';
  end if;
  if consent_row.revoked_at is not null then
    raise exception 'consent record is already terminated' using errcode = '23514';
  end if;

  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);
  new_revoked_at := now();

  insert into public.domain_events(
    tenant_id, event_id, event_type, actor_id, actor_role, target_type, target_id,
    event_payload_schema_version, event_payload_json, event_payload_digest,
    correlation_id, idempotency_key, event_stream_position
  )
  values (
    claim_tenant_id, new_event_id, 'consent_terminated', claim_principal_id, claim_actor_role,
    'consent_record', row_consent_id, 1, row_event_payload_json, row_event_payload_digest,
    row_correlation_id, row_idempotency_key, new_position
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, domain_event_id)
  values (new_position, claim_tenant_id, 'domain', new_event_id);

  update public.consent_records
  set revoked_at = new_revoked_at,
      termination_reason = row_reason,
      terminated_by = claim_principal_id,
      termination_domain_event_id = new_event_id
  where tenant_id = claim_tenant_id and id = row_consent_id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_domain_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'revoke_consent_record', 'consent_record', row_consent_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'domain', new_event_id
  );

  insert into public.audit_events(
    tenant_id, id, actor_id, actor_role, action, target_type, target_id,
    reason_code, sanitized_detail, correlation_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), claim_principal_id, claim_actor_role,
    'revoke_consent_record', 'consent_record', row_consent_id,
    'user_requested_consent_termination', 'Terminated consent record through M0 consent command.', row_correlation_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  consent_id := row_consent_id;
  revoked_at := new_revoked_at;
  return next;
end;
$$;
revoke all on function knudg_revoke_consent_record(uuid, text, text, uuid, text, jsonb, text) from public;
grant execute on function knudg_revoke_consent_record(uuid, text, text, uuid, text, jsonb, text) to knudg_app;

create or replace function knudg_withdraw_publication_approval(
  row_card_id uuid,
  row_expected_current_version uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_reason text,
  row_event_payload_json jsonb default '{}'::jsonb,
  row_event_payload_digest text default 'sha256:event'
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  consent_id uuid,
  revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
declare
  claims jsonb;
  claim_tenant_id uuid;
  claim_principal_id uuid;
  claim_actor_role text;
  card_row public.experience_cards%rowtype;
  consent_row public.consent_records%rowtype;
  existing_idempotency public.idempotency_keys%rowtype;
  new_event_id uuid;
  new_position bigint;
  new_seq bigint;
  new_revoked_at timestamptz;
begin
  claims := knudg_private.current_claims_json();
  claim_tenant_id := (claims->>'tenant_id')::uuid;
  claim_principal_id := (claims->>'principal_id')::uuid;
  claim_actor_role := claims->>'actor_role';

  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_reason is null or row_reason = '' then
    raise exception 'withdrawal reason is required' using errcode = '23514';
  end if;
  if row_event_payload_json is null or jsonb_typeof(row_event_payload_json) <> 'object' then
    raise exception 'event payload must be a json object' using errcode = '23514';
  end if;
  if row_event_payload_digest is null or row_event_payload_digest = '' then
    raise exception 'event payload digest is required' using errcode = '23514';
  end if;
  if claim_actor_role <> 'app_user' then
    raise exception 'withdraw_publication_approval requires app_user actor role' using errcode = '28000';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    'knudg:withdraw_publication_approval:' || claim_tenant_id::text || ':' || row_card_id::text || ':v1:' || row_idempotency_key,
    0
  ));

  select *
  into existing_idempotency
  from public.idempotency_keys ik
  where ik.tenant_id = claim_tenant_id
    and ik.operation = 'withdraw_publication_approval'
    and ik.logical_object_type = 'card'
    and ik.logical_object_id = row_card_id
    and ik.operation_version = 1
    and ik.idempotency_key = row_idempotency_key
  for update;

  if found then
    if existing_idempotency.request_digest <> row_request_digest then
      raise exception 'idempotency key replayed with different request digest' using errcode = '23505';
    end if;
    select ce.event_id, ce.event_stream_position, ce.event_seq, ce.card_id, cr.id, cr.revoked_at
    into event_id, event_stream_position, event_seq, card_id, consent_id, revoked_at
    from public.card_events ce
    join public.experience_cards c on c.tenant_id = ce.tenant_id and c.id = ce.card_id
    join public.consent_records cr on cr.tenant_id = ce.tenant_id and cr.termination_card_event_id = ce.event_id
    where ce.tenant_id = claim_tenant_id
      and ce.event_id = existing_idempotency.effect_card_event_id
      and ce.card_id = row_card_id
      and c.namespace_id = any(knudg_private.current_namespace_ids())
      and cr.subject_id = claim_principal_id;
    if not found then
      raise exception 'idempotent withdraw_publication_approval replay is not authorized' using errcode = '28000';
    end if;
    return next;
    return;
  end if;

  select *
  into card_row
  from public.experience_cards c
  where c.tenant_id = claim_tenant_id
    and c.id = row_card_id
    and c.namespace_id = any(knudg_private.current_namespace_ids())
    and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, c.current_version_id)
  for update;

  if not found then
    raise exception 'card not found or not authorized' using errcode = '28000';
  end if;
  if card_row.current_version_id <> row_expected_current_version then
    raise exception 'stale expected current version' using errcode = '40001';
  end if;
  if card_row.status <> 'approved_for_publication' then
    raise exception 'card is not approved for publication' using errcode = '23514';
  end if;

  select *
  into consent_row
  from public.consent_records cr
  where cr.tenant_id = claim_tenant_id
    and cr.scope = 'public_publication'
    and cr.artifact_type = 'card_version'
    and cr.card_version_id = row_expected_current_version
    and cr.artifact_id = row_expected_current_version
    and cr.subject_id = claim_principal_id
    and cr.revoked_at is null
  for update;

  if not found then
    raise exception 'active public publication consent not found' using errcode = '23514';
  end if;

  select coalesce(max(ce.event_seq), 0) + 1
  into new_seq
  from public.card_events ce
  where ce.tenant_id = claim_tenant_id and ce.card_id = row_card_id;

  new_event_id := knudg_crypto.gen_random_uuid();
  new_position := nextval('public.event_stream_position_seq'::regclass);
  new_revoked_at := now();

  insert into public.card_events(
    tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
    actor_id, actor_role, previous_status, next_status, expected_current_version,
    correlation_id, idempotency_key, event_payload_schema_version,
    event_payload_json, event_payload_digest
  )
  values (
    claim_tenant_id, row_card_id, new_event_id, new_position, new_seq, 'approval_withdrawn',
    claim_principal_id, claim_actor_role, 'approved_for_publication', 'publication_withdrawn',
    row_expected_current_version, row_correlation_id, row_idempotency_key, 1,
    row_event_payload_json, row_event_payload_digest
  );

  insert into public.event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
  values (new_position, claim_tenant_id, 'card', new_event_id);

  update public.experience_cards
  set status = 'publication_withdrawn', updated_at = now()
  where tenant_id = claim_tenant_id and id = row_card_id;

  update public.consent_records
  set revoked_at = new_revoked_at,
      termination_reason = row_reason,
      terminated_by = claim_principal_id,
      termination_card_event_id = new_event_id
  where tenant_id = claim_tenant_id and id = consent_row.id;

  insert into public.idempotency_keys(
    tenant_id, id, operation, logical_object_type, logical_object_id,
    operation_version, idempotency_key, request_digest, response_digest,
    effect_event_source_type, effect_card_event_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), 'withdraw_publication_approval', 'card', row_card_id,
    1, row_idempotency_key, row_request_digest,
    'sha256:event:' || new_event_id::text, 'card', new_event_id
  );

  insert into public.audit_events(
    tenant_id, id, actor_id, actor_role, action, target_type, target_id,
    reason_code, sanitized_detail, correlation_id
  )
  values (
    claim_tenant_id, knudg_crypto.gen_random_uuid(), claim_principal_id, claim_actor_role,
    'withdraw_publication_approval', 'card', row_card_id,
    'user_requested_publication_withdrawal', 'Withdrew publication approval through M0 consent command.', row_correlation_id
  );

  event_id := new_event_id;
  event_stream_position := new_position;
  event_seq := new_seq;
  card_id := row_card_id;
  consent_id := consent_row.id;
  revoked_at := new_revoked_at;
  return next;
end;
$$;
revoke all on function knudg_withdraw_publication_approval(uuid, uuid, text, text, uuid, text, jsonb, text) from public;
grant execute on function knudg_withdraw_publication_approval(uuid, uuid, text, text, uuid, text, jsonb, text) to knudg_app;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'tenant_memberships','namespaces','namespace_grants','tenant_revocation_epochs',
    'break_glass_cases','verification_records','experience_cards','card_versions',
    'domain_events','card_events','card_edges','revocation_tombstones',
    'outbox_events','jobs','job_attempts',
    'approval_challenges','approval_handoffs','consent_records','idempotency_keys','audit_events'
  ] loop
    execute format('alter table %I enable row level security', table_name);
    execute format('alter table %I force row level security', table_name);
  end loop;
end
$$;

alter table tenants enable row level security;
alter table tenants force row level security;

drop policy if exists tenants_isolation on tenants;
create policy tenants_isolation on tenants
  for select to knudg_app, knudg_worker, knudg_readonly_ops
  using (id = knudg_private.current_tenant_id());

drop policy if exists namespaces_isolation on namespaces;
create policy namespaces_isolation on namespaces
  for all to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id() and id = any(knudg_private.current_namespace_ids()))
  with check (tenant_id = knudg_private.current_tenant_id() and id = any(knudg_private.current_namespace_ids()));

drop policy if exists experience_cards_isolation on experience_cards;
create policy experience_cards_isolation on experience_cards
  for all to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and namespace_id = any(knudg_private.current_namespace_ids())
    and knudg_private.card_not_revoked(tenant_id, namespace_id, id, current_version_id)
  )
  with check (tenant_id = knudg_private.current_tenant_id() and namespace_id = any(knudg_private.current_namespace_ids()));

drop policy if exists tenant_rows_isolation on tenant_memberships;
create policy tenant_rows_isolation on tenant_memberships
  for all to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id())
  with check (tenant_id = knudg_private.current_tenant_id());

drop policy if exists namespace_grants_isolation on namespace_grants;
create policy namespace_grants_isolation on namespace_grants
  for all to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id())
  with check (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_readonly on card_versions;
create policy tenant_scoped_readonly on card_versions
  for select to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = card_versions.tenant_id
        and c.id = card_versions.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
        and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, card_versions.id)
    )
  );

drop policy if exists event_readonly on card_events;
create policy event_readonly on card_events
  for select to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = card_events.tenant_id
        and c.id = card_events.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
        and knudg_private.card_event_visible_not_revoked(
          c.tenant_id, c.namespace_id, c.id, c.current_version_id, card_events.expected_current_version
        )
    )
  );
drop policy if exists domain_event_readonly on domain_events;
create policy domain_event_readonly on domain_events
  for select to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_readonly on outbox_events;
create policy tenant_scoped_readonly on outbox_events
  for select to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_readonly on jobs;
create policy tenant_scoped_readonly on jobs
  for select to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_readonly on job_attempts;
create policy tenant_scoped_readonly on job_attempts
  for select to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_all on consent_records;
create policy tenant_scoped_all on consent_records
  for all to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and (
      namespace_id is null
      or namespace_id = any(knudg_private.current_namespace_ids())
    )
    and knudg_private.approval_artifact_not_revoked(
      tenant_id, namespace_id, artifact_type, artifact_id, card_version_id
    )
  )
  with check (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_all on approval_challenges;
create policy tenant_scoped_all on approval_challenges
  for all to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and namespace_id = any(knudg_private.current_namespace_ids())
    and knudg_private.approval_artifact_not_revoked(
      tenant_id, namespace_id, artifact_type, artifact_id, card_version_id
    )
  )
  with check (tenant_id = knudg_private.current_tenant_id());

drop policy if exists tenant_scoped_all on approval_handoffs;
create policy tenant_scoped_all on approval_handoffs
  for all to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and namespace_id = any(knudg_private.current_namespace_ids())
    and knudg_private.approval_artifact_not_revoked(
      tenant_id, namespace_id, artifact_type, artifact_id, card_version_id
    )
  )
  with check (tenant_id = knudg_private.current_tenant_id());

drop policy if exists idempotency_keys_readonly on idempotency_keys;
drop policy if exists tenant_scoped_all on idempotency_keys;
create policy idempotency_keys_readonly on idempotency_keys
  for select to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id())
  ;

drop policy if exists tenant_scoped_insert_select on audit_events;
create policy tenant_scoped_insert_select on audit_events
  for select to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id());
create policy tenant_scoped_audit_insert on audit_events
  for insert to knudg_app, knudg_worker
  with check (tenant_id = knudg_private.current_tenant_id());

grant select on tenants, principals, external_identities to knudg_app, knudg_worker, knudg_readonly_ops;
grant select on card_statuses, card_event_types, domain_event_types, actor_roles, outcome_types,
  quality_states, verification_statuses, evidence_strengths, namespace_visibilities,
  revocation_subject_types, consent_scopes, artifact_types, card_edge_types
  to knudg_app, knudg_worker, knudg_readonly_ops;
grant select on tenant_memberships, namespaces, namespace_grants, experience_cards,
  approval_challenges, approval_handoffs, consent_records, idempotency_keys, audit_events,
  outbox_events, jobs, job_attempts
  to knudg_app, knudg_worker;
revoke select on domain_events from knudg_app, knudg_worker;
grant select on card_versions, card_events, revocation_tombstones to knudg_app, knudg_worker;
grant select on event_stream_positions to knudg_readonly_ops;

insert into card_state_transitions(from_status, to_status, event_type, actor_role)
values
  ('candidate_created','pending_admission','admission_accepted','ingestion_worker'),
  ('pending_admission','deferred','admission_deferred','ingestion_worker'),
  ('deferred','pending_admission','admission_accepted','ingestion_worker'),
  ('discard_pending','pending_review','discard_restored','app_user'),
  ('pending_admission','pending_redaction','redaction_requested','ingestion_worker'),
  ('pending_redaction','pending_review','redaction_completed','redaction_worker'),
  ('pending_review','awaiting_user_approval','user_approval_requested','review_worker'),
  ('awaiting_user_approval','pending_redaction','approval_digest_invalidated','app_user'),
  ('awaiting_user_approval','pending_redaction','approval_digest_invalidated','review_worker'),
  ('awaiting_user_approval','approved_private','private_approved','app_user'),
  ('awaiting_user_approval','approved_for_publication','publication_approved','app_user'),
  ('approved_for_publication','publication_withdrawn','approval_withdrawn','app_user'),
  ('publication_withdrawn','awaiting_user_approval','user_approval_requested','app_user'),
  ('approved_for_publication','rejected','reviewer_rejected_after_approval','reviewer'),
  ('approved_for_publication','pending_redaction','reviewer_requested_reredaction','reviewer'),
  ('approved_for_publication','published','reviewer_published','reviewer'),
  ('published','indexed_hot','hot_indexed','index_worker'),
  ('indexed_hot','indexed_main','main_indexed','index_worker')
on conflict do nothing;

insert into card_state_transitions(from_status, to_status, event_type, actor_role)
select status, 'rejected', 'rejected', 'review_worker'
from unnest(array['candidate_created','pending_admission','deferred','pending_redaction','pending_review','awaiting_user_approval']) as status
on conflict do nothing;
insert into card_state_transitions(from_status, to_status, event_type, actor_role)
select status, 'discard_pending', 'discard_requested', 'app_user'
from unnest(array['candidate_created','pending_admission','deferred','pending_redaction','pending_review','awaiting_user_approval']) as status
on conflict do nothing;
insert into card_state_transitions(from_status, to_status, event_type, actor_role)
select status, target, event_type, 'reviewer'
from unnest(array['published','indexed_hot','indexed_main']) as status,
     (values ('superseded','superseded'), ('deprecated','deprecated')) as transitions(target, event_type)
on conflict do nothing;
insert into card_state_transitions(from_status, to_status, event_type, actor_role)
select status, 'revoked', 'revoked', role
from unnest(array[
  'candidate_created','pending_admission','deferred','pending_redaction','pending_review',
  'awaiting_user_approval','approved_private','approved_for_publication','discard_pending',
  'publication_withdrawn','published','indexed_hot','indexed_main','rejected','superseded','deprecated'
]) as status,
unnest(array['app_user','break_glass_admin']) as role
on conflict do nothing;
insert into card_state_transitions(from_status, to_status, event_type, actor_role)
select status, status, 'version_created', role
from unnest(array[
  'candidate_created','pending_admission','deferred','pending_redaction','pending_review',
  'awaiting_user_approval','approved_private','approved_for_publication','discard_pending',
  'publication_withdrawn','published','indexed_hot','indexed_main','rejected','superseded','deprecated'
]) as status,
unnest(array['app_user','agent_delegated_user','ingestion_worker','redaction_worker']) as role
on conflict do nothing;
insert into card_state_transitions(from_status, to_status, event_type, actor_role)
values ('pending_review','pending_review','review_requested','review_worker')
on conflict do nothing;
insert into card_state_transitions(from_status, to_status, event_type, actor_role)
select status, status, 'dispute_recorded', 'review_worker'
from unnest(array['published','indexed_hot','indexed_main','superseded','deprecated']) as status
on conflict do nothing;
