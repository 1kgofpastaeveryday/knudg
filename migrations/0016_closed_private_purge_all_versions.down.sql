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
