-- Pillar 4: additive semantic-search functions.
-- These do NOT modify the existing FTS publish/search functions. The API layer
-- stores embeddings best-effort after capture and combines FTS + vector results
-- (hybrid) in application code, so the keyword path is unchanged and degrades
-- gracefully when embeddings or the embedding provider are absent.

-- Store/refresh the embedding for one captured search document.
create or replace function knudg_closed_private_set_embedding(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
  row_card_id uuid,
  row_card_version_id uuid,
  row_embedding vector(384)
)
returns table (
  card_id uuid,
  card_version_id uuid,
  embedded boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public, knudg_private, pg_temp
as $$
declare
  updated_count integer;
begin
  perform knudg_private.closed_private_require_namespace_scope(
    row_tenant_id,
    row_namespace_ids,
    row_principal_id,
    array['submit','admin']::text[]
  );
  update local_private_search_documents d
    set embedding = row_embedding
    from experience_cards c
    where d.tenant_id = row_tenant_id
      and d.card_id = row_card_id
      and d.card_version_id = row_card_version_id
      and c.tenant_id = d.tenant_id
      and c.id = d.card_id
      and c.namespace_id = any(row_namespace_ids)
      and d.lifecycle_status = 'captured'
      and d.purged_at is null;
  get diagnostics updated_count = row_count;
  return query select row_card_id, row_card_version_id, (updated_count > 0);
end;
$$;

-- Vector (semantic) search over active, non-revoked private docs that have an
-- embedding. Same active-doc filters and return shape as the FTS search; ranked
-- by cosine similarity above a floor.
create or replace function knudg_closed_private_vector_search(
  row_tenant_id uuid,
  row_namespace_ids uuid[],
  row_principal_id uuid,
  row_workspace_id text,
  row_query_embedding vector(384),
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
  if row_query_embedding is null then
    return;
  end if;
  if row_limit is null or row_limit < 1 or row_limit > 10 then
    row_limit := 3;
  end if;

  return query
  with active_docs as (
    select c.id as card_id, d.card_version_id, c.namespace_id,
      cv.payload_digest, c.outcome_type, c.quality_state, c.evidence_strength,
      c.updated_at, d.embedding
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
      and d.embedding is not null
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
  )
  select active_docs.card_id,
    active_docs.card_version_id,
    active_docs.namespace_id,
    active_docs.payload_digest,
    active_docs.outcome_type,
    active_docs.quality_state,
    active_docs.evidence_strength,
    greatest(round((1 - (active_docs.embedding <=> row_query_embedding)) * 10)::integer, 1) as match_score,
    array['semantic_similarity']::text[] as coarse_match_reason
  from active_docs
  where (1 - (active_docs.embedding <=> row_query_embedding)) >= 0.55
  order by active_docs.embedding <=> row_query_embedding asc, active_docs.updated_at desc, active_docs.card_id
  limit row_limit;
end;
$$;

-- Bound runtime wrappers (resolve the configured workspace binding, same as the
-- other closed-API wrappers). Embeddings are passed as text and cast to vector.
create or replace function knudg_closed_api_set_embedding(
  row_workspace_id text,
  row_card_id uuid,
  row_card_version_id uuid,
  row_embedding text
)
returns table (
  card_id uuid,
  card_version_id uuid,
  embedded boolean
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
  from knudg_closed_private_set_embedding(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    row_card_id,
    row_card_version_id,
    row_embedding::vector(384)
  );
end;
$$;

create or replace function knudg_closed_api_vector_search(
  row_workspace_id text,
  row_query_embedding text,
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
  from knudg_closed_private_vector_search(
    binding.tenant_id,
    array[binding.namespace_id]::uuid[],
    binding.principal_id,
    row_workspace_id,
    row_query_embedding::vector(384),
    row_limit
  );
end;
$$;

revoke all on function knudg_closed_api_set_embedding(text, uuid, uuid, text) from public;
revoke all on function knudg_closed_api_vector_search(text, text, integer) from public;
grant execute on function knudg_closed_api_set_embedding(text, uuid, uuid, text) to knudg_api_app;
grant execute on function knudg_closed_api_vector_search(text, text, integer) to knudg_api_app;
