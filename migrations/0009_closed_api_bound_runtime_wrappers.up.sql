create table if not exists knudg_private.closed_api_runtime_bindings (
  tenant_id uuid not null,
  namespace_id uuid not null,
  principal_id uuid not null,
  tenant_slug text not null,
  namespace_key text not null,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, namespace_id, principal_id),
  check (tenant_slug <> '' and namespace_key <> '')
);

create unique index if not exists closed_api_runtime_bindings_single_active_idx
  on knudg_private.closed_api_runtime_bindings(enabled)
  where enabled;

revoke all on table knudg_private.closed_api_runtime_bindings from public;

create or replace function knudg_private.closed_api_runtime_binding()
returns table (
  tenant_id uuid,
  namespace_id uuid,
  principal_id uuid,
  tenant_slug text,
  namespace_key text
)
language plpgsql
security definer
set search_path = pg_catalog, knudg_private, pg_temp
as $$
begin
  if session_user <> 'knudg_api_app' then
    raise exception 'closed api runtime binding rejected' using errcode = '28000';
  end if;

  return query
  select b.tenant_id, b.namespace_id, b.principal_id, b.tenant_slug, b.namespace_key
  from knudg_private.closed_api_runtime_bindings b
  where b.enabled
  limit 1;

  if not found then
    raise exception 'closed api runtime binding is not configured' using errcode = '28000';
  end if;
end;
$$;

revoke all on function knudg_private.closed_api_runtime_binding() from public;

