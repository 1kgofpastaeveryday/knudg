create or replace function knudg_private.text_array_has_duplicates(row_values text[])
returns boolean
language sql
immutable
set search_path = pg_catalog, pg_temp
as $$
  select coalesce((
    select count(*) <> count(distinct item)
    from unnest(row_values) as item
  ), false);
$$;

create or replace function knudg_private.text_array_items_within_bounds(row_values text[], min_length integer, max_length integer)
returns boolean
language sql
immutable
set search_path = pg_catalog, pg_temp
as $$
  select coalesce((
    select bool_and(char_length(item) between min_length and max_length)
    from unnest(row_values) as item
  ), true);
$$;

create or replace function knudg_private.text_array_matches_none(row_values text[], pattern text)
returns boolean
language sql
immutable
set search_path = pg_catalog, pg_temp
as $$
  select coalesce((
    select bool_and(item !~* pattern)
    from unnest(row_values) as item
  ), true);
$$;

create table if not exists redacted_private_experience_records (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null,
  namespace_id uuid not null,
  created_by uuid not null references principals(id) on delete restrict,
  schema_version text not null default 'experience-storage-record-v0' check (schema_version = 'experience-storage-record-v0'),
  record_class text not null default 'redacted_private_experience_record' check (record_class = 'redacted_private_experience_record'),
  domain text not null references experience_domain_policies(domain) on delete restrict,
  subject_type text not null check (subject_type in ('company', 'place', 'service')),
  subject_public_name text not null check (
    char_length(subject_public_name) between 1 and 160
    and subject_public_name !~ '[@\\\\]'
    and subject_public_name !~* '(password|secret|token|api[_-]?key|credential|private[_ -]?key)'
  ),
  subject_aliases text[] not null default '{}'::text[] check (
    coalesce(array_length(subject_aliases, 1), 0) <= 8
    and not knudg_private.text_array_has_duplicates(subject_aliases)
    and knudg_private.text_array_items_within_bounds(subject_aliases, 1, 120)
    and knudg_private.text_array_matches_none(subject_aliases, '[@\\\\]')
    and knudg_private.text_array_matches_none(subject_aliases, '(password|secret|token|api[_-]?key|credential|private[_ -]?key)')
  ),
  entity_name_public_allowed boolean not null default true check (entity_name_public_allowed = true),
  private_person_ref_count integer not null default 0 check (private_person_ref_count = 0),
  title text not null check (
    char_length(title) between 8 and 120
    and title !~ '[@\\\\]'
    and title !~* '(password|secret|token|api[_-]?key|credential|private[_ -]?key)'
  ),
  summary text not null check (
    char_length(summary) between 20 and 600
    and summary !~ '[@\\\\]'
    and summary !~* '(https?://|localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0|20[0-9]{2}-[0-9]{2}-[0-9]{2})'
    and summary !~* '(20[0-9]{2}[/-][0-9]{1,2}[/-][0-9]{1,2}|20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日|[0-9]{1,2}:[0-9]{2}|0[0-9]{1,4}[- ][0-9]{1,4}[- ][0-9]{3,4})'
    and summary !~* '(password|secret|token|api[_-]?key|credential|private[_ -]?key)'
  ),
  observations text[] not null check (
    coalesce(array_length(observations, 1), 0) between 1 and 8
    and knudg_private.text_array_items_within_bounds(observations, 8, 240)
    and array_to_string(observations, ' ') !~ '[@\\\\]'
    and array_to_string(observations, ' ') !~* '(https?://|localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0|20[0-9]{2}-[0-9]{2}-[0-9]{2})'
    and array_to_string(observations, ' ') !~* '(20[0-9]{2}[/-][0-9]{1,2}[/-][0-9]{1,2}|20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日|[0-9]{1,2}:[0-9]{2}|0[0-9]{1,4}[- ][0-9]{1,4}[- ][0-9]{3,4})'
    and array_to_string(observations, ' ') !~* '(password|secret|token|api[_-]?key|credential|private[_ -]?key)'
  ),
  subjective_impressions text[] not null default '{}'::text[] check (
    coalesce(array_length(subjective_impressions, 1), 0) <= 8
    and knudg_private.text_array_items_within_bounds(subjective_impressions, 8, 240)
    and array_to_string(subjective_impressions, ' ') !~ '[@\\\\]'
    and array_to_string(subjective_impressions, ' ') !~* '(https?://|localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0|20[0-9]{2}-[0-9]{2}-[0-9]{2})'
    and array_to_string(subjective_impressions, ' ') !~* '(20[0-9]{2}[/-][0-9]{1,2}[/-][0-9]{1,2}|20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日|[0-9]{1,2}:[0-9]{2}|0[0-9]{1,4}[- ][0-9]{1,4}[- ][0-9]{3,4})'
    and array_to_string(subjective_impressions, ' ') !~* '(password|secret|token|api[_-]?key|credential|private[_ -]?key)'
  ),
  disallowed_detail_classes text[] not null check (
    not knudg_private.text_array_has_duplicates(disallowed_detail_classes)
    and disallowed_detail_classes <@ array[
      'selection_status',
      'private_message',
      'private_person_identity',
      'exact_timestamp',
      'raw_source_material',
      'protected_identity_signal',
      'device_or_network_signal'
    ]::text[]
    and disallowed_detail_classes @> array[
      'selection_status',
      'private_message',
      'private_person_identity',
      'exact_timestamp',
      'raw_source_material',
      'protected_identity_signal',
      'device_or_network_signal'
    ]::text[]
  ),
  private_selection_status_present boolean not null default false check (private_selection_status_present = false),
  raw_quotes_present boolean not null default false check (raw_quotes_present = false),
  exact_dates_present boolean not null default false check (exact_dates_present = false),
  private_person_present boolean not null default false check (private_person_present = false),
  capture_notice_shown boolean not null default true check (capture_notice_shown = true),
  revocation_supported boolean not null default true check (revocation_supported = true),
  private_retention_consent_id uuid not null,
  private_retention_handoff_id uuid not null,
  private_retention_challenge_id uuid not null,
  consented_card_id uuid not null,
  consented_card_version_id uuid not null,
  consented_artifact_digest text not null check (consented_artifact_digest ~ '^(sha256:)?[a-f0-9]{64}$'),
  consent_policy_version text not null check (consent_policy_version <> ''),
  consent_policy_digest text not null check (consent_policy_digest ~ '^sha256:[a-f0-9]{64}$'),
  consent_challenge_digest text not null check (consent_challenge_digest ~ '^sha256:[a-f0-9]{64}$'),
  consent_handoff_digest text not null check (consent_handoff_digest ~ '^sha256:[a-f0-9]{64}$'),
  consent_granted_at timestamptz not null,
  consent_grant_card_event_id uuid not null,
  publication_consent boolean not null default false check (publication_consent = false),
  b2b_contact_consent boolean not null default false check (b2b_contact_consent = false),
  dashboard_aggregation_consent boolean not null default false check (dashboard_aggregation_consent = false),
  raw_source_retention text not null default 'none' check (raw_source_retention = 'none'),
  raw_detail_escrow_ref uuid null check (raw_detail_escrow_ref is null),
  raw_source_available_to_model boolean not null default false check (raw_source_available_to_model = false),
  source_digest text not null check (source_digest ~ '^sha256:[a-f0-9]{64}$'),
  redaction_digest text not null check (redaction_digest ~ '^sha256:[a-f0-9]{64}$'),
  payload_digest text not null check (payload_digest ~ '^sha256:[a-f0-9]{64}$'),
  lifecycle_status text not null default 'captured' check (lifecycle_status in ('captured', 'revoked', 'purged')),
  revoked_at timestamptz null,
  purged_at timestamptz null,
  revocation_reason_digest text null check (revocation_reason_digest is null or revocation_reason_digest ~ '^[a-f0-9]{64}$'),
  purge_reason_digest text null check (purge_reason_digest is null or purge_reason_digest ~ '^[a-f0-9]{64}$'),
  retrieval_policy text not null default 'explicit_or_contextual' check (retrieval_policy = 'explicit_or_contextual'),
  database_write_enabled boolean not null default true check (database_write_enabled = true),
  record_visible_to_retrieval boolean not null default false check (record_visible_to_retrieval = false),
  public_candidate_conversion_enabled boolean not null default false check (public_candidate_conversion_enabled = false),
  public_serving_enabled boolean not null default false check (public_serving_enabled = false),
  b2b_delivery_enabled boolean not null default false check (b2b_delivery_enabled = false),
  identity_processing_enabled boolean not null default false check (identity_processing_enabled = false),
  raw_detail_escrow_enabled boolean not null default false check (raw_detail_escrow_enabled = false),
  dashboard_enabled boolean not null default false check (dashboard_enabled = false),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, id),
  foreign key (tenant_id, namespace_id) references namespaces(tenant_id, id) on delete restrict,
  foreign key (tenant_id, private_retention_consent_id) references consent_records(tenant_id, id) on delete restrict,
  foreign key (tenant_id, private_retention_handoff_id) references approval_handoffs(tenant_id, id) on delete restrict,
  foreign key (tenant_id, private_retention_challenge_id) references approval_challenges(tenant_id, id) on delete restrict,
  foreign key (tenant_id, consented_card_id, consented_card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  foreign key (tenant_id, consent_grant_card_event_id) references card_events(tenant_id, event_id) on delete restrict,
  check (domain in ('career_private', 'place_service_experience')),
  check (
    (domain = 'career_private' and subject_type = 'company')
    or (domain = 'place_service_experience' and subject_type in ('place', 'service'))
  ),
  check (
    (lifecycle_status = 'captured' and revoked_at is null and purged_at is null)
    or (lifecycle_status = 'revoked' and revoked_at is not null and purged_at is null)
    or (lifecycle_status = 'purged' and purged_at is not null)
  ),
  check (
    regexp_replace(source_digest, '^sha256:', '') = regexp_replace(consented_artifact_digest, '^sha256:', '')
  )
);

