# Knudg Backlog

The implementation queue for Knudg, aligned to the current model.

Design source of truth:
- [docs/architecture/target-model.md](../docs/architecture/target-model.md) — what Knudg is and the one-pipe backend shape.
- [docs/architecture/semantic-search.md](../docs/architecture/semantic-search.md) — pillar ④ design.

The older milestone task files (m0/m1/m3, experience-domains, backend-roadmap,
production-readiness, core-status) described a private-first, human-gated,
M0–M6 model that the reshape replaced. They were retired; see git history if you
need the prior plan. Where anything conflicts, target-model.md wins.

## The four pillars (and where they stand)

1. **Agents create knudg** — proactive write offer at solved-work boundaries
   (SKILL.md completion self-check). Done.
2. **Share** — the public/Team shared pipe. Deferred on purpose until the solo
   loop is proven useful (do not build the sharing side first).
3. **Strip non-public info** — deterministic redaction at capture + the GLM
   filter queue (40 rpm throttle). The queue exists; it still needs rewiring so
   ingestion feeds it directly (see ③ below).
4. **Semantic search** — hybrid FTS + pgvector, opt-in. Done (storage + functions
   + API), pending a full HTTP-level e2e test.

## Done in the reshape (2026-06)

- Adopted target-model.md as the core map.
- Removed the human-gate / on-backend-private / broader-domain machinery:
  publication-candidate, consent-review UI, private-retention completion,
  redacted-experience storage, candidate-payload-facets, and ~94 over-scope gate
  scaffolds. The capture → FTS search → revoke/purge loop and the GLM filter
  queue stayed intact.
- ① writer now offers a knudg proactively at solved-work boundaries (no hook,
  no auto-write).
- ④ semantic search: dev Postgres → `pgvector/pgvector:pg16`; migration 0017
  (embedding column + HNSW); migration 0018 (`set_embedding`, `vector_search`,
  additive — FTS functions untouched); API embed seam (fastembed BGE-small/384,
  opt-in `KNUDG_EMBEDDING_ENABLED=1`) + hybrid merge.
- Verified: 206 tests pass (2 pre-existing `test_m0_schema` failures are
  unrelated — see Known issues).

## Next slices (ordered)

1. **Dogfood ① + ④.** Turn on `KNUDG_EMBEDDING_ENABLED=1`, use the loop for real,
   and judge whether hybrid retrieval and the write offer actually help. This
   gates whether ③ (sharing) is worth building.
2. **③ ingestion → queue rewire.** Make capture enqueue every knudg into the GLM
   filter queue (the project's "everything goes through the filter" model),
   decoupled from the old publication path. This is the spine of the shared pipe.
   Only after the solo loop proves useful.
3. **Shared pipe / serving** (Public + Team servers as one pipe with
   filter+access config) — the heavy ② work; after ③.
4. **Doc consolidation.** Reconcile or retire docs that predate target-model:
   `docs/architecture/implementation-readiness.md`, the product/RFC docs
   (`docs/rfcs/0004-*` + the adversarial review reports), and the README link to
   `docs/product/codex-for-oss-readiness.md`. Mind README/internal links.
5. **Semantic-search e2e test.** HTTP-level: publish with embedding on → embedding
   stored → hybrid served (model-gated skip). See semantic-search.md.

## Known issues / cleanup

- Two pre-existing `test_m0_schema` failures (`audit_insert_function...`,
  `knudgctl_local_private_capture_search_revoke_purge_vertical_loop`, exit 3).
  Unrelated to the reshape (migrations/knudgctl unchanged); needs separate
  investigation.
- `tests/test_knudg_closed_api.py::seed_closed_api_private_retention_proof` is a
  now-unused dead helper; remove when convenient.
- dev Postgres image changed to pgvector; the existing data volume needed a
  `REFRESH COLLATION VERSION` (dev-only artifact of the image switch).

## Operating rules

- YAGNI gate: before adding a new surface/gate/table/capability, confirm the user
  asked for it *this iteration*. If not, don't build it. (This is what the
  reshape was undoing.)
- private stays local; the backend is the shared corpus only.
- The GLM filter is the sole publication gate; its quality is the safety boundary.
- Revoke must always work (un-share after the fact).
- Prefer vertical slices that exercise the real backend; keep changes verifiable.