create or replace function knudg_closed_api_publish(
  row_workspace_id text,
  row_body_json jsonb,
  row_projection_payload jsonb
)
returns table (
  tenant_id uuid,
  namespace_id uuid,
  principal_id uuid,
  card_id uuid,
  card_version_id uuid,
  body_digest text,
  payload_digest text
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  return query
  select *
  from knudg_closed_private_publish(
    binding.tenant_id,
    binding.namespace_id,
    binding.principal_id,
    binding.tenant_slug,
    binding.namespace_key,
    row_workspace_id,
    row_body_json,
    row_projection_payload
  );
end;
$$;

create or replace function knudg_closed_api_search(
  row_workspace_id text,
  row_terms text[],
  row_query_text text,
  row_limit integer
)
returns table (
  card_id uuid,
  card_version_id uuid,
  namespace_id uuid,
  payload_digest text,
  outcome_type text,
  quality_state text,
  evidence_strength text,
  match_score integer,
  coarse_match_reason text[]
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  return query
  select *
  from knudg_closed_private_search(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    row_workspace_id,
    row_terms,
    row_query_text,
    row_limit
  );
end;
$$;

create or replace function knudg_closed_api_revoke(
  row_workspace_id text,
  row_card_id uuid,
  row_reason_digest text
)
returns table (
  card_id uuid,
  card_version_id uuid,
  revoked boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  return query
  select *
  from knudg_closed_private_revoke(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    row_workspace_id,
    row_card_id,
    row_reason_digest
  );
end;
$$;

create or replace function knudg_closed_api_purge(
  row_workspace_id text,
  row_card_id uuid,
  row_reason_digest text
)
returns table (
  card_id uuid,
  card_version_id uuid,
  purged boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  return query
  select *
  from knudg_closed_private_purge(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    row_workspace_id,
    row_card_id,
    row_reason_digest
  );
end;
$$;

create or replace function knudg_closed_api_publication_candidate(
  row_workspace_id text,
  row_card_id uuid
)
returns table (
  card_id uuid,
  card_version_id uuid,
  body_digest text,
  payload_digest text,
  candidate_digest text,
  candidate_json jsonb
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
  target record;
  candidate_payload jsonb;
  digest text;
begin
  select * into binding from knudg_private.closed_api_runtime_binding();
  perform knudg_private.closed_private_require_namespace_scope(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    array['read','submit','admin']::text[]
  );
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;

  select c.id as card_id,
    c.current_version_id as card_version_id,
    c.namespace_id,
    cv.payload_digest,
    b.body_json,
    b.body_digest
  into target
  from experience_cards c
  join card_versions cv
    on cv.tenant_id = c.tenant_id
   and cv.card_id = c.id
   and cv.id = c.current_version_id
  join local_private_card_bodies b
    on b.tenant_id = c.tenant_id
   and b.card_id = c.id
   and b.card_version_id = c.current_version_id
  join local_private_search_documents d
    on d.tenant_id = c.tenant_id
   and d.card_id = c.id
   and d.card_version_id = c.current_version_id
  where c.tenant_id = binding.tenant_id
    and c.id = row_card_id
    and c.namespace_id = binding.namespace_id
    and c.status = 'approved_private'
    and b.lifecycle_status = 'captured'
    and b.purged_at is null
    and d.lifecycle_status = 'captured'
    and d.revoked_at is null
    and d.purged_at is null
    and knudg_private.local_private_card_body_v0_is_valid(b.body_json)
    and not exists (
      select 1
      from revocation_tombstones rt
      where rt.tenant_id = c.tenant_id
        and (
          rt.subject_type = 'tenant'
          or (rt.subject_type = 'namespace' and rt.namespace_id = c.namespace_id)
          or (rt.subject_type = 'card' and rt.card_id = c.id)
          or (rt.subject_type = 'card_version' and rt.card_version_id = c.current_version_id)
        )
    )
  for update;

  if not found then
    raise exception 'private card not found or not publication-candidate eligible' using errcode = '28000';
  end if;

  candidate_payload := jsonb_build_object(
    'schema_version', 'closed-publication-candidate-v0',
    'candidate_state', 'publication_ready_candidate',
    'source_class', 'local_private_dogfood',
    'public_publication_enabled', false,
    'external_publication_enabled', false,
    'team_publication_enabled', false,
    'requires_human_approval', true,
    'source', jsonb_build_object(
      'card_id', target.card_id,
      'card_version_id', target.card_version_id,
      'namespace_id', target.namespace_id,
      'body_digest', target.body_digest,
      'payload_digest', target.payload_digest
    ),
    'artifact', jsonb_build_object(
      'title', target.body_json->>'title',
      'problem_summary', target.body_json->>'problem_summary',
      'solution_summary', target.body_json->>'solution_summary',
      'public_packages', target.body_json->'public_packages',
      'environment_tags', target.body_json->'environment_tags',
      'public_reference_urls', target.body_json->'public_reference_urls',
      'command_labels', target.body_json->'command_labels',
      'error_fingerprints', target.body_json->'error_fingerprints',
      'lessons', target.body_json->'lessons'
    ),
    'redaction', jsonb_build_object(
      'state', 'sanitized_public_fields_only',
      'source_contract', 'local-private-card-v0',
      'db_validator', 'knudg_private.local_private_card_body_v0_is_valid',
      'raw_body_excluded', true,
      'private_path_hostname_secret_scans_required', true,
      'candidate_digest_binds_exact_artifact', true
    ),
    'review', jsonb_build_object(
      'review_state', 'candidate_ready',
      'review_required_before_publication', true,
      'consent_required_before_publication', true,
      'reviewer_publish_enabled', false,
      'public_indexing_enabled', false
    )
  );
  digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(candidate_payload), 'sha256'), 'hex');

  insert into local_private_value_events(
    tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
  )
  values (
    binding.tenant_id,
    row_workspace_id,
    'publication_candidate_prepared',
    target.card_id,
    target.card_version_id,
    jsonb_build_object(
      'candidate_digest', digest,
      'candidate_state', 'publication_ready_candidate',
      'redaction_state', 'sanitized_public_fields_only',
      'public_publication_enabled', false
    )
  );

  card_id := target.card_id;
  card_version_id := target.card_version_id;
  body_digest := target.body_digest;
  payload_digest := target.payload_digest;
  candidate_digest := digest;
  candidate_json := candidate_payload;
  return next;
end;
$$;

revoke all on function knudg_closed_api_publish(text, jsonb, jsonb) from public;
revoke all on function knudg_closed_api_search(text, text[], text, integer) from public;
revoke all on function knudg_closed_api_revoke(text, uuid, text) from public;
revoke all on function knudg_closed_api_purge(text, uuid, text) from public;
revoke all on function knudg_closed_api_publication_candidate(text, uuid) from public;

revoke all on function knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb) from knudg_api_app;
revoke all on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) from knudg_api_app;
revoke all on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) from knudg_api_app;
revoke all on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) from knudg_api_app;
revoke all on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) from knudg_api_app;

grant execute on function knudg_closed_api_publish(text, jsonb, jsonb) to knudg_api_app;
grant execute on function knudg_closed_api_search(text, text[], text, integer) to knudg_api_app;
grant execute on function knudg_closed_api_revoke(text, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_api_purge(text, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_api_publication_candidate(text, uuid) to knudg_api_app;
