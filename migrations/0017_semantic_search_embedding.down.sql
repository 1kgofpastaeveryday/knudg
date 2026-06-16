drop index if exists local_private_search_documents_embedding_idx;

alter table local_private_search_documents
  drop column if exists embedding;

-- The vector extension is intentionally left in place; dropping it would fail or
-- cascade if any other object comes to depend on it.
