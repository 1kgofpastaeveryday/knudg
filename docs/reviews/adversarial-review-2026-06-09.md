# Adversarial Design Review — 2026-06-09

## Review Configuration
- Date: 2026-06-09
- Project: knudg (local repo root)
- Target: `docs/rfcs/0004-public-publication-path.md` (public publication path)
- Focus: safety + data-model; "auto-publish on LLM pass"
- Tier: full (6 reviewers)
- Reviewers: 6 total
  - gpt-5.4: Attack Surface, Production Stress, Assumption Challenger
  - gpt-5.4 (fallback for gpt-5.3-codex, unsupported on this account): Implementation Reality, Schema & Data Integrity
  - claude-sonnet-4-6: Coherence Auditor
- Lane-diversity caveat: the two intended gpt-5.3-codex lanes were run on gpt-5.4 because `gpt-5.3-codex` is rejected for this ChatGPT account. Five of six lanes therefore share a model family; convergence between same-family lanes is weaker evidence than cross-family convergence. The Coherence lane (sonnet) is the only independent family.

## Scoring Summary

| Reviewer | Correctness (3x) | Completeness (2x) | Implementability (2x) | Resilience (1x) | Verdict |
|----------|:---:|:---:|:---:|:---:|:---:|
| Attack Surface | 2 | 2 | 3 | 1 | FAIL |
| Production Stress | 2 | 2 | 3 | 2 | FAIL |
| Assumption Challenger | 3 | 2 | 3 | 2 | FAIL |
| Implementation Reality | 2 | 2 | 2 | 3 | FAIL |
| Schema & Data Integrity | 2 | 2 | 2 | 3 | FAIL |
| Coherence Auditor | 5 | 4 | 5 | 5 | (no axis ≤3, but 47.5% weighted) |
| **Average** | **2.7** | **2.3** | **3.0** | **2.7** | — |

**PASS/FAIL: FAIL.** Correctness (2.7) and Completeness (2.3) average ≤ 3. Overall weighted average ≈ **2.7/10**.

Diagnosis (cross-lane): the RFC is not wrong in *direction* — no reviewer said public publication is impossible. The repeated finding is that the RFC **speaks in an implementation-ready tone while leaving authority, state-machine, and creation-path questions unresolved, and routes around documented hard gates (PR-005 / RB-LP-001) without claiming authority to do so.** It is prematurely executable, not misdirected.

## Cross-Model Convergence

Issues raised by 3+ lanes (highest priority):

| # | Issue | Lanes | Tier |
|---|-------|-------|------|
| C1 | **Kill switch / rollback wired to wrong state.** `publication_withdrawn` only exists pre-publish; live `published`/`indexed_*` cards exit via `revoked`. "Withdraw all public cards" cannot recall served copies. | Attack, Prod, Assume, Schema | T1 |
| C2 | **Public-card creation path is missing.** The existing candidate is an ephemeral JSON+digest, not a new public `experience_cards`/`card_versions` row via `complete_publication_from_private_request`. OQ5 must be a prerequisite, not a "confirm". | Impl, Schema, Coherence, Prod, Assume | T1 |
| C3 | **Standing "publish all passing" mode is incompatible with M0 consent** (exact artifact/policy/challenge binding; scopes never inherit). Must be rejected, not deferred to a UX question. | Attack, Prod, Assume, Schema, Coherence | T1/T2 |
| C4 | **Actor model for auto-triggered `reviewer_publish` is unspecified.** M0 requires `reviewer` actor role; automation is `%worker`; current auth = static bearer token possession, not a live reviewer proof. | Attack, Impl, Schema, Coherence | T1 |
| C5 | **Auto-publish not bound to the exact approved artifact.** Filter digest is `{candidate, policy_context}` only; a stale/repaired pass can publish a different artifact than the one approved (digest TOCTOU). | Attack, Prod, Schema | T1 |
| C6 | **"Loopback public" / "minimal serving" is false.** Existing closed API is UUID-addressed and hardcoded to `approved_private` private bodies; topology A/B/C must be resolved before any serving design. Possibly a category error vs existing private retrieval. | Assume, Schema, Attack, Impl | T1/T2 |
| C7 | **"Already designed in M0" overstates readiness.** `public_card_handles` and `complete_publication_from_private_request` are *deferred* logical contracts, not shipped infrastructure; `derived_from_private_card` edge isn't even seeded in the migration. This is net-new work, not wiring. | Impl, Coherence, Assume | T1/T2 |
| C8 | **RB-LP-001 / PR-005 gate authority not acknowledged.** RB-LP-001 blocks ANY public route (incl. static prototype); PR-005 is binary-blocked with no documented partial-open path. The RFC unilaterally narrows a hard gate. | Coherence, Prod, Assume | T1 |
| C9 | **`published` ≠ public-readable until `indexed_*`.** A handle valid at `reviewer_publish` bypasses the post-index public boundary in the visibility matrix. | Attack, Assume, Schema | T2 |

Issues raised by 2 lanes:

| # | Issue | Lanes | Tier |
|---|-------|-------|------|
| C10 | **GLM-5.1 judge is prompt-injectable + permissive parser** accepts label-only output as `pass`; filter sees a compact surrogate, not the exact published bytes. Auto-publish makes `pass` the de-facto release control. | Attack, Assume | T1 |
| C11 | **Queue is not idempotent/lease-safe;** `pass→publish` has no M0 event/outbox anchor; bound runtime role (`knudg_api_app` NOLOGIN) is unsatisfiable. | Prod, Impl, Schema | T1 |
| C12 | **`hold`/`reject` leaves publication consent armed;** non-pass or content change must force `approval_digest_invalidated` + fresh challenge. | Attack, Schema | T1 |

