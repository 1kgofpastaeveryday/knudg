# Adversarial Design Review — 2026-06-09 (Round 2)

## Review Configuration
- Date: 2026-06-09
- Target: `docs/rfcs/0004-public-publication-path.md` (Draft **v2**, revised after round 1)
- Round: 2 of 2
- Tier: full intended (6 lanes); **4 effective lanes** — see caveat.
- Effective reviewers:
  - Coherence Auditor (claude-sonnet-4-6) — completed
  - Schema & Data Integrity (gpt-5.4 codex) — completed
  - Implementation Reality (gpt-5.4 codex, relaunched after usage-limit) — completed
  - Attack Surface + Assumption Challenger (claude-sonnet-4-6, combined fallback) — completed
- **Caveat (honest):** Attack, Production-Stress, and Assumption codex lanes hit the OpenAI Codex **usage limit** mid-run (resets ~Jun 11). Effective coverage = 2 codex lanes (Schema, Implementation) + 2 independent sonnet lanes (Coherence; combined Attack+Assumption). Production-Stress was not independently re-run in round 2 — its round-1 findings (queue idempotency, lease safety, DLQ) are echoed by Schema/Attack/Impl here. Multi-model breadth is lower than round 1.

## Scoring Summary (round 1 → round 2)

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted | Verdict |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Coherence | 5 | 4 | 5 | 5 | ~4.8/10 | borderline (no axis ≤3) |
| Schema & Data Integrity | 4 | 3 | **2** | 4 | 3.4/10 | **FAIL** (Impl ≤3) |
| Attack + Assumption | 5 | 5 | 6 | 5 | 5.25/10 | borderline (no axis ≤3) |
| **Round-2 effective avg** | ~4.7 | ~4.0 | ~4.3 | ~4.7 | **~4.5/10** | — |
| Round-1 avg (6 lanes) | 2.7 | 2.3 | 3.0 | 2.7 | **~2.7/10** | FAIL |

**Verdict: NOT YET ACCEPTED, but a large improvement (≈2.7 → ≈4.5).** The design *decisions* now survive review; the RFC is held back by **not binding those decisions to the concrete shipped SQL/claim/queue/validator surfaces**, plus a few genuine residual risks the operator must own.

## Round-1 Blocker Resolution (consensus across the 3 lanes)

| Blocker | Status | Note |
|---|---|---|
| C1 kill switch (withdraw vs revoke) | **RESOLVED** | PD-6 re-centers on `revoked`; withdrawal is pre-publish only |
| C2 public-card creation missing | **PARTIAL** | phase-0 added, but doesn't yet match exact M0 creation columns/ledger (SDI-1) |
| C3 standing "publish all passing" | **RESOLVED** | PD-5 rejects it; per-artifact only |
| C4 reviewer actor model | **PARTIAL** | `operator_reviewer` named but not a seeded `actor_roles` value and not enforced in `knudg_set_claims` (SDI-4/ATK-01/N-1) |
| C5 exact-artifact digest TOCTOU | **PARTIAL** | tuple named in prose; no physical authority record/constraint (ATK-03/SDI-2) |
| C6 loopback-public category error | **RESOLVED** | publish/serve split removes it |
| C7 "already designed in M0" overstatement | **RESOLVED** | v2 now calls it net-new with a logical-vs-physical table |
| C8 PR-005/RB-LP-001 authority | **RESOLVED (publish-route)** | PD-8 requires a manifest entry; but manifest schema can't express "publish yes/serve no" (SDI-7) and PR-005 publication gates may still apply to `reviewer_publish` (ASM-04) |
| C9 published vs indexed visibility | **RESOLVED** | RFC stops at `published`, serves nothing |
| C10 judge injection / permissive parser | **PARTIAL** | PD-8 *claims* strict-JSON/exact-bytes, but shipped code still has the label/regex fallback + compact surrogate (ATK-02) |
| C11 queue idempotency/lease/outbox | **PARTIAL** | `complete_final_filter_job` still completes by id only (no lease CAS, ATK-05); `final_filter_jobs` is not the M0 outbox (ATK-06) |
| C12 hold/reject leaves consent armed | **PARTIAL** | disarm rule stated, not a persisted termination on the authority row (SDI-2) |

## Convergent Remaining Work (Tier 1 — before implementation past phase 0)

These are "bind the decision to the shipped surface," verified against real code/SQL:

