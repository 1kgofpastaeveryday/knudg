# Intent Crosswalk

This document maps the user's stated product intent in `user-said.md` to design requirements that prevent drift.

## Not Personal Memory

Intent:

- Knudg is not Claude Subconscious, Letta memory, or a local memory subscription.
- The core is shared search infrastructure and its database.

Design anchors:

- `README.md`: Product Positioning and Architecture Invariants
- `docs/architecture/overview.md`: local state limits
- `docs/product/strategy.md`: monetization excludes local memory as the primary value

Guardrail:

- Local state is only current-work query material, pending writer approval, and short-lived cache metadata by default.
- MVP value must be measured from the remote shared corpus excluding same-session local cache.

## Agent-Readable Experience Infrastructure

Intent:

- The product is "Stack Overflow + incident DB + reusable agent work patterns" for agents.
- MCP, CLI, and hooks matter before a polished human UI.

Design anchors:

- `README.md`: Core Roles and Initial MVP
- `docs/architecture/retrieval.md`: injection contract and delivery modes

Guardrail:

- Every wedge must expose agent-native access contracts before human-facing knowledge-base polish.
- Retrieved cards are evidence, not instructions.

## Thin Injection

Intent:

- The main agent prompt should not be polluted.
- Cards should appear only as concise candidate paths when useful.

Design anchors:

- `docs/architecture/retrieval.md`: Injection Contract
- `docs/architecture/security-privacy.md`: Retrieved Card Trust Boundary
- `docs/architecture/operations.md`: rollout controls

Guardrail:

- Default rollout moves through shadow and sidecar before inline hints.
- Inline injection has max cards, token budget, and no-suggestion fallback.

## Consent and Transparency

Intent:

- Publication requires explicit human approval.
- Users must understand what is and is not public.
- The published unit is a redacted reusable artifact, not a raw transcript.

Design anchors:

- `docs/architecture/security-privacy.md`: Privacy, Redaction, and Consent
- `docs/architecture/data-model.md`: consent records and derived artifacts
- `docs/architecture/overview.md`: canonical trail policy

Guardrail:

- Consent binds to the exact redacted artifact shown to the user.
- Derived artifacts need explicit inheritance rules or renewed approval.
- Raw artifact retention consent is separate from public-card publication consent.

## Candidate Paths, Not Truth

Intent:

- Public cards must not be treated as authoritative answers.
- Quality, deprecation, environment specificity, and contradictions are core.

Design anchors:

- `README.md`: Architecture Invariants
- `docs/architecture/data-model.md`: outcome types, quality state, edges, lifecycle
- `docs/architecture/retrieval.md`: abstention and display rules
- `docs/architecture/overview.md`: canonical trail reversibility

Guardrail:

- Search can abstain.
- Canonical trails remain reversible to source card versions.
- Contradictory fixes are linked, not merged.

## Store Unknowns and Failed Paths

Intent:

- Knudg should store "無知の知", failed paths, clarified uncertainties, and environment traps, not only successes.

Design anchors:

- `docs/architecture/data-model.md`: `outcome_type`, `known_unknowns`, `scope_limits`, `evidence_strength`
- `docs/architecture/retrieval.md`: unknown/constraint embeddings and quality gates

Guardrail:

- `failed_only`, `inconclusive`, and `unknown_clarified` cards are first-class searchable objects.

## Bigger Than Tech Worklogs

Intent:

- The first wedge can be developer tooling, but the product is about agent work broadly.

Design anchors:

- `docs/product/strategy.md`: wedge boundary statement
- `docs/architecture/data-model.md`: domain-general outcome fields

Guardrail:

- Wedge-specific examples must not hard-code the global ontology.

## Massive Shared DB and Economics

Intent:

- Indexing, writing, storage growth, and operating cost are core concerns from the beginning.

Design anchors:

- `docs/architecture/overview.md`: admission, dedupe, novelty, backlog controls
- `docs/architecture/operations.md`: cost telemetry and index migration operations
- `docs/product/strategy.md`: unit economics

Guardrail:

- The write path must reject, defer, or sideline low-novelty candidates before costly review/indexing.
- Billing waits until retrieval value and operating cost are measured.