create index if not exists redacted_private_experience_consent_idx
  on redacted_private_experience_records(tenant_id, private_retention_consent_id, private_retention_handoff_id);

create or replace function knudg_private.enforce_redacted_private_experience_consent_binding()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
begin
  if not exists (
    select 1
    from consent_records cr
    join approval_challenges ac
      on ac.tenant_id = cr.tenant_id
     and ac.id = cr.challenge_id
    join approval_handoffs ah
      on ah.tenant_id = cr.tenant_id
     and ah.challenge_id = cr.challenge_id
    join card_versions cv
      on cv.tenant_id = cr.tenant_id
     and cv.id = cr.card_version_id
     and cv.card_id = new.consented_card_id
    where cr.tenant_id = new.tenant_id
      and cr.id = new.private_retention_consent_id
      and cr.scope = 'private_retention'
      and cr.artifact_type = 'card_version'
      and cr.subject_id = new.created_by
      and cr.namespace_id = new.namespace_id
      and cr.revoked_at is null
      and (cr.expires_at is null or cr.expires_at > now())
      and cr.challenge_id = new.private_retention_challenge_id
      and cr.artifact_id = new.consented_card_version_id
      and cr.card_version_id = new.consented_card_version_id
      and cr.artifact_digest = new.consented_artifact_digest
      and cr.policy_version = new.consent_policy_version
      and cr.policy_digest = new.consent_policy_digest
      and cr.challenge_digest = new.consent_challenge_digest
      and cr.grant_card_event_id = new.consent_grant_card_event_id
      and cr.granted_at = new.consent_granted_at
      and ac.used_by_consent_id = cr.id
      and ac.subject_id = cr.subject_id
      and ac.namespace_id = cr.namespace_id
      and ac.consent_scope = cr.scope
      and ac.artifact_type = cr.artifact_type
      and ac.artifact_id = cr.artifact_id
      and ac.card_version_id = cr.card_version_id
      and ac.artifact_digest = cr.artifact_digest
      and ac.policy_version = cr.policy_version
      and ac.policy_digest = cr.policy_digest
      and ac.challenge_digest = cr.challenge_digest
      and ah.id = new.private_retention_handoff_id
      and ah.subject_id = cr.subject_id
      and ah.namespace_id = cr.namespace_id
      and ah.consent_scope = cr.scope
      and ah.artifact_type = cr.artifact_type
      and ah.artifact_id = cr.artifact_id
      and ah.card_version_id = cr.card_version_id
      and ah.artifact_digest = cr.artifact_digest
      and ah.policy_version = cr.policy_version
      and ah.policy_digest = cr.policy_digest
      and ah.challenge_digest = cr.challenge_digest
      and ah.handoff_digest = new.consent_handoff_digest
      and cv.payload_digest = cr.artifact_digest
      and regexp_replace(new.source_digest, '^sha256:', '') = regexp_replace(cr.artifact_digest, '^sha256:', '')
  ) then
    raise exception 'redacted private experience record consent proof is invalid' using errcode = '23514';
  end if;
  return new;
