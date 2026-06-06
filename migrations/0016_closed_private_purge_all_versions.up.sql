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
  target record;
  search_versions integer := 0;
  body_versions integer := 0;
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

  select c.id as card_id, c.current_version_id
  into target
  from experience_cards c
  where c.tenant_id = row_tenant_id
    and c.id = row_card_id
    and c.namespace_id = any(row_namespace_ids);

  if found then
    update local_private_search_documents
    set lifecycle_status = 'revoked',
      revoked_at = coalesce(revoked_at, now())
    where local_private_search_documents.tenant_id = row_tenant_id
      and local_private_search_documents.card_id = row_card_id
      and lifecycle_status = 'captured'
      and purged_at is null;
    get diagnostics search_versions = row_count;

    update local_private_card_bodies
    set lifecycle_status = 'revoked'
    where local_private_card_bodies.tenant_id = row_tenant_id
      and local_private_card_bodies.card_id = row_card_id
      and lifecycle_status <> 'purged'
      and purged_at is null;
    get diagnostics body_versions = row_count;

    did_revoke := search_versions > 0 or body_versions > 0;
    if did_revoke then
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
        target.card_id,
        target.current_version_id,
        jsonb_build_object(
          'reason_digest', row_reason_digest,
          'search_versions_revoked', search_versions,
          'body_versions_revoked', body_versions
        )
      );
    end if;
  end if;

  card_id := row_card_id;
  card_version_id := case when did_revoke then target.current_version_id else null end;
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
  search_versions integer := 0;
  body_versions integer := 0;
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

  select c.id as card_id, c.current_version_id
  into target
  from experience_cards c
  where c.tenant_id = row_tenant_id
    and c.id = row_card_id
    and c.namespace_id = any(row_namespace_ids);

  if found then
    update local_private_search_documents
    set lifecycle_status = 'purged',
      search_text = '',
      revoked_at = null,
      purged_at = coalesce(purged_at, now())
    where local_private_search_documents.tenant_id = row_tenant_id
      and local_private_search_documents.card_id = row_card_id
      and (
        lifecycle_status <> 'purged'
        or purged_at is null
        or search_text <> ''
      );
    get diagnostics search_versions = row_count;

    update local_private_card_bodies
    set lifecycle_status = 'purged',
      body_json = '{}'::jsonb,
      purged_at = coalesce(purged_at, now())
    where local_private_card_bodies.tenant_id = row_tenant_id
      and local_private_card_bodies.card_id = row_card_id
      and (
        lifecycle_status <> 'purged'
        or purged_at is null
        or body_json <> '{}'::jsonb
      );
    get diagnostics body_versions = row_count;

    did_purge := search_versions > 0 or body_versions > 0;
    if did_purge then
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
        target.current_version_id,
        jsonb_build_object(
          'reason_digest', row_reason_digest,
          'search_versions_purged', search_versions,
          'body_versions_purged', body_versions
        )
      );
    end if;
  end if;

  card_id := row_card_id;
  card_version_id := case when did_purge then target.current_version_id else null end;
  purged := did_purge;
  return next;
end;
$$;
