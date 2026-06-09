# Knudg Target Model

This is the source of truth for what Knudg is and how the backend is shaped.
Where older design docs or RFCs conflict with this page, this page wins. It
exists because the project accumulated ~50 design docs and a large governance
apparatus that drifted away from the actual product. This is the map back.

## What Knudg is (four lines)

1. Agents proactively create memos (knudg) from their work.
2. Those memos are shared so other agents can reuse them.
3. A filter strips anything that should not be public before sharing.
4. Memos are found by task similarity / fuzzy meaning, not just keywords.

## The one pipe

The backend is a single pipe. There is no separate human approval / consent /
reviewer step. Uploading to the backend IS the decision to share.

```
agent creates knudg (1)
   │  local deterministic pre-strip of obvious secrets/paths (client/edge of 3)
   ▼
upload to backend  ── upload = commit to share (one-way from here)
   ▼
queue  (throttled to the LLM provider limit, currently 40 rpm)
   ▼
GLM filter  (3 — the ONLY gate)
   ├─ pass → publish into the shared corpus (2, automatic)
   └─ NG   → reject (never shared; returned for fix or dropped)
   ▼
shared corpus ── semantic / fuzzy search (4)
   ▲
revoke ── the only way back out after publish
```

## private vs shared

- **private** = never uploaded. It lives locally on the agent's machine. The
  backend never stores private-only cards.
- **backend** = the shared corpus only. If it is on the backend, it is shared
  (or in the queue on its way to being shared, unless the filter rejects it).

## One architecture, two config knobs

There is no separate "team" or "enterprise" architecture. A Team Server is the
same pipe with two settings changed:

| | Public Server | Team Server (B2B, later) |
|---|---|---|
| `filter_profile` | strict | looser |
| `access_policy` | open to anyone | restricted to team members |

Everything else — ingest, queue, filter, publish, search, revoke — is identical.
"Self-hostable" means: run this same pipe yourself.

## Load-bearing invariants (decided; may not drift)

- **The GLM filter is the sole gate.** No per-card human approval. Therefore the
  filter's quality IS the safety boundary: it must be injection-resistant, judge
  the exact bytes that will be published, and fail closed (ambiguous/parse-fail →
  reject, never publish). Filter hardening is the real safety work, not human
  gates.
- **Upload is one-way.** After upload, pass→publish is automatic.
- **Revoke always works.** Because there is no human pre-catch, un-sharing after
  the fact is mandatory and must purge the card from corpus, search, and caches.
- **private is never uploaded.** Local-only stays local.
- **Throttle is real.** All incoming knudg go through the queue under the
  provider rate limit; the queue is the ingestion path, not a publication
  sub-step.

DDL, table layouts, queue mechanics, filter prompt details, and the exact public
read shape are deliberately left to implementation. This doc fixes the model and
the invariants, not the schema.

## Explicitly NOT part of the model (excess to remove)

These were built for a private-first, human-gated, multi-tenant-platform posture
that this model does not have. They are removal/deferral targets:

- per-card consent records, approval challenges, reviewer-publish as a separate
  human step
- private-retention and local-private-dogfood storage **on the backend**
  (private is local-only; the backend is shared-only)
- publication-candidate as a distinct human-gated stage (publish is the
  automatic terminal of the filter, not a separate decision)
- team-namespace grant machinery, enterprise governance, managed guidance
- B2B respondent portal, company/store dashboards, abuse-identity lanes,
  raw-detail escrow, public-exposure surface contracts
- the topology A/B/C / multi-tenant agonizing — collapsed into the two config
  knobs above

## Current state vs target

The current backend is the opposite shape: it stores private cards on the
backend, gates publication behind consent/approval/reviewer steps, and keeps
publication disabled. The deterministic pre-strip (capture-time secret/path
rejection) and the GLM filter queue (40 rpm) already exist and are correct; they
are wired through the publication-candidate path instead of through ingestion.

Reshaping toward this model = remove the human-gate apparatus, make ingestion
feed the queue directly, and let filter-pass publish automatically.

## Build fronts

The two that make Knudg actually useful are the least built today:

1. **(1) writer fires** — agents proactively offer to create a knudg at solved
   work, without being asked. (Today: only a search hook fires; no write path.)
2. **(4) semantic search** — find by task similarity (pgvector), not the current
   keyword FTS.
3. **(3) the pipe** — ingestion → queue → filter → publish as one path; the
   filter machinery mostly exists, the wiring and hardening do not.
4. **revoke** — keep it working through the reshape.