end;
$$;

drop trigger if exists redacted_private_experience_consent_binding on redacted_private_experience_records;
create trigger redacted_private_experience_consent_binding
before insert or update of private_retention_consent_id, private_retention_handoff_id,
  private_retention_challenge_id, consented_card_id, consented_card_version_id,
  consented_artifact_digest, consent_policy_version, consent_policy_digest,
  consent_challenge_digest, consent_handoff_digest, consent_granted_at,
  consent_grant_card_event_id
on redacted_private_experience_records
for each row execute function knudg_private.enforce_redacted_private_experience_consent_binding();

alter table redacted_private_experience_records enable row level security;
alter table redacted_private_experience_records force row level security;

drop policy if exists redacted_private_experience_records_isolation on redacted_private_experience_records;
create policy redacted_private_experience_records_isolation on redacted_private_experience_records
  for select to knudg_readonly_ops
  using (false);

grant select on redacted_private_experience_records to knudg_readonly_ops;

create or replace function knudg_closed_api_store_redacted_experience(
  row_workspace_id text,
  row_record_json jsonb
)
returns table (
  tenant_id uuid,
  namespace_id uuid,
  principal_id uuid,
  record_id uuid,
  private_retention_consent_id uuid,
  private_retention_handoff_id uuid,
  domain text,
  subject_type text,
  subject_public_name text,
  payload_digest text,
  record_visible_to_retrieval boolean,
  public_candidate_conversion_enabled boolean,
  public_serving_enabled boolean,
  b2b_delivery_enabled boolean,
  identity_processing_enabled boolean,
  raw_detail_escrow_enabled boolean,
  dashboard_enabled boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
  consent_proof jsonb;
  consent_row record;
  new_record_id uuid;
  new_payload_digest text;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;
  if jsonb_typeof(row_record_json) <> 'object' then
    raise exception 'record must be a json object' using errcode = '23514';
  end if;
  if row_record_json->>'schema_version' <> 'experience-storage-record-v0'
    or row_record_json->>'record_class' <> 'redacted_private_experience_record'
    or row_record_json #>> '{storage_state,mode}' <> 'stored_private_redacted'
    or row_record_json #>> '{storage_state,activation_required}' <> 'false'
    or row_record_json #>> '{storage_state,database_write_enabled}' <> 'true'
    or row_record_json #>> '{storage_state,record_visible_to_retrieval}' <> 'false'
    or coalesce(jsonb_typeof(row_record_json #> '{consent,private_retention_consent_proof}'), '') <> 'object'
    or row_record_json #>> '{source_controls,raw_source_retention}' <> 'none'
    or row_record_json #>> '{source_controls,raw_source_available_to_model}' <> 'false'
    or row_record_json #>> '{surface_controls,public_candidate_conversion_enabled}' <> 'false'
    or row_record_json #>> '{surface_controls,public_serving_enabled}' <> 'false'
    or row_record_json #>> '{surface_controls,b2b_delivery_enabled}' <> 'false'
    or row_record_json #>> '{surface_controls,identity_processing_enabled}' <> 'false'
    or row_record_json #>> '{surface_controls,raw_detail_escrow_enabled}' <> 'false'
    or row_record_json #>> '{surface_controls,dashboard_enabled}' <> 'false' then
    raise exception 'redacted experience record is not private-storage eligible' using errcode = '23514';
  end if;
  if row_record_json #> '{source_controls,raw_detail_escrow_ref}' <> 'null'::jsonb then
    raise exception 'raw escrow refs are not allowed' using errcode = '23514';
  end if;
  consent_proof := row_record_json #> '{consent,private_retention_consent_proof}';

  insert into tenants(id, slug, name)
  values (binding.tenant_id, binding.tenant_slug, 'Knudg Closed Private')
  on conflict (id) do update set slug = excluded.slug;

  insert into principals(id, principal_type, display_name)
  values (binding.principal_id, 'human_user', 'Closed Launch Operator')
  on conflict (id) do update set display_name = excluded.display_name;

  insert into tenant_memberships(tenant_id, id, principal_id, membership_role, status, valid_from)
  values (binding.tenant_id, knudg_crypto.gen_random_uuid(), binding.principal_id, 'member', 'active', now() - interval '1 minute')
  on conflict do nothing;

  insert into namespaces(tenant_id, id, key, name, visibility)
  values (binding.tenant_id, binding.namespace_id, binding.namespace_key, 'Closed Private', 'private')
  on conflict on constraint namespaces_pkey do update set key = excluded.key;

  insert into namespace_grants(tenant_id, id, namespace_id, principal_id, grant_scope, status, valid_from)
  select binding.tenant_id, knudg_crypto.gen_random_uuid(), binding.namespace_id, binding.principal_id, scope, 'active', now() - interval '1 minute'
  from unnest(array['submit','read','admin']) as scope
  on conflict do nothing;

  new_record_id := knudg_crypto.gen_random_uuid();
  new_payload_digest := 'sha256:' || encode(knudg_crypto.digest(knudg_private.canonical_jsonb(row_record_json), 'sha256'), 'hex');

  select cr.id as consent_id, ah.id as handoff_id, cr.challenge_id,
    cv.card_id, cr.card_version_id, cr.artifact_digest, cr.policy_version,
    cr.policy_digest, cr.challenge_digest, ah.handoff_digest,
    cr.granted_at, cr.grant_card_event_id
  into consent_row
  from consent_records cr
  join approval_challenges ac
    on ac.tenant_id = cr.tenant_id
   and ac.id = cr.challenge_id
  join approval_handoffs ah
    on ah.tenant_id = cr.tenant_id
   and ah.challenge_id = cr.challenge_id
  join card_versions cv
    on cv.tenant_id = cr.tenant_id
   and cv.id = cr.card_version_id
  where cr.tenant_id = binding.tenant_id
    and cr.id = (consent_proof->>'consent_id')::uuid
    and ah.id = (consent_proof->>'handoff_id')::uuid
    and cr.scope = 'private_retention'
    and cr.artifact_type = 'card_version'
    and cr.subject_id = binding.principal_id
    and cr.namespace_id = binding.namespace_id
    and cr.revoked_at is null
    and (cr.expires_at is null or cr.expires_at > now())
    and cr.challenge_id = (consent_proof->>'challenge_id')::uuid
    and cr.artifact_id = cr.card_version_id
    and cr.card_version_id = (consent_proof->>'card_version_id')::uuid
    and cv.card_id = (consent_proof->>'card_id')::uuid
    and cr.artifact_digest = consent_proof->>'artifact_digest'
    and cr.policy_version = consent_proof->>'policy_version'
    and cr.policy_digest = consent_proof->>'policy_digest'
    and cr.challenge_digest = consent_proof->>'challenge_digest'
    and ah.handoff_digest = consent_proof->>'handoff_digest'
    and regexp_replace(row_record_json #>> '{source_controls,source_digest}', '^sha256:', '') = regexp_replace(cr.artifact_digest, '^sha256:', '')
    and ac.used_by_consent_id = cr.id
    and ac.subject_id = cr.subject_id
    and ac.namespace_id = cr.namespace_id
    and ac.consent_scope = cr.scope
    and ac.artifact_type = cr.artifact_type
    and ac.artifact_id = cr.artifact_id
    and ac.card_version_id = cr.card_version_id
    and ac.artifact_digest = cr.artifact_digest
    and ac.policy_version = cr.policy_version
    and ac.policy_digest = cr.policy_digest
    and ac.challenge_digest = cr.challenge_digest
    and ah.subject_id = cr.subject_id
    and ah.namespace_id = cr.namespace_id
    and ah.consent_scope = cr.scope
    and ah.artifact_type = cr.artifact_type
    and ah.artifact_id = cr.artifact_id
    and ah.card_version_id = cr.card_version_id
    and ah.artifact_digest = cr.artifact_digest
    and ah.policy_version = cr.policy_version
    and ah.policy_digest = cr.policy_digest
    and ah.challenge_digest = cr.challenge_digest
    and cv.payload_digest = cr.artifact_digest
    and cr.grant_card_event_id is not null;
  if not found then
    raise exception 'private retention consent proof is not active for this workspace' using errcode = '23514';
  end if;

  insert into redacted_private_experience_records(
    tenant_id, id, namespace_id, created_by, domain, subject_type,
    subject_public_name, subject_aliases, title, summary, observations, subjective_impressions,
    disallowed_detail_classes, private_retention_consent_id, private_retention_handoff_id,
    private_retention_challenge_id, consented_card_id, consented_card_version_id,
    consented_artifact_digest, consent_policy_version, consent_policy_digest,
    consent_challenge_digest, consent_handoff_digest, consent_granted_at,
    consent_grant_card_event_id, source_digest, redaction_digest, payload_digest,
    retrieval_policy, database_write_enabled, record_visible_to_retrieval,
    public_candidate_conversion_enabled, public_serving_enabled,
    b2b_delivery_enabled, identity_processing_enabled,
    raw_detail_escrow_enabled, dashboard_enabled
  )
  values (
    binding.tenant_id, new_record_id, binding.namespace_id, binding.principal_id,
    row_record_json->>'domain',
    row_record_json #>> '{subject,type}',
    row_record_json #>> '{subject,public_name}',
    coalesce(array(select jsonb_array_elements_text(row_record_json #> '{subject,aliases}')), '{}'::text[]),
    row_record_json #>> '{redacted_experience,title}',
    row_record_json #>> '{redacted_experience,summary}',
    array(select jsonb_array_elements_text(row_record_json #> '{redacted_experience,observations}')),
    coalesce(array(select jsonb_array_elements_text(row_record_json #> '{redacted_experience,subjective_impressions}')), '{}'::text[]),
    array(select jsonb_array_elements_text(row_record_json #> '{redacted_experience,disallowed_detail_classes}')),
    consent_row.consent_id,
    consent_row.handoff_id,
    consent_row.challenge_id,
    consent_row.card_id,
    consent_row.card_version_id,
    consent_row.artifact_digest,
    consent_row.policy_version,
    consent_row.policy_digest,
    consent_row.challenge_digest,
    consent_row.handoff_digest,
    consent_row.granted_at,
    consent_row.grant_card_event_id,
    row_record_json #>> '{source_controls,source_digest}',
    row_record_json #>> '{audit,redaction_digest}',
    new_payload_digest,
    row_record_json #>> '{surface_controls,retrieval_policy}',
    true,
    false,
    false,
    false,
    false,
    false,
    false,
    false
  );

  tenant_id := binding.tenant_id;
  namespace_id := binding.namespace_id;
  principal_id := binding.principal_id;
  record_id := new_record_id;
  private_retention_consent_id := consent_row.consent_id;
  private_retention_handoff_id := consent_row.handoff_id;
  domain := row_record_json->>'domain';
  subject_type := row_record_json #>> '{subject,type}';
  subject_public_name := row_record_json #>> '{subject,public_name}';
  payload_digest := new_payload_digest;
  record_visible_to_retrieval := false;
  public_candidate_conversion_enabled := false;
  public_serving_enabled := false;
  b2b_delivery_enabled := false;
  identity_processing_enabled := false;
  raw_detail_escrow_enabled := false;
  dashboard_enabled := false;
  return next;
end;
$$;

revoke all on function knudg_closed_api_store_redacted_experience(text, jsonb) from public;
grant execute on function knudg_closed_api_store_redacted_experience(text, jsonb) to knudg_api_app;

create or replace function knudg_closed_api_complete_private_retention(
  row_workspace_id text,
  row_handoff_id uuid,
  row_idempotency_key text,
  row_request_digest text,
  row_correlation_id uuid,
  row_artifact_digest text,
  row_challenge_digest text,
  row_handoff_digest text,
  row_comprehension_confirmed boolean,
  row_private_retention_scope_confirmed boolean,
  row_no_publication_confirmed boolean
)
returns table (
  event_id uuid,
  event_stream_position bigint,
  event_seq bigint,
  card_id uuid,
  consent_id uuid,
  previous_status text,
  next_status text,
  current_version_id uuid,
  challenge_id uuid,
  handoff_id uuid
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
  handoff record;
  request_id uuid;
  event_payload jsonb;
  event_payload_digest text;
  approved record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;
  if row_handoff_id is null then
    raise exception 'handoff id is required' using errcode = '23514';
  end if;
  if row_idempotency_key is null or row_idempotency_key = '' then
    raise exception 'idempotency key is required' using errcode = '23514';
  end if;
  if row_request_digest is null or row_request_digest = '' then
    raise exception 'request digest is required' using errcode = '23514';
  end if;
  if row_artifact_digest is null or row_artifact_digest !~ '^(sha256:)?[a-f0-9]{64}$'
    or row_challenge_digest is null or row_challenge_digest !~ '^sha256:[a-f0-9]{64}$'
    or row_handoff_digest is null or row_handoff_digest !~ '^sha256:[a-f0-9]{64}$' then
    raise exception 'approval handoff proof digests are required' using errcode = '23514';
  end if;
  if row_comprehension_confirmed is not true
    or row_private_retention_scope_confirmed is not true
    or row_no_publication_confirmed is not true then
    raise exception 'private retention completion confirmations are required' using errcode = '23514';
  end if;

  select ah.tenant_id, ah.id as handoff_id, ah.challenge_id, ah.subject_id,
    ah.namespace_id, ah.consent_scope, ah.artifact_type, ah.artifact_id,
    ah.card_version_id, ah.artifact_digest, ah.policy_version, ah.policy_digest,
    ah.challenge_digest, ah.handoff_digest, ah.expires_at, ah.invalidated_at,
    ac.used_by_consent_id, ac.invalidated_at as challenge_invalidated_at,
    ac.expires_at as challenge_expires_at, cv.card_id, cv.payload_digest,
    c.status as card_status, c.current_version_id
  into handoff
  from approval_handoffs ah
  join approval_challenges ac on ac.tenant_id = ah.tenant_id and ac.id = ah.challenge_id
  join card_versions cv on cv.tenant_id = ah.tenant_id and cv.id = ah.card_version_id
  join experience_cards c on c.tenant_id = cv.tenant_id and c.id = cv.card_id
  where ah.tenant_id = binding.tenant_id
    and ah.id = row_handoff_id
  for update;

  if not found then
    raise exception 'approval handoff not found or not authorized' using errcode = '28000';
  end if;
  if handoff.subject_id <> binding.principal_id
    or handoff.namespace_id <> binding.namespace_id
    or handoff.consent_scope <> 'private_retention'
    or handoff.artifact_type <> 'card_version'
    or handoff.artifact_id <> handoff.card_version_id
    or handoff.artifact_digest <> handoff.payload_digest
    or handoff.artifact_digest <> row_artifact_digest
    or handoff.challenge_digest <> row_challenge_digest
    or handoff.handoff_digest <> row_handoff_digest
    or handoff.card_version_id <> handoff.current_version_id
    or handoff.invalidated_at is not null
    or handoff.expires_at <= now()
    or handoff.challenge_invalidated_at is not null
    or handoff.challenge_expires_at <= now()
    or handoff.used_by_consent_id is not null then
    raise exception 'approval handoff is not active for private retention completion' using errcode = '23514';
  end if;

  request_id := coalesce(row_correlation_id, knudg_crypto.gen_random_uuid());
  insert into request_claim_contexts(
    backend_pid, transaction_id, request_id, claims_digest, principal_id,
    tenant_id, actor_role, namespace_ids, grant_snapshot_version, expires_at
  )
  values (
    pg_backend_pid(), pg_current_xact_id(), request_id,
    encode(knudg_crypto.digest(convert_to(binding.tenant_id::text || ':' || binding.principal_id::text || ':' || row_handoff_id::text, 'UTF8'), 'sha256'), 'hex'),
    binding.principal_id, binding.tenant_id, 'app_user', array[binding.namespace_id]::uuid[], 1, now() + interval '5 minutes'
  )
  on conflict (backend_pid, transaction_id, request_id) do update
  set principal_id = excluded.principal_id,
      tenant_id = excluded.tenant_id,
      actor_role = excluded.actor_role,
      namespace_ids = excluded.namespace_ids,
      expires_at = excluded.expires_at,
      created_at = now();
  perform set_config('knudg.trusted_request_id', request_id::text, true);

  event_payload := jsonb_build_object(
    'source', 'closed_api_private_retention_completion',
    'handoff_id', row_handoff_id,
    'workspace_id', row_workspace_id,
    'comprehension_confirmed', true,
    'private_retention_scope_confirmed', true,
    'no_publication_confirmed', true,
    'public_publication_enabled', false,
    'team_sharing_enabled', false
  );
  event_payload_digest := 'sha256:' || encode(knudg_crypto.digest(knudg_private.canonical_jsonb(event_payload), 'sha256'), 'hex');

  select *
  into approved
  from knudg_approve_private_retention(
    handoff.card_id,
    handoff.challenge_id,
    row_idempotency_key,
    row_request_digest,
    request_id,
    event_payload,
    event_payload_digest
  );

  event_id := approved.event_id;
  event_stream_position := approved.event_stream_position;
  event_seq := approved.event_seq;
  card_id := approved.card_id;
  consent_id := approved.consent_id;
  previous_status := approved.previous_status;
  next_status := approved.next_status;
  current_version_id := approved.current_version_id;
  challenge_id := handoff.challenge_id;
  handoff_id := row_handoff_id;
  return next;
end;
$$;

revoke all on function knudg_closed_api_complete_private_retention(text, uuid, text, text, uuid, text, text, text, boolean, boolean, boolean) from public;
grant execute on function knudg_closed_api_complete_private_retention(text, uuid, text, text, uuid, text, text, text, boolean, boolean, boolean) to knudg_api_app;

create or replace function knudg_closed_api_revoke_redacted_experience(
  row_workspace_id text,
  row_record_id uuid,
  row_reason_digest text
)
returns table (
  record_id uuid,
  lifecycle_status text,
  revoked boolean,
  protected_data_serving_enabled boolean,
  publication_enabled boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
  updated record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;
  if row_record_id is null then
    raise exception 'record id is required' using errcode = '23514';
  end if;
  if row_reason_digest is null or row_reason_digest !~ '^[a-f0-9]{64}$' then
    raise exception 'reason digest is required' using errcode = '23514';
  end if;

  update redacted_private_experience_records
  set lifecycle_status = 'revoked',
      revoked_at = now(),
      revocation_reason_digest = row_reason_digest,
      updated_at = now()
  where tenant_id = binding.tenant_id
    and namespace_id = binding.namespace_id
    and id = row_record_id
    and lifecycle_status = 'captured'
  returning id, lifecycle_status
  into updated;

  record_id := row_record_id;
  lifecycle_status := coalesce(updated.lifecycle_status, 'not_changed');
  revoked := updated.id is not null;
  protected_data_serving_enabled := false;
  publication_enabled := false;
  return next;
end;
$$;

create or replace function knudg_closed_api_purge_redacted_experience(
  row_workspace_id text,
  row_record_id uuid,
  row_reason_digest text
)
returns table (
  record_id uuid,
  lifecycle_status text,
  purged boolean,
  protected_data_serving_enabled boolean,
  publication_enabled boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
  updated record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;
  if row_record_id is null then
    raise exception 'record id is required' using errcode = '23514';
  end if;
  if row_reason_digest is null or row_reason_digest !~ '^[a-f0-9]{64}$' then
    raise exception 'reason digest is required' using errcode = '23514';
  end if;

  update redacted_private_experience_records
  set lifecycle_status = 'purged',
      subject_public_name = 'Purged private record',
      subject_aliases = '{}'::text[],
      title = 'Purged private experience',
      summary = 'Purged redacted private experience record with display fields removed.',
      observations = array['Purged private experience record.']::text[],
      subjective_impressions = '{}'::text[],
      revoked_at = coalesce(revoked_at, now()),
      purged_at = now(),
      purge_reason_digest = row_reason_digest,
      updated_at = now()
  where tenant_id = binding.tenant_id
    and namespace_id = binding.namespace_id
    and id = row_record_id
    and lifecycle_status in ('captured', 'revoked')
  returning id, lifecycle_status
  into updated;

  record_id := row_record_id;
  lifecycle_status := coalesce(updated.lifecycle_status, 'not_changed');
  purged := updated.id is not null;
  protected_data_serving_enabled := false;
  publication_enabled := false;
  return next;
end;
$$;

revoke all on function knudg_closed_api_revoke_redacted_experience(text, uuid, text) from public;
revoke all on function knudg_closed_api_purge_redacted_experience(text, uuid, text) from public;
grant execute on function knudg_closed_api_revoke_redacted_experience(text, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_api_purge_redacted_experience(text, uuid, text) to knudg_api_app;
