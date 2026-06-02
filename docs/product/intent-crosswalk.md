# Intent Crosswalk

This document maps the public Knudg product intent to design requirements that
prevent drift.

## Not Personal Memory

Intent:

- Knudg is not Claude Subconscious, Letta memory, or a local memory subscription.
- The core is shared search infrastructure and its database.

Design anchors:

- `README.md`: Product Positioning and Architecture Invariants
- `docs/architecture/overview.md`: local state limits
- `docs/architecture/overview.md`: live backend orchestration is the active
  writer/searcher/nudger path; subconscious is optional plumbing
- `docs/product/strategy.md`: public-benefit sustainability excludes paid local
  memory and B2B data products as primary value

Guardrail:

- Local state is only current-work query material, pending writer approval, and short-lived cache metadata by default.
- MVP value must be measured from the closed-launch backend path, excluding
  same-session local cache.
- Writer/searcher/nudger must be usable through live backend orchestration
  without completing a local subconscious sidecar.

## Agent-Readable Experience Infrastructure

Intent:

- The product is "Stack Overflow + incident DB + reusable agent work patterns" for agents.
- MCP, CLI, and hooks matter before a polished human UI.

Design anchors:

- `README.md`: Core Roles and Initial MVP
- `docs/architecture/agent-access.md`: transport, operation, token, hook, and response contracts
- `docs/architecture/overview.md`: live closed-launch orchestration before
  automatic hooks
- `docs/architecture/retrieval.md`: injection contract and delivery modes

Guardrail:

- Every wedge must expose agent-native access contracts before human-facing knowledge-base polish.
- Retrieved cards are evidence, not instructions.
- Sub-agents may search, draft, nudge, or review in parallel with main-agent
  work, but the main agent keeps task execution and final action authority.

## Thin Injection

Intent:

- The main agent prompt should not be polluted.
- Cards should appear only as concise candidate paths when useful.

Design anchors:

- `docs/architecture/overview.md`: compact backend verdicts outside the acting
  prompt
- `docs/architecture/retrieval.md`: Injection Contract
- `docs/architecture/security-privacy.md`: Retrieved Card Trust Boundary
- `docs/architecture/operations.md`: rollout controls

Guardrail:

- Default rollout moves through shadow and retrieval-panel delivery before inline hints.
- Inline injection has max cards, token budget, and no-suggestion fallback.
- Searcher/writer/nudger orchestration returns bounded verdicts first; raw
  card bodies or long historical context require an explicit panel or handoff.

## Consent and Transparency

Intent:

- Publication requires explicit human approval.
- Users must understand what is and is not public.
- The published unit is a redacted reusable artifact, not a raw transcript.
- Raw Knudg logs, transcripts, stack traces, and file excerpts do not leave the
  local environment unless the user explicitly approves that exact transfer
  path.

Design anchors:

- `docs/architecture/security-privacy.md`: Privacy, Redaction, and Consent
- `docs/architecture/consent-revocation-ux.md`: consent matrix and revocation cockpit
- `docs/architecture/data-model.md`: consent records and derived artifacts
- `docs/architecture/overview.md`: canonical trail policy

Guardrail:

- Before approval, live backend calls may receive only sanitized query material,
  such as a bounded task profile. They must not receive raw Knudg logs, raw
  transcripts, full stack traces, source excerpts, secrets, or private paths.
- Approval for private retention, team sharing, public publication, raw artifact
  retention, and commercial or derived use are separate decisions. Approval for
  one path does not authorize another.
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
- Broader wall-bouncing should eventually let Codex retrieve structured prior
  reasoning such as "we considered this before and reached this boundary" for
  personal decisions, career/company fit, place/service experiences, and other
  reusable observations.

Design anchors:

- `docs/product/strategy.md`: wedge boundary statement
- `docs/architecture/data-model.md`: domain-general outcome fields
- `docs/architecture/experience-domains.md`: domain separation for technical,
  personal reasoning, career, place/service, public candidates, and public
  aggregate signals

Guardrail:

- Wedge-specific examples must not hard-code the global ontology.
- Broader domains must not mix with technical retrieval by default. Each domain
  needs its own retrieval, redaction, consent, retention, and publication
  policy.
- Company names and place/service names may remain as retrieval keys when
  policy allows, but selection details, people, direct messages, exact dates,
  account/receipt IDs, and private circumstances are redacted by default.
- Public use is a separate artifact path. Private cards do not become public by
  changing visibility; public candidates require exact approval and review, and
  public aggregate signals must avoid person-level targeting or one-off
  complaint amplification.

## Massive Shared DB and Sustainability

Intent:

- Indexing, writing, storage growth, and operating cost are core concerns from the beginning.

Design anchors:

- `docs/architecture/overview.md`: admission, dedupe, novelty, backlog controls
- `docs/architecture/operations.md`: cost telemetry and index migration operations
- `docs/architecture/implementation-readiness.md`: provisional budgets, queue defaults, runbook template
- `docs/product/strategy.md`: unit economics

Guardrail:

- The write path must reject, defer, or sideline low-novelty candidates before costly review/indexing.
- Billing and paid access are out of scope for the OSS public-good strategy;
  cost controls remain necessary for abuse resistance and public-service
  sustainability.
