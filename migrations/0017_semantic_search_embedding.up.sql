-- Pillar 4 (semantic search) foundation.
-- Adds pgvector and a nullable embedding column on the local-private search
-- documents. The embedding is best-effort: rows without an embedding still work
-- through FTS. Hybrid (FTS + cosine) ranking and the embedding provider are
-- wired in later steps; this migration only establishes the storage + index.
--
-- Dimension 384 matches the default local embedding model (BGE-small class) from
-- docs/architecture/semantic-search.md. Changing the provider to a different
-- dimension requires a new migration.
create extension if not exists vector;

alter table local_private_search_documents
  add column if not exists embedding vector(384);

create index if not exists local_private_search_documents_embedding_idx
  on local_private_search_documents
  using hnsw (embedding vector_cosine_ops);
