# RFC 0004 - Public Publication Path (true public / anonymous readers)

## Status

Draft v4. Not accepted. Supersedes v1–v3.

This RFC deliberately does NOT specify full DDL or every mechanism. It fixes only
the decisions that are **irreversible once public data or public readers exist**,
or that are **safety/privacy boundaries**. Everything else is explicitly left
open for implementation, with rationale. Over-specifying a public-corpus design
before real readers exist tends to ossify the wrong abstractions; this RFC treats
chosen ambiguity as a design tool, not a gap.

Revision history:
- v1 publish-only "wire M0": FAIL (~2.7) — spoke as executable, routed around gates.
- v2 publish/serve split: ~4.5 — but publish-without-serve ≈ `approved_private`.
- v3 publish+serve, topology B (operator's own authenticated agents): ~5.2 — but
  three review rounds converged that topology B is authenticated single-tenant
  retrieval (≈ M2/M3), not public publication.
- v4 (this): operator decided the real destination is **true public — other
  people/agents read the operator's published cards (topology C)**. This is the
  README's stated public-good vision. It is the heaviest path, gated mainly by
  PR-005, and v4 reframes the work and the prerequisite stack accordingly.

## Destination (decided)

True public corpus: a card the operator publishes becomes readable by anonymous
or third-party agents/people, as untrusted reusable experience. This is what the
README means by "public-good infrastructure for sharing agent experience," and
what `What Knudg Is Not` constrains ("not a public publishing system without
explicit consent and review").

Reader auth is therefore **not** the gating problem (readers are anonymous). The
gating problem is **what is safe to expose to the world and how it is consented,
reviewed, and revoked** — i.e. PR-005, not PR-004.

## Design Philosophy: Fixed vs Deliberately Open

The acceptance bar for v4 is NOT "a developer can build it without thinking." It
is "every irreversible or safety/privacy decision is made; every reversible
detail is left to the implementer with its invariant stated." Reviewers who
demanded full DDL appendices are asking for premature commitment; v4 declines
that on purpose and instead pins invariants.

### Fixed now (irreversible once public, or safety/privacy boundary)

These cannot be cheaply undone after the first public card is served. They are
decided here and may not drift during implementation.

1. **Public = a new card, never a visibility flip.** Publication creates a new
   `experience_cards` row in the public branch via
   `complete_publication_from_private_request`, linked to the private source by
   a non-public `derived_from_private_card` edge. The private row is never
   mutated; private-retention consent is never reused as public consent.
   (Irreversible identity decision; a flipped private card can never be cleanly
   separated later.)
2. **Consent is exact and per-artifact.** `public_publication` consent binds the
   exact published artifact digest, policy, and challenge. No standing/blanket
   approval. (You cannot retroactively narrow what the world was allowed to see.)
3. **Revocation is the kill switch and it is complete.** Live public cards exit
   via `revoke` (not `publication_withdrawn`). Revoke terminates the consent row,
   fences every read path (tombstone-first), invalidates handles, removes index
   projections, and purges caches. Un-publishing must always work. (Safety: the
   one thing that must never be "impossible to undo.")
4. **Deny-by-default public exposure boundary.** Public reads expose only an
   explicit allowlist; everything else — internal IDs, digests, timestamps,
   provenance, contributor identity, `derived_from_private_card` lineage,
   private-source correlation — is excluded. Single-observation negatives,
   person-level details, selection status, exact dates, account/receipt IDs, and
   private circumstances are rejected from public serving. (Privacy leaks are
   irreversible.)
5. **Hostile-card / prompt-injection safety gates BEFORE any publish.** A public
   card is consumed by other agents as untrusted evidence; one poisoned card is
   an injection vector for every reader. The judge must accept only strict
   schema-valid JSON (no free-text label upgrades to `pass`), evaluate the exact
   published bytes, and pass an injection/hostile-card gate; a kill switch +
   revoke rollback must exist. (Irreversible exposure once served.)
6. **Schema-versioned public readers (one-way-door posture).** Published cards
   are immutable and consent is digest-bound; therefore the serve path MUST read
   cards by their stored `card_schema_version`, so a future schema/policy change
   does not orphan existing consent or force mass re-publication. (This is the
   decision that KEEPS future schema choices cheap — it preserves ambiguity
   deliberately rather than locking the payload shape now.)

### Deliberately left open (reversible / implementation-shaped — invariant only)

These are NOT decided here. Locking them now would ossify. Each carries only the
invariant the implementation must satisfy; the form is the implementer's call,
revisable with feedback.

- **`public_card_handles` DDL.** Invariant: opaque, non-enumerable, not derivable
  from internal IDs, revocable, one active per published version+generation.
  Columns/index strategy/entropy mechanism: open.
- **Index projection internals** (`indexed_hot`/`indexed_main`). Invariant:
  rebuildable from canonical rows + event log; revocation-epoch aware. Table
  shape, ranking, hot/main split mechanics: open.
- **Public-read field allowlist contents.** Invariant: deny-by-default; the
  exclusions in Fixed #4 hold. The exact field list will evolve; do not freeze it.
- **Cache TTL / freshness.** Invariant: a served card must never outlive its
  revocation epoch (stale-after-revoke is forbidden). Concrete TTL: ops config.
- **Queue mechanics for publish work.** Invariant: idempotent, lease-token CAS,
  reconcilable from the event log, on a reserved safety lane. Whether it reuses
  M0 outbox tables or a migrated form: open (but it must not be an
  unreconcilable side channel like today's `final_filter_jobs`).
- **Capability signaling shape.** Invariant: serving state is explicit and
  fail-closed by default. JSON field name/versioning: open.
- **Reviewer supply specifics.** Invariant: PR-005 reviewer-capacity gate is met
  before public serving. Exact staffing/rota: ops, not this RFC.
- **Auto-trigger on `pass`.** Default OFF; built only after PR-003. Whether to
  ever enable it for true-public is itself deferred (for an anonymous corpus,
  manual reviewer publish is likely the right long-term default).

### What v4 does NOT pretend

The shipped code holes the reviews found (judge label fallback, compact
surrogate, `complete_final_filter_job` lacking lease CAS, `derived_from_private_card`
unseeded, no public payload validator, no `public_card_handles`) are **real
prerequisite work**, not "already done." Naming them is honest; they remain
unbuilt because nothing is implemented yet. They are listed as prereqs, not
hidden.

## Prerequisite Stack for True Public (reprioritized for topology C)

The heavy part of true public is PR-005, not PR-004.

1. **PR-005 core (the real work):** public privacy attack model (single-
   observation/PII/correlation rejection; rare-fingerprint probes), hostile-card
   / prompt-injection release gate (corpus, golden tests, pass-rate floor,
   model/provider requalification, kill switch, rollback drill), RB-LP-001 public
   route incident runbook, and reviewer-capacity gate. Manifest must authorize a
   PR-005 sub-gate (whole-gate today; add granularity).
2. **PR-003 trusted consent completion** for `public_publication` (the repo today
   completes only private-retention; all publication-completion flags are false).
3. **Public payload contract migration** — the current validator accepts only
   `local_private_dogfood`/synthetic; a public redacted payload needs its own
   schema branch.
4. **PR-004 for the WRITE/admin side only** (operator/contributor and reviewer
   auth), not for the anonymous reader. Lighter on the critical path than v3
   implied.
5. **Judge + queue hardening** (Fixed #5 + queue invariant) before publish.

Abuse-identity lane: deferrable with an enforced tripwire while the operator is
the sole contributor; becomes hard the moment third-party contributors exist.

## Lifecycle (decisions, not DDL)

- Creation: Phase-0 atomic new-public-card transaction (Fixed #1), event-sourced
  (`card_created` + event-stream ledger + idempotency), under the public payload
  contract. Exact columns follow M0's existing creation pattern — not re-specified
  here; the invariant is "no committed card without a current version, lineage
  edge, and event."
- Approval: exact-bound `public_publication` consent on `consent_records`
  (Fixed #2); add scope `NOT NULL`/`CHECK` so the binding cannot be null-bypassed
  — this constraint IS fixed because a loose consent row is an irreversible
  authority gap.
- Reviewer authority: M0 `reviewer` actor role, enforced by a durable grant that
  `knudg_set_claims` checks fail-closed (today it enforces only `%worker`). For
  an anonymous public corpus, independent review matters more than in the solo
  case — name whether the operator is the sole reviewer (nominal two-party) and
  what PR-005 reviewer-supply requires before scale.
- Publish: `reviewer_publish` runs the full serializable protocol + all rechecks
  (redaction, approval digest, safety metadata, domain allowlist, abuse gates) at
  transition time. Then index → serve by handle (Fixed #3/#4 boundaries).

## Phased Plan (gates first; details deferred)

0. PR-005 core acceptance (privacy model + injection gate + RB-LP-001 + reviewer
   capacity) and PR-003 consent completion and public payload contract and judge/
   queue hardening. No public card is created before these.
1. Public-card creation + exact-bound consent constraints + read-path exclusion
   (private routes/edge must not leak the public/private link). Manual only.
2. `reviewer_publish` + revoke-complete (consent termination + fence) — manual.
3. Indexing + public handles + deny-by-default public read + cache fence +
   RB-LP-001 live. Serving turns on here, behind the PR-005 manifest gate.
4. (Deferred, maybe never for true-public) auto-trigger.

DDL for handles, index projection, and the public read schema is produced at the
implementing phase, against the invariants above — intentionally not in this RFC.

## Open For The Operator

- D-A: confirm the abuse-identity tripwire is acceptable (defer while sole
  contributor) vs build it now.
- D-B: sole-reviewer-now vs PR-005 reviewer supply before serving — what scale
  triggers the supply requirement.
- D-C: is anonymous read truly the goal, or authenticated-third-party first (a
  middle that re-introduces reader auth)? v4 assumes fully anonymous.

## Non-Goals

- No standing auto-publish; no consent-scope aliasing; no visibility-flip
  publication; no private-row mutation.
- No premature DDL for reversible structures.
- Not describing the closed-launch loop as publication-ready.

## Companion: Writer Reminder (#2)

Unchanged; completion-time agent self-check to *offer* (not auto-write) a
candidate; no hooks/shell/auto-write. Exact SKILL.md diff ships with its own PR.