1. **Auto-trigger default OFF; name the single-credential risk (ATK-01, ASM-02, N-1, SDI-4).** `operator_reviewer` does not eliminate "steal `KNUDG_OPERATOR_TOKEN` → pre-arm → pass → auto-publish"; it formalizes it. `knudg_set_claims` enforces reviewer authority for no `actor_role='reviewer'` today. Make manual the default until PR-003; state token-compromise as an explicit OPEN risk; name single-principal publication as a nominal (not independent) reviewer.
2. **Make `consent_records` THE publish authority (ATK-03, SDI-2, C5/C12).** Add scope-specific `NOT NULL`/`CHECK` for `public_publication` (require `card_version_id`, `challenge_id`, `challenge_digest`); decide where `request_digest` binds (consent payload vs new column). Disarm = persisted consent termination on non-pass/content-change. No vague "publish-authority record."
3. **Judge hardening is a current hole, not done (ATK-02, C10).** Shipped `parse_final_filter_model_content` still upgrades free-text `approved`/`ok`/`safe` to `pass`; judge gets `compact_final_filter_candidate`, not exact bytes. RFC must frame these as removals required in phase 3 (fail to `hold` on non-JSON; feed canonical full payload bytes), not as already-satisfied.
4. **Queue fixes are prerequisites (ATK-05, ATK-06, SDI-5, C11).** Add `AND lease_token = %s` to `complete_final_filter_job`; name the `final_filter_jobs` → M0 `outbox_events`/`jobs` migration as an explicit phase-0/4 prerequisite (current table has no event-stream linkage / idempotency row).
5. **Phase-0 must be the exact M0 creation transaction (SDI-1, SDI-3).** List every required `experience_cards` column + `event_stream_positions` ledger row; and add a **public payload contract** first — `card_payload_v1_is_valid()` today accepts only `local_private_dogfood` or synthetic M0 payloads, not a public-from-private card.
6. **Read-path exclusion for published public cards (ATK-04).** `private_cards_view` and `derived_from_private_card` edge reads must not expose the new public card UUID via existing operator-token routes; negative test required.
7. **Update the public-exposure contract/validator in the same change (SDI-6).** Today `validate_public_candidate_conversion` rejects `stored_public_card=true`; v2's "store but don't serve" needs that contract/schema updated or an explicit, justified bypass.

## Decide Before Implementation (Tier 2)

- **Launch-gate-manifest granularity (SDI-7):** the schema opens/closes whole gate IDs; "publish yes / serve no" needs a sub-gate/slice field or a new gate ID — else PR-005 is still narrowed by prose.
- **PR-005 scope (ASM-04):** confirm whether PR-005 hostile-card/injection release gates apply to *committing* `published` rows, not only serving. If yes, they gate phase 3/4.
- **Capability field (SDI-8):** define `publish_lifecycle` field location, schema version bump, client/SKILL/test migration, backward-compat (validators require boolean `features.*` today).
- **Resolve D-A/D-B vs PD-1/PD-2 (N-2):** "Remaining Decisions" reopen things PD-1/PD-2 mark decided — pick one state.

## Future Risk (Tier 3 — operator must own these bets)

- **One-way-door (ASM-01, ASM-06, N-3, ASM-05):** `published` public cards + `artifact_digest`-bound consent are durable/immutable. Any later `card_versions` schema or policy-version change orphans existing consent and forces per-card revoke+re-publish. Revoke must explicitly terminate the `public_publication` consent. Define the migration contract and the `derived_from_private_card` edge uniqueness before committing the first public row.
- **"Public" with no reader (ASM-03):** a `published`-but-unserved card is operationally identical to `approved_private` until the serve RFC ships. Its value is *contingent* on the serve RFC. This is an architectural bet the operator should make explicitly.

## Recommendation
v2 is sound in direction and structure. Do **one more targeted revision (v3)** that (a) applies the mechanical bind-to-surface fixes 1–7 + Tier-2, and (b) surfaces the Tier-3 operator bets as explicit acknowledgements/decisions — then implementation may begin at **phase 0 only** (public payload contract + creation transaction + read-path exclusion), with auto-trigger OFF and `reviewer_publish` manual until PR-003. Codex usage resets ~Jun 11 if a full 6-lane re-review of v3 is wanted; otherwise a sonnet-only spot re-review can confirm v3.

## Raw lane outputs
`coherence2.md`, `schema2.md`, `attack-assume2.md` (review temp dir).
