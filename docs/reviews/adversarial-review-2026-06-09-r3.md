# Adversarial Design Review — 2026-06-09 (Round 3)

## Review Configuration
- Target: `docs/rfcs/0004-public-publication-path.md` (Draft **v3**, publish+serve unified, topology B)
- Round: 3
- Tier: sonnet-only (Codex usage exhausted, resets ~Jun 11). 3 effective lanes:
  - Coherence (claude-sonnet-4-6)
  - Schema & Data-Integrity + Implementation-Reality (claude-sonnet-4-6)
  - Attack Surface + Assumption Challenger (claude-sonnet-4-6)
- Caveat: single model family (sonnet). Cross-family corroboration unavailable
  this round. Treat convergence as same-family.

## Scoring (round 1 → 2 → 3)

| Lane | Correctness | Completeness | Implementability | Resilience | Weighted | Verdict |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Coherence | — | — | — | — | **6.75/10** | Conditional Pass (no axis ≤3) |
| Schema + Impl | — | — | **3** | — | ~3.x/10 | **FAIL** (Impl ≤3) |
| Attack + Assumption | — | — | — | — | **~5.4/10** | Not accepted, closeable |
| **r3 effective avg** | | | | | **≈5.2/10** | — |
| r2 avg | | | | | ≈4.5 | — |
| r1 avg | | | | | ≈2.7 | — |

Trajectory: **2.7 → 4.5 → ≈5.2.** Each round improved; design direction is now
"architecturally sound" per all three lanes. Two things still block acceptance:
(1) implementability — v3 is a decisions/contracts doc, but this repo's
convention (RFC 0001) requires a DDL appendix before a migration RFC is
"complete," and v3 has several "define explicitly" placeholders; (2) a recurring
strategic question (below) that three rounds have not dissolved.

## Round-2 Resolution (consensus)

Design-level (doc) items the lanes credit as resolved/handled in v3:
consent_records-as-authority, phase-0 exact creation contract, judge/queue
hardening reframed as prereqs, emergency-stop = revoke + consent termination,
single-principal named, auto-trigger OFF, manifest sub-gate, one-way-door
contract introduced, capability field named, PR-004 made a hard prereq.

Still open / newly surfaced:
- **Reviewer-grant enforcement is prose, no DDL** (Coherence partial, Schema:
  `knudg_set_claims` enforces only `%worker`; no reviewer-grant rule exists).
- **Code-level holes unchanged (expected for a doc):** judge label/regex
  fallback, compact-surrogate judge input, `complete_final_filter_job` lacks
  lease CAS, `final_filter_jobs` not on M0 outbox, `derived_from_private_card`
  unseeded, public payload validator branch absent. v3 correctly names these as
  prereq-0 work; they are not yet done because nothing is implemented.

## New in v3 (the serve half)

Tier 1 / Tier 2:
- **Public read field allowlist is undefined** — literally "define explicitly"
  without the definition (Schema). Must be concrete before serving.
- **No public-namespace DDL, no index-projection table** for `indexed_hot/main`
  (Schema). Serving has no storage contract yet.
- **`public_card_handles` still marked "deferred" in `data-model.md`** — v3
  brings it in scope but the canonical data-model wasn't updated; cross-doc
  contradiction (Schema/Coherence). Same-change update required.
- **Reader authz granularity unspecified (ATK-06):** which delegated agent may
  read which cards — "PR-004 then read" is not an authz model.
- **Serve-route token-theft/replay scope (ATK-07):** v3 defers all reader auth
  to PR-004 without naming what the serve route itself requires.
- **Revocation-fence cache TTL on handle→card lookup has no upper bound (ATK-08)**
  — a terminated-consent card could be served from cache.
- **Handle entropy floor** unspecified (enumeration).
- **PR-004 token shape** not specified (Schema/ATK).
- **Coherence T1-01:** topology B inserts into a `public` namespace that the
  data model treats as anonymous-web-eligible at index time; the auth boundary
  is serving-layer only, not schema-layer — must be stated explicitly or the
  schema implies broader exposure than intended.
- **Coherence T1-02:** no interim posture if PR-004 acceptance is delayed —
  risks silently recreating the v2 "published but unserved" problem.
- **Split the PR-005 deferral (Coherence T2-01):** hostile-card/injection gate
  must fire at Phase 3 even single-tenant; multi-tenant public-privacy gate is
  correctly deferred. v3 blends them.
- **D-A self-contradiction:** "Remaining Decisions" reopens PR-004 scope that
  the body already decided is a hard prerequisite.

## The Recurring Strategic Finding (3 rounds, unresolved by design changes)

Every round has returned a version of the same root, now sharpest from the
Assumption and Coherence lanes:

> **Topology B — the operator's own authenticated agents reading the operator's
> own reviewed cards — is authenticated cross-agent/cross-session retrieval over
> a single tenant. That is a private/team retrieval problem (≈ M2/M3), not public
> publication (M6).** The full public-publication machinery (public_publication
> consent, public_card_handles, reviewer publish, anonymous-eligible public
> namespace, indexing) is heavyweight for "my agents reuse my reviewed cards."

- r1: "loopback public is a category error vs existing private retrieval."
- r2: "publish-without-serve is identical to `approved_private` until a reader
  exists."
- r3: "topology B is authenticated cross-tenant-member retrieval; may warrant a
  simpler private cross-agent read RFC without the full consent/handle/indexing
  machinery — this should be an explicit operator decision, not an implicit
  architectural assumption."

This is not a bug in v3; it is the design process telling us the **container may
be wrong**. RFC 0004 ("public publication") keeps being asked to carry a need
that is really private cross-agent retrieval.

## Recommendation

v3's direction is sound and acceptance is "closeable," but before writing the
DDL appendix and closing the ~10 targeted gaps, resolve the strategic fork
(below) — because if the real need is private cross-agent retrieval, most of the
public-publication machinery the remaining gaps concern is unnecessary.

Either way, **PR-004 (non-local auth) is the true critical path** for any
network reader, public or private.

## Raw lane outputs
`coherence3.md`, `schema3.md`, `attack-assume3.md` (review temp dir).
