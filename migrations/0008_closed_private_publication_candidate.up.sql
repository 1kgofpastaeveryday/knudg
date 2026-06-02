alter table local_private_value_events
  drop constraint if exists local_private_value_events_event_name_check;

alter table local_private_value_events
  add constraint local_private_value_events_event_name_check check (event_name in (
    'capture_attempt','capture_rejected','search_completed','suggestion_shown',
    'suggestion_accepted','suggestion_ignored','revoke_completed',
    'purge_completed','leakage_check_completed','publication_candidate_prepared'
  ));

create or replace function knudg_closed_private_publication_candidate(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
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
  target record;
  candidate_payload jsonb;
  digest text;
begin
  perform knudg_private.closed_private_require_namespace_scope(
    row_tenant_id,
    row_namespace_ids,
    row_principal_id,
    array['read','submit','admin']::text[]
  );
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;

  select c.id as card_id,
    c.current_version_id as card_version_id,
    c.namespace_id,
    c.outcome_type,
    c.quality_state,
    c.evidence_strength,
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
  where c.tenant_id = row_tenant_id
    and c.id = row_card_id
    and c.namespace_id = any(row_namespace_ids)
    and c.status = 'approved_private'
    and b.lifecycle_status = 'captured'
    and b.purged_at is null
    and d.lifecycle_status = 'captured'
    and d.revoked_at is null
    and d.purged_at is null
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
    row_tenant_id,
    row_workspace_id,
    'publication_candidate_prepared',
    target.card_id,
    target.card_version_id,
    jsonb_build_object(
      'candidate_digest', digest,
      'candidate_state', 'publication_ready_candidate',
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

revoke all on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) from public;
grant execute on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) to knudg_app;
grant execute on function knudg_closed_private_publication_candidate(uuid, uuid[], uuid, text, uuid) to knudg_api_app;
