alter table local_private_value_events
  drop constraint if exists local_private_value_events_event_name_check;

alter table local_private_value_events
  add constraint local_private_value_events_event_name_check check (event_name in (
    'capture_attempt','capture_rejected','search_completed','suggestion_shown',
    'suggestion_accepted','suggestion_ignored','revoke_completed',
    'purge_completed','leakage_check_completed','publication_candidate_prepared',
    'merge_update_completed'
  ));

create or replace function knudg_closed_private_search(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
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
  if row_terms is null or array_length(row_terms, 1) is null then
    return;
  end if;
  if row_limit is null or row_limit < 1 or row_limit > 10 then
    row_limit := 3;
  end if;

  insert into local_private_value_events(tenant_id, workspace_id, event_name, event_json)
  values (
    row_tenant_id,
    row_workspace_id,
    'search_completed',
    jsonb_build_object('served_from', 'closed_private_exact_fts')
  );

  return query
  with active_docs as (
    select c.tenant_id, c.id as card_id, c.namespace_id,
      c.outcome_type, c.quality_state, c.evidence_strength,
      d.card_version_id, d.search_text, d.search_vector,
      cv.payload_digest, c.updated_at
    from local_private_search_documents d
    join experience_cards c
      on c.tenant_id = d.tenant_id
     and c.id = d.card_id
     and c.current_version_id = d.card_version_id
    join card_versions cv
      on cv.tenant_id = d.tenant_id
     and cv.card_id = d.card_id
     and cv.id = d.card_version_id
    join local_private_card_bodies b
      on b.tenant_id = d.tenant_id
     and b.card_id = d.card_id
     and b.card_version_id = d.card_version_id
    where d.tenant_id = row_tenant_id
      and c.namespace_id = any(row_namespace_ids)
      and c.status = 'approved_private'
      and d.lifecycle_status = 'captured'
      and d.revoked_at is null
      and d.purged_at is null
      and b.lifecycle_status = 'captured'
      and b.purged_at is null
      and not exists (
        select 1
        from revocation_tombstones rt
        where rt.tenant_id = c.tenant_id
          and (
            rt.subject_type = 'tenant'
            or (rt.subject_type = 'namespace' and rt.namespace_id = c.namespace_id)
            or (rt.subject_type = 'card' and rt.card_id = c.id)
            or (rt.subject_type = 'card_version' and rt.card_version_id = d.card_version_id)
          )
      )
  ),
  scored as (
    select *,
      plainto_tsquery('english', row_query_text) as query,
      (
        select count(*)::integer
        from unnest(row_terms) as exact(term)
        where lower(active_docs.search_text) like '%' || exact.term || '%'
      ) as exact_hits,
      array(
        select exact.term
        from unnest(row_terms) as exact(term)
        where lower(active_docs.search_text) like '%' || exact.term || '%'
        limit 8
      ) as matched_terms
    from active_docs
  )
  select scored.card_id,
    scored.card_version_id,
    scored.namespace_id,
    scored.payload_digest,
    scored.outcome_type,
    scored.quality_state,
    scored.evidence_strength,
    greatest(scored.exact_hits + case when ts_rank_cd(scored.search_vector, scored.query) > 0 then 1 else 0 end, 1)::integer as match_score,
    scored.matched_terms as coarse_match_reason
  from scored
  where scored.exact_hits > 0 or scored.search_vector @@ scored.query
  order by scored.exact_hits desc, ts_rank_cd(scored.search_vector, scored.query) desc, scored.updated_at desc, scored.card_id
  limit row_limit;
end;
$$;

create or replace function knudg_closed_private_merge_update(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
  row_workspace_id text,
  row_card_id uuid,
  row_body_json jsonb,
  row_projection_payload jsonb,
  row_merge_json jsonb
)
returns table (
  tenant_id uuid,
  namespace_id uuid,
  principal_id uuid,
  card_id uuid,
  previous_card_version_id uuid,
  card_version_id uuid,
  version_number integer,
  body_digest text,
  payload_digest text,
  merge_result text
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  target record;
  new_version_id uuid;
  new_body_digest text;
  new_payload_digest text;
  next_version_number integer;
  row_search_text text;
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
  if not knudg_private.local_private_card_body_v0_is_valid(row_body_json) then
    raise exception 'local private card body rejected' using errcode = '23514';
  end if;
  if not knudg_private.card_payload_v1_is_valid(row_projection_payload) then
    raise exception 'local private projection rejected' using errcode = '23514';
  end if;
  if row_projection_payload->>'source_class' <> 'local_private_dogfood'
    or row_projection_payload->>'visibility' <> 'local_private'
    or row_projection_payload->>'sharing_state' <> 'not_shared'
    or row_projection_payload->>'publication_state' <> 'never_publishable'
    or row_projection_payload #>> '{privacy,source_class}' <> 'local_private_dogfood'
    or row_projection_payload #>> '{privacy,publication_state}' <> 'never_publishable'
    or row_projection_payload #>> '{provenance,source_class}' <> 'local_private_dogfood' then
    raise exception 'local private projection rejected' using errcode = '23514';
  end if;
  if jsonb_typeof(row_merge_json) <> 'object'
    or row_merge_json->>'schema_version' <> 'local-private-merge-request-v0'
    or row_merge_json->>'decision' <> 'update_existing'
    or coalesce(row_merge_json->>'reason_digest', '') !~ '^sha256:[a-f0-9]{64}$' then
    raise exception 'merge request rejected' using errcode = '23514';
  end if;

  select c.id as card_id,
    c.current_version_id,
    c.namespace_id,
    cv.version_number,
    cv.payload_digest,
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
    raise exception 'private card not found or not merge-update eligible' using errcode = '28000';
  end if;

  new_body_digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(row_body_json), 'sha256'), 'hex');
  new_payload_digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(row_projection_payload), 'sha256'), 'hex');

  if target.body_digest = new_body_digest and target.payload_digest = new_payload_digest then
    insert into local_private_value_events(
      tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
    )
    values (
      row_tenant_id,
      row_workspace_id,
      'merge_update_completed',
      target.card_id,
      target.current_version_id,
      jsonb_build_object(
        'result', 'already_current',
        'previous_card_version_id', target.current_version_id,
        'card_version_id', target.current_version_id,
        'reason_digest', row_merge_json->>'reason_digest',
        'created_new_card', false
      )
    );

    tenant_id := row_tenant_id;
    namespace_id := target.namespace_id;
    principal_id := row_principal_id;
    card_id := target.card_id;
    previous_card_version_id := target.current_version_id;
    card_version_id := target.current_version_id;
    version_number := target.version_number;
    body_digest := new_body_digest;
    payload_digest := new_payload_digest;
    merge_result := 'already_current';
    return next;
    return;
  end if;

  new_version_id := knudg_crypto.gen_random_uuid();
  select coalesce(max(cv.version_number), 0) + 1
  into next_version_number
  from card_versions cv
  where cv.tenant_id = row_tenant_id
    and cv.card_id = target.card_id;

  row_search_text := concat_ws(
    ' ',
    row_body_json->>'title',
    row_body_json->>'problem_summary',
    row_body_json->>'solution_summary',
    row_body_json->'public_packages',
    row_body_json->'environment_tags',
    row_body_json->'public_reference_urls',
    row_body_json->'command_labels',
    row_body_json->'error_fingerprints',
    row_body_json->'lessons'
  );

  insert into card_versions(
    tenant_id, id, card_id, version_number, card_schema_version,
    payload_json, payload_digest, created_by
  )
  values (
    row_tenant_id, new_version_id, target.card_id, next_version_number, 1,
    row_projection_payload, new_payload_digest, row_principal_id
  );

  insert into card_edges(
    tenant_id, id, source_card_id, target_card_id,
    source_card_version_id, target_card_version_id, edge_type, created_by
  )
  values (
    row_tenant_id,
    knudg_crypto.gen_random_uuid(),
    target.card_id,
    target.card_id,
    new_version_id,
    target.current_version_id,
    'supersedes',
    row_principal_id
  )
  on conflict do nothing;

  update experience_cards
  set current_version_id = new_version_id,
      outcome_type = 'solved',
      quality_state = 'unreviewed',
      evidence_strength = 'operator_judgment',
      updated_at = now()
  where experience_cards.tenant_id = row_tenant_id
    and experience_cards.id = target.card_id
    and experience_cards.current_version_id = target.current_version_id;

  update local_private_search_documents
  set lifecycle_status = 'revoked',
      revoked_at = now()
  where local_private_search_documents.tenant_id = row_tenant_id
    and local_private_search_documents.card_id = target.card_id
    and local_private_search_documents.card_version_id = target.current_version_id
    and local_private_search_documents.lifecycle_status = 'captured'
    and local_private_search_documents.revoked_at is null;

  insert into local_private_card_bodies(
    tenant_id, card_id, card_version_id, body_json, body_digest, created_by
  )
  values (row_tenant_id, target.card_id, new_version_id, row_body_json, new_body_digest, row_principal_id);

  insert into local_private_search_documents(
    tenant_id, card_id, card_version_id, search_text, rank_manifest_version
  )
  values (row_tenant_id, target.card_id, new_version_id, row_search_text, 'local_private_fts_v0');

  insert into local_private_value_events(
    tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
  )
  values (
    row_tenant_id,
    row_workspace_id,
    'merge_update_completed',
    target.card_id,
    new_version_id,
    jsonb_build_object(
      'result', 'version_created',
      'previous_card_version_id', target.current_version_id,
      'card_version_id', new_version_id,
      'version_number', next_version_number,
      'reason_digest', row_merge_json->>'reason_digest',
      'created_new_card', false
    )
  );

  tenant_id := row_tenant_id;
  namespace_id := target.namespace_id;
  principal_id := row_principal_id;
  card_id := target.card_id;
  previous_card_version_id := target.current_version_id;
  card_version_id := new_version_id;
  version_number := next_version_number;
  body_digest := new_body_digest;
  payload_digest := new_payload_digest;
  merge_result := 'version_created';
  return next;
end;
$$;

create or replace function knudg_closed_api_merge_update(
  row_workspace_id text,
  row_card_id uuid,
  row_body_json jsonb,
  row_projection_payload jsonb,
  row_merge_json jsonb
)
returns table (
  tenant_id uuid,
  namespace_id uuid,
  principal_id uuid,
  card_id uuid,
  previous_card_version_id uuid,
  card_version_id uuid,
  version_number integer,
  body_digest text,
  payload_digest text,
  merge_result text
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
  from knudg_closed_private_merge_update(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    row_workspace_id,
    row_card_id,
    row_body_json,
    row_projection_payload,
    row_merge_json
  );
end;
$$;

revoke all on function knudg_closed_private_merge_update(uuid, uuid[], uuid, text, uuid, jsonb, jsonb, jsonb) from public;
revoke all on function knudg_closed_private_merge_update(uuid, uuid[], uuid, text, uuid, jsonb, jsonb, jsonb) from knudg_api_app;
revoke all on function knudg_closed_api_merge_update(text, uuid, jsonb, jsonb, jsonb) from public;
grant execute on function knudg_closed_api_merge_update(text, uuid, jsonb, jsonb, jsonb) to knudg_api_app;
