create or replace function knudg_closed_private_publish(
  row_tenant_id uuid,
  row_namespace_id uuid,
  row_principal_id uuid,
  row_tenant_slug text,
  row_namespace_key text,
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
  new_card_id uuid;
  new_version_id uuid;
  new_body_digest text;
  new_payload_digest text;
  row_search_text text;
begin
  if row_tenant_slug is null or row_tenant_slug = '' then
    raise exception 'tenant slug is required' using errcode = '23514';
  end if;
  if row_namespace_key is null or row_namespace_key = '' then
    raise exception 'namespace key is required' using errcode = '23514';
  end if;
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

  new_card_id := knudg_crypto.gen_random_uuid();
  new_version_id := knudg_crypto.gen_random_uuid();
  new_body_digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(row_body_json), 'sha256'), 'hex');
  new_payload_digest := encode(knudg_crypto.digest(knudg_private.canonical_jsonb(row_projection_payload), 'sha256'), 'hex');
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

  insert into tenants(id, slug, name)
  values (row_tenant_id, row_tenant_slug, 'Knudg Closed Private')
  on conflict (id) do update set slug = excluded.slug;

  insert into principals(id, principal_type, display_name)
  values (row_principal_id, 'human_user', 'Closed Launch Operator')
  on conflict (id) do update set display_name = excluded.display_name;

  insert into tenant_memberships(tenant_id, id, principal_id, membership_role, status, valid_from)
  values (row_tenant_id, knudg_crypto.gen_random_uuid(), row_principal_id, 'member', 'active', now() - interval '1 minute')
  on conflict do nothing;

  insert into namespaces(tenant_id, id, key, name, visibility)
  values (row_tenant_id, row_namespace_id, row_namespace_key, 'Closed Private', 'private')
  on conflict on constraint namespaces_pkey do update set key = excluded.key;

  insert into namespace_grants(tenant_id, id, namespace_id, principal_id, grant_scope, status, valid_from)
  select row_tenant_id, knudg_crypto.gen_random_uuid(), row_namespace_id, row_principal_id, scope, 'active', now() - interval '1 minute'
  from unnest(array['submit','read','admin']) as scope
  on conflict do nothing;

  insert into experience_cards(
    tenant_id, id, namespace_id, current_version_id, status,
    outcome_type, quality_state, evidence_strength, created_by
  )
  values (
    row_tenant_id, new_card_id, row_namespace_id, new_version_id, 'approved_private',
    'solved', 'unreviewed', 'operator_judgment', row_principal_id
  );

  insert into card_versions(
    tenant_id, id, card_id, version_number, card_schema_version,
    payload_json, payload_digest, created_by
  )
  values (
    row_tenant_id, new_version_id, new_card_id, 1, 1,
    row_projection_payload, new_payload_digest, row_principal_id
  );

  insert into local_private_card_bodies(
    tenant_id, card_id, card_version_id, body_json, body_digest, created_by
  )
  values (row_tenant_id, new_card_id, new_version_id, row_body_json, new_body_digest, row_principal_id);

  insert into local_private_search_documents(
    tenant_id, card_id, card_version_id, search_text, rank_manifest_version
  )
  values (row_tenant_id, new_card_id, new_version_id, row_search_text, 'local_private_fts_v0');

  insert into local_private_value_events(
    tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
  )
  values (
    row_tenant_id, row_workspace_id, 'capture_attempt', new_card_id, new_version_id,
    '{"result":"private_published","source_class":"local_private_dogfood"}'::jsonb
  );

  tenant_id := row_tenant_id;
  namespace_id := row_namespace_id;
  principal_id := row_principal_id;
  card_id := new_card_id;
  card_version_id := new_version_id;
  body_digest := new_body_digest;
  payload_digest := new_payload_digest;
  return next;
end;
$$;

revoke all on function knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb) from public;
grant execute on function knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb) to knudg_app;
