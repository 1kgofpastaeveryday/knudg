create or replace function knudg_private.closed_private_require_namespace_scope(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
  row_scopes text[]
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
begin
  if row_tenant_id is null
    or row_principal_id is null
    or row_namespace_ids is null
    or array_length(row_namespace_ids, 1) is null
    or row_scopes is null
    or array_length(row_scopes, 1) is null then
    raise exception 'closed private scope rejected' using errcode = '28000';
  end if;

  if not exists (
    select 1
    from tenant_memberships tm
    join principals p on p.id = tm.principal_id
    where tm.tenant_id = row_tenant_id
      and tm.principal_id = row_principal_id
      and tm.status = 'active'
      and tm.revoked_at is null
      and tm.effective_until is null
      and tm.valid_from <= now()
      and (tm.expires_at is null or tm.expires_at > now())
      and p.disabled_at is null
  ) then
    raise exception 'closed private tenant binding rejected' using errcode = '28000';
  end if;

  if exists (
    select 1
    from unnest(row_namespace_ids) as ns(namespace_id)
    where not exists (
      select 1
      from namespace_grants ng
      where ng.tenant_id = row_tenant_id
        and ng.namespace_id = ns.namespace_id
        and ng.principal_id = row_principal_id
        and ng.grant_scope = any(row_scopes)
        and ng.status = 'active'
        and ng.revoked_at is null
        and ng.effective_until is null
        and ng.valid_from <= now()
        and (ng.expires_at is null or ng.expires_at > now())
    )
  ) then
    raise exception 'closed private namespace binding rejected' using errcode = '28000';
  end if;
end;
$$;

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

create or replace function knudg_closed_private_revoke(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
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
  changed record;
  did_revoke boolean := false;
begin
  perform knudg_private.closed_private_require_namespace_scope(
    row_tenant_id,
    row_namespace_ids,
    row_principal_id,
    array['submit','admin']::text[]
  );
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;

  update local_private_search_documents d
  set lifecycle_status = 'revoked', revoked_at = coalesce(revoked_at, now())
  from experience_cards c
  where c.tenant_id = d.tenant_id
    and c.id = d.card_id
    and d.tenant_id = row_tenant_id
    and d.card_id = row_card_id
    and c.namespace_id = any(row_namespace_ids)
    and d.lifecycle_status = 'captured'
    and d.purged_at is null
  returning d.card_id, d.card_version_id into changed;

  if found then
    did_revoke := true;
    update local_private_card_bodies
    set lifecycle_status = 'revoked'
    where local_private_card_bodies.tenant_id = row_tenant_id
      and local_private_card_bodies.card_id = row_card_id
      and local_private_card_bodies.card_version_id = changed.card_version_id
      and lifecycle_status = 'captured'
      and purged_at is null;

    update experience_cards
    set status = 'revoked', updated_at = now()
    where experience_cards.tenant_id = row_tenant_id and experience_cards.id = row_card_id;

    insert into local_private_value_events(
      tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
    )
    values (
      row_tenant_id,
      row_workspace_id,
      'revoke_completed',
      changed.card_id,
      changed.card_version_id,
      jsonb_build_object('reason_digest', row_reason_digest)
    );
  end if;

  card_id := row_card_id;
  card_version_id := case when did_revoke then changed.card_version_id else null end;
  revoked := did_revoke;
  return next;
end;
$$;

create or replace function knudg_closed_private_purge(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
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
  target record;
  did_purge boolean := false;
begin
  perform knudg_private.closed_private_require_namespace_scope(
    row_tenant_id,
    row_namespace_ids,
    row_principal_id,
    array['submit','admin']::text[]
  );
  if row_workspace_id is null or row_workspace_id = '' then
    raise exception 'workspace id is required' using errcode = '23514';
  end if;

  select d.card_id, d.card_version_id into target
  from local_private_search_documents d
  join experience_cards c on c.tenant_id = d.tenant_id and c.id = d.card_id
  where d.tenant_id = row_tenant_id
    and d.card_id = row_card_id
    and c.namespace_id = any(row_namespace_ids)
  order by d.created_at desc
  limit 1;

  if found then
    did_purge := true;
    update local_private_search_documents
    set lifecycle_status = 'purged',
      search_text = '',
      revoked_at = null,
      purged_at = coalesce(purged_at, now())
    where local_private_search_documents.tenant_id = row_tenant_id
      and local_private_search_documents.card_id = row_card_id
      and local_private_search_documents.card_version_id = target.card_version_id;

    update local_private_card_bodies
    set lifecycle_status = 'purged',
      body_json = '{}'::jsonb,
      purged_at = coalesce(purged_at, now())
    where local_private_card_bodies.tenant_id = row_tenant_id
      and local_private_card_bodies.card_id = row_card_id
      and local_private_card_bodies.card_version_id = target.card_version_id;

    update experience_cards
    set status = 'revoked', updated_at = now()
    where experience_cards.tenant_id = row_tenant_id and experience_cards.id = row_card_id;

    insert into local_private_value_events(
      tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
    )
    values (
      row_tenant_id,
      row_workspace_id,
      'purge_completed',
      target.card_id,
      target.card_version_id,
      jsonb_build_object('reason_digest', row_reason_digest)
    );
  end if;

  card_id := row_card_id;
  card_version_id := case when did_purge then target.card_version_id else null end;
  purged := did_purge;
  return next;
end;
$$;

revoke all on function knudg_private.closed_private_require_namespace_scope(uuid, uuid[], uuid, text[]) from public;
revoke all on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) from public;
revoke all on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) from public;
revoke all on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) from public;

grant execute on function knudg_closed_private_search(uuid, uuid[], uuid, text, text[], text, integer) to knudg_app;
grant execute on function knudg_closed_private_revoke(uuid, uuid[], uuid, text, uuid, text) to knudg_app;
grant execute on function knudg_closed_private_purge(uuid, uuid[], uuid, text, uuid, text) to knudg_app;