## Tier 1 — Immediate Fix Required (before RFC acceptance)

1. **Redesign emergency stop around revocation, not withdrawal (C1).** Define a post-publish revoke path: route stop → handle invalidation → tombstones → index removal → cache purge → reconciliation + verification queries. State explicitly "serve-stop is not rollback."
2. **Make public-card creation phase 0 (C2/C7).** One transaction creating the public `experience_cards` row, first public `card_versions` row, `derived_from_private_card` edge, `card_created` event, and idempotency row — via `complete_publication_from_private_request`. First fix the base migration so `derived_from_private_card` is seeded in `card_edge_types`. Close OQ5 as "false: candidate is not the first public version."
3. **Reject standing auto-publish mode (C3).** Per-artifact pre-arm only. Standing mode = a different consent model requiring a separate RFC. Remove it as a candidate.
4. **Name the actor/authority model (C4).** Specify the role/principal that executes auto-triggered `reviewer_publish` and prove the DB transition trigger accepts it; or keep `reviewer_publish` manual until PR-003 trusted reviewer authorization exists. Bearer-token possession is not reviewer authority.
5. **Bind publish to the exact approved artifact (C5/C12).** Publish must consume an immutable authority record keyed by the full M0 tuple (artifact_id, artifact_digest, policy_version/digest, challenge_id/digest) + final-filter request digest. Any non-pass or content change disarms and invalidates the approval.
6. **Acknowledge PR-005 + RB-LP-001 authority (C8).** Either define a manifest-backed gate/slice that authorizes `operator_public_single_tenant`, or keep `publication: disabled`. The RFC cannot unilaterally narrow a binary-blocked gate.
7. **Harden the injection gate + filter the exact bytes (C10).** For publication decisions: strict schema-valid JSON only (remove label/regex fallback), prompt-injection evals against the judge itself, and require the judge to evaluate the exact stored/served artifact bytes for the published digest.
8. **Put `pass→publish` on a real M0 event/outbox with idempotency + lease-token CAS (C11).** Not the current side-channel `local_private_value_events` queue.

## Tier 2 — Decide Before Implementation

- **Resolve reader topology A/B/C first (C6);** specify whether first-slice reads happen at `published` or only after `indexed_*` (C9). Possibly split "publish the artifact" from "serve the artifact" into separate RFCs.
- **Fix the RFC's draft/decided ambiguity:** OQ1/OQ2 are listed open while the plan assumes R1 + topology A. Convert to explicit prerequisite decisions or make the plan conditional.
- **`public_card_handles` is a noun list, not a table contract:** define PK, composite FK with `tenant_id`, opaque-handle uniqueness, one-active-handle rule, expiry/revoked invariant, and a machine-checkable no-internal-id-exposure negative test.
- **Define the capability-label schema:** `publication` is boolean today and validators reject non-boolean / non-local publication. `operator_public_single_tenant` needs a versioned schema + client/test/SKILL.md migration.
- **Reframe "already designed in M0"** into (a) accepted logical contracts vs (b) shipped physical infra; everything in (a)-not-(b) is net-new.
- **Injection threshold floor (OQ4):** state a non-zero floor + timing ("set before phase 3, recorded in launch-gate-manifest before phase 4"). "Private launch-control material" without a floor is not a gate.
- **Show the SKILL.md diff** for the #2 writer change so the non-weakening claim is reviewable; address the `Accept` + auto-publish term-consistency issue.

## Tier 3 — Future Risk

- Public read function must explicitly exclude `derived_from_private_card` edges + provenance/digests/timestamps (correlation-to-private risk). Define a strict public-read allowlist schema.
- Add domain allowlist (`technical_work`, `public_experience_candidate`) to `reviewer_publish` recheck.
- Verdict cache key must include model/provider/prompt/gate version so a cached `pass` can't survive requalification.
- Add enforcement tripwires (capability/config assertions) so topology B fails closed before PR-004, and deferred PR-005 gates re-activate when a second reader/contributor appears — not prose-only deferral.
- `reviewer_publish` should get a reserved safety-critical queue lane, not the shared final-filter pool.

## Statistics
- Lanes: 6 (5 FAIL by per-axis threshold; Coherence above per-axis threshold but 47.5% weighted)
- Convergence (3+ lanes): 9 clusters; (2 lanes): 3 clusters
- Overall weighted average ≈ 2.7/10 → **FAIL**

## Recommended Next Step
Do **not** start implementation. The direction (R1 over R2; single-operator first) survives review, but the RFC needs one revision round that (a) turns OQ1/OQ3/OQ5 into decided prerequisites, (b) adds public-card creation as phase 0, (c) redesigns the kill switch around revocation, (d) names the reviewer actor model, (e) acknowledges PR-005/RB-LP-001 authority, and (f) hardens the injection/exact-bytes gate. Then re-review before any code.

## Raw Reviewer Outputs
Full per-lane findings are preserved at:
- `attack.md`, `prod.md`, `assume.md`, `impl.md`, `schema.md`, `coherence.md`
  (under the review temp dir; copy into this repo if a permanent record is needed)
