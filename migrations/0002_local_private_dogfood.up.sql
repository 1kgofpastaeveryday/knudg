create or replace function knudg_private.local_private_text_is_sanitized(row_text text)
returns boolean
language sql
immutable
set search_path = pg_catalog, pg_temp
as $$
  select row_text is not null
    and row_text !~ '[[:cntrl:]]'
    and row_text !~* '(secret|password|credential|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|auth[_ -]?token|authorization[[:space:]]*[=:][[:space:]]*(bearer|token)|bearer[[:space:]]+[A-Za-z0-9._~+/-]+|github_pat_|ghp_[A-Za-z0-9_]+|-----BEGIN)'
    and row_text !~ '([A-Za-z]:\\|\\\\|/(Users|home|etc|var|tmp|mnt|working)(/|$))'
    and row_text !~* '(forbidden_canary|local_private_forbidden_canary|knudg_forbidden_canary)'
    and row_text !~ '(```|<[^>]+>)';
$$;

create or replace function knudg_private.local_private_jsonb_string_array_is_valid(
  row_value jsonb,
  row_max_items integer,
  row_max_length integer
)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select jsonb_typeof(row_value) = 'array'
    and jsonb_array_length(row_value) <= row_max_items
    and not exists (
      select 1
      from jsonb_array_elements(row_value) as item(value)
      where jsonb_typeof(item.value) <> 'string'
        or item.value #>> '{}' = ''
        or length(item.value #>> '{}') > row_max_length
        or not knudg_private.local_private_text_is_sanitized(item.value #>> '{}')
    );
$$;

create or replace function knudg_private.local_private_public_urls_are_valid(row_value jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select jsonb_typeof(row_value) = 'array'
    and jsonb_array_length(row_value) <= 3
    and not exists (
      select 1
      from jsonb_array_elements(row_value) as item(value)
      where jsonb_typeof(item.value) <> 'string'
        or item.value #>> '{}' = ''
        or length(item.value #>> '{}') > 2048
        or item.value #>> '{}' !~* '^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]+)?(/|$)'
        or item.value #>> '{}' ~* '^https://([^/?#]*localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|[^/?#]*\.local)([:/?#]|$)'
        or not knudg_private.local_private_text_is_sanitized(item.value #>> '{}')
    );
$$;

create or replace function knudg_private.local_private_command_labels_are_valid(row_value jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select knudg_private.local_private_jsonb_string_array_is_valid(row_value, 6, 80)
    and not exists (
      select 1
      from jsonb_array_elements(row_value) as item(value)
      where item.value #>> '{}' ~ '(^|[[:space:]])-{1,2}[A-Za-z0-9]'
        or item.value #>> '{}' ~ '[|&;<>]'
    );
$$;

create or replace function knudg_private.local_private_card_body_v0_is_valid(row_body jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select jsonb_typeof(row_body) = 'object'
    and not knudg_private.jsonb_has_non_ascii_keys(row_body)
    and not knudg_private.jsonb_has_non_portable_numbers(row_body)
    and not exists (
      select 1
      from jsonb_object_keys(row_body) as key
      where key not in (
        'source_class','title','problem_summary','solution_summary',
        'public_packages','environment_tags','public_reference_urls',
        'command_labels','error_fingerprints','lessons'
      )
    )
    and row_body ?& array[
      'source_class','title','problem_summary','solution_summary',
      'public_packages','environment_tags','public_reference_urls',
      'command_labels','error_fingerprints','lessons'
    ]
    and row_body->>'source_class' = 'local_private_dogfood'
    and jsonb_typeof(row_body->'title') = 'string'
    and length(row_body->>'title') between 8 and 120
    and knudg_private.local_private_text_is_sanitized(row_body->>'title')
    and jsonb_typeof(row_body->'problem_summary') = 'string'
    and length(row_body->>'problem_summary') between 20 and 600
    and knudg_private.local_private_text_is_sanitized(row_body->>'problem_summary')
    and jsonb_typeof(row_body->'solution_summary') = 'string'
    and length(row_body->>'solution_summary') between 20 and 900
    and knudg_private.local_private_text_is_sanitized(row_body->>'solution_summary')
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'public_packages', 8, 80)
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'environment_tags', 12, 40)
    and knudg_private.local_private_public_urls_are_valid(row_body->'public_reference_urls')
    and knudg_private.local_private_command_labels_are_valid(row_body->'command_labels')
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'error_fingerprints', 6, 120)
    and knudg_private.local_private_jsonb_string_array_is_valid(row_body->'lessons', 6, 200);
$$;

create or replace function knudg_private.local_private_event_json_is_valid(row_event jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog, knudg_private, pg_temp
as $$
  select jsonb_typeof(row_event) = 'object'
    and length(row_event::text) <= 4096
    and knudg_private.local_private_text_is_sanitized(row_event::text);
$$;

create table if not exists local_private_card_bodies (
  tenant_id uuid not null,
  card_id uuid not null,
  card_version_id uuid not null,
  lifecycle_status text not null default 'captured'
    check (lifecycle_status in ('captured','revoked','purged')),
  body_json jsonb not null,
  body_digest text not null,
  created_by uuid not null references principals(id) on delete restrict,
  created_at timestamptz not null default now(),
  purged_at timestamptz null,
  primary key (tenant_id, card_id, card_version_id),
  foreign key (tenant_id, card_id) references experience_cards(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_id, card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  check (body_digest ~ '^[0-9a-f]{64}$'),
  check (
    (
      lifecycle_status in ('captured','revoked')
      and purged_at is null
      and knudg_private.local_private_card_body_v0_is_valid(body_json)
      and body_digest = encode(knudg_crypto.digest(knudg_private.canonical_jsonb(body_json), 'sha256'), 'hex')
    )
    or (
      lifecycle_status = 'purged'
      and purged_at is not null
      and body_json = '{}'::jsonb
    )
  )
);

create table if not exists local_private_search_documents (
  tenant_id uuid not null,
  card_id uuid not null,
  card_version_id uuid not null,
  lifecycle_status text not null default 'captured'
    check (lifecycle_status in ('captured','revoked','purged')),
  search_text text not null,
  search_vector tsvector generated always as (to_tsvector('english'::regconfig, search_text)) stored,
  rank_manifest_version text not null,
  created_at timestamptz not null default now(),
  revoked_at timestamptz null,
  purged_at timestamptz null,
  primary key (tenant_id, card_id, card_version_id),
  foreign key (tenant_id, card_id) references experience_cards(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_id, card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  check (rank_manifest_version = 'local_private_fts_v0'),
  check (
    (
      lifecycle_status = 'captured'
      and revoked_at is null
      and purged_at is null
      and length(search_text) between 1 and 8192
      and knudg_private.local_private_text_is_sanitized(search_text)
    )
    or (
      lifecycle_status = 'revoked'
      and revoked_at is not null
      and purged_at is null
      and length(search_text) between 1 and 8192
      and knudg_private.local_private_text_is_sanitized(search_text)
    )
    or (
      lifecycle_status = 'purged'
      and purged_at is not null
      and search_text = ''
    )
  )
);

create table if not exists local_private_value_events (
  tenant_id uuid not null references tenants(id) on delete restrict,
  id uuid not null default knudg_crypto.gen_random_uuid(),
  workspace_id text not null,
  event_name text not null,
  card_id uuid null,
  card_version_id uuid null,
  created_at timestamptz not null default now(),
  event_json jsonb not null,
  primary key (tenant_id, id),
  foreign key (tenant_id, card_id) references experience_cards(tenant_id, id) on delete restrict,
  foreign key (tenant_id, card_id, card_version_id) references card_versions(tenant_id, card_id, id) on delete restrict,
  check (workspace_id <> '' and length(workspace_id) <= 200 and knudg_private.local_private_text_is_sanitized(workspace_id)),
  check (event_name in (
    'capture_attempt','capture_rejected','search_completed','suggestion_shown',
    'suggestion_accepted','suggestion_ignored','revoke_completed',
    'purge_completed','leakage_check_completed'
  )),
  check ((card_id is null and card_version_id is null) or (card_id is not null and card_version_id is not null)),
  check (knudg_private.local_private_event_json_is_valid(event_json))
);

create index if not exists local_private_card_bodies_active_card_idx
  on local_private_card_bodies(tenant_id, card_id, created_at desc)
  where lifecycle_status in ('captured','revoked') and purged_at is null;
create index if not exists local_private_card_bodies_purge_idx
  on local_private_card_bodies(tenant_id, purged_at, card_id)
  where lifecycle_status = 'purged';

create index if not exists local_private_search_documents_fts_idx
  on local_private_search_documents using gin(search_vector)
  where lifecycle_status = 'captured' and revoked_at is null and purged_at is null;
create index if not exists local_private_search_documents_active_idx
  on local_private_search_documents(tenant_id, created_at desc, card_id)
  where lifecycle_status = 'captured' and revoked_at is null and purged_at is null;
create index if not exists local_private_search_documents_revoke_idx
  on local_private_search_documents(tenant_id, card_id, revoked_at)
  where lifecycle_status = 'revoked';
create index if not exists local_private_search_documents_purge_idx
  on local_private_search_documents(tenant_id, card_id, purged_at)
  where lifecycle_status = 'purged';

create index if not exists local_private_value_events_workspace_idx
  on local_private_value_events(tenant_id, workspace_id, event_name, created_at desc);
create index if not exists local_private_value_events_card_idx
  on local_private_value_events(tenant_id, card_id, created_at desc)
  where card_id is not null;

alter table local_private_card_bodies enable row level security;
alter table local_private_card_bodies force row level security;
alter table local_private_search_documents enable row level security;
alter table local_private_search_documents force row level security;
alter table local_private_value_events enable row level security;
alter table local_private_value_events force row level security;

drop policy if exists local_private_card_bodies_isolation on local_private_card_bodies;
create policy local_private_card_bodies_isolation on local_private_card_bodies
  for all to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_card_bodies.tenant_id
        and c.id = local_private_card_bodies.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
    )
  )
  with check (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_card_bodies.tenant_id
        and c.id = local_private_card_bodies.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
    )
  );

drop policy if exists local_private_search_documents_select on local_private_search_documents;
create policy local_private_search_documents_select on local_private_search_documents
  for select to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and lifecycle_status = 'captured'
    and revoked_at is null
    and purged_at is null
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_search_documents.tenant_id
        and c.id = local_private_search_documents.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
        and knudg_private.card_not_revoked(c.tenant_id, c.namespace_id, c.id, local_private_search_documents.card_version_id)
    )
  );

drop policy if exists local_private_search_documents_insert on local_private_search_documents;
create policy local_private_search_documents_insert on local_private_search_documents
  for insert to knudg_app, knudg_worker
  with check (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_search_documents.tenant_id
        and c.id = local_private_search_documents.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
    )
  );

drop policy if exists local_private_search_documents_update on local_private_search_documents;
create policy local_private_search_documents_update on local_private_search_documents
  for update to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_search_documents.tenant_id
        and c.id = local_private_search_documents.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
    )
  )
  with check (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_search_documents.tenant_id
        and c.id = local_private_search_documents.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
    )
  );

drop policy if exists local_private_search_documents_delete on local_private_search_documents;
create policy local_private_search_documents_delete on local_private_search_documents
  for delete to knudg_app, knudg_worker
  using (
    tenant_id = knudg_private.current_tenant_id()
    and exists (
      select 1
      from public.experience_cards c
      where c.tenant_id = local_private_search_documents.tenant_id
        and c.id = local_private_search_documents.card_id
        and c.namespace_id = any(knudg_private.current_namespace_ids())
    )
  );

drop policy if exists local_private_value_events_isolation on local_private_value_events;
create policy local_private_value_events_isolation on local_private_value_events
  for all to knudg_app, knudg_worker
  using (tenant_id = knudg_private.current_tenant_id())
  with check (tenant_id = knudg_private.current_tenant_id());

grant select, insert, update, delete on local_private_card_bodies to knudg_app, knudg_worker;
grant select, insert, update, delete on local_private_search_documents to knudg_app, knudg_worker;
grant select, insert on local_private_value_events to knudg_app, knudg_worker;
