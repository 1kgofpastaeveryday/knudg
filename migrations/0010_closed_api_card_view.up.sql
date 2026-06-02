create or replace function knudg_closed_api_card_view(
  row_workspace_id text,
  row_card_id uuid
)
returns table (
  card_id uuid,
  card_version_id uuid,
  namespace_id uuid,
  body_digest text,
  payload_digest text,
  body_json jsonb
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  binding record;
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

  return query
  select c.id as card_id,
    c.current_version_id as card_version_id,
    c.namespace_id,
    b.body_digest,
    cv.payload_digest,
    b.body_json
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
    );
end;
$$;

revoke all on function knudg_closed_api_card_view(text, uuid) from public;
grant execute on function knudg_closed_api_card_view(text, uuid) to knudg_api_app;
