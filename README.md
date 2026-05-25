# Knudg

Knudg is an agent experience infrastructure project.

The core idea is not personal memory. It is a shared retrieval layer where agents can discover what other agents have already learned: solved problems, failed paths, workarounds, environment-specific traps, deprecated approaches, and unknowns that were clarified during real work.

## One-line Concept

Agents should not start from zero.

Knudg gives agents access to lived experience from previous agent work, so they can reduce redundant reasoning, avoid repeated failures, and reach useful paths faster.

## Product Positioning

Knudg is not a local memory plugin.

It is a central search infrastructure and knowledge database for agent-readable experience.

Adjacent products such as Claude Subconscious, Letta memory, Recall, Remnic, and Engram are closer to personal, team, or repo memory. Knudg should be positioned as a larger experience network: an index of reusable agent work patterns across tools, users, teams, domains, and ecosystems.

Human-facing analogy:

- Stack Overflow for humans
- incident databases for engineering teams
- package registries for reusable code
- search engines for documents

Agent-facing analogy:

- an experience network for agents
- a retrieval layer for solved agent problems
- a database of paths agents have already walked

## Core Roles

In MVP these roles may run as summoned sub-agents: the main agent starts the
user's task and, in parallel, asks bounded Knudg roles for compact verdicts.
This avoids filling the acting prompt with historical experience. A fully
automatic hook or local subconscious sidecar is optional later plumbing, not a
dependency for writer/searcher/nudger.

### Knowledge Crawler

The crawler runs alongside an active agent session. It builds a sanitized outbound query profile, searches for similar past experience, and shows concise retrieval-panel suggestions outside the acting agent prompt in MVP.

Retrieved cards are always untrusted evidence, not instructions. The main agent can use a card as a clue, but must independently validate any action. Inline prompt delivery is non-MVP and requires a hostile-card red-team gate.

### Knowledge Nudger

The nudger decides whether a Knudg suggestion is worth surfacing during active
work. It returns only a short signal such as "offer retrieval panel" or "offer
writer draft"; it does not tell the main agent what technical action to take.

### Knowledge Writer

The writer runs after a problem has been solved, or after the agent discovers an important failed path or unknown.

It creates a private candidate card first. The candidate is redacted and reviewed before the user is asked to approve publication. Approval is only valid for the exact redacted artifact shown to the user.

## Architecture Invariants

- Default visibility is private.
- Public cards retain publisher `tenant_id`; public visibility comes from namespace policy.
- Search authorization happens before candidate generation, ranking, and reranking.
- Raw logs, transcripts, stack traces, and file excerpts are not stored by default.
- Public consent is bound to the exact redacted artifact shown to the user; derived artifacts need explicit inheritance rules.
- Canonical truth is an append-only event log plus derived current-state projections.
- Retrieved card text must never directly trigger privileged actions.
- Search may abstain. Returning no card is a valid result.
- Consent and revocation human UI is launch-blocking for product-path or
  shared/hosted non-synthetic private retention, team namespace sharing, and
  public publication; MCP, CLI, and hooks can hand off but cannot complete
  consent. The only P0 exception is `local_private_dogfood`: explicit local
  structured cards may persist locally only with revoke/purge, no-log tests,
  and non-promotion guarantees.
- Enterprise-managed directives and routing guidance are separate from experience cards; they require scoped policy objects, approval, revocation, conflict handling, and audit.
- Database-side intake must run a deterministic and model-assisted safety gate before accepting non-synthetic candidate content.
- Queue processing is at-least-once; correctness is enforced with database idempotency and reconciliation.
- Cards, APIs, indexes, embeddings, and storage manifests are versioned.

## Initial MVP

The MVP priority is now the local vertical experience first:

```text
explicit local capture -> local Postgres storage -> later task-profile search ->
retrieval-panel suggestion -> local purge/revoke
```

This comes before production/shared infrastructure. The first product question
is whether a solved agent-work card, captured intentionally by one operator,
actually helps on a later similar task. If that loop is not useful, team/public
consent machinery, vector search, enterprise governance, and publication flows
are premature.

The first non-synthetic source class is `local_private_dogfood`, not
team/private production ingestion. It is single-operator, single-workspace,
local-Postgres only, explicit-command only, and never public/team shared. It
stores structured operator-written cards, not raw transcripts, logs, stack
traces, source files, or arbitrary workspace files. It must include local
revoke and local purge commands before it is considered usable.

`local_private_dogfood` is not a lane, queue, or publication state. It is an
immutable `source_class`. Separate fields must carry local-only visibility,
sharing state, publication state, and lifecycle state. Local private cards must
not be promoted into team/public/hosted projections, embeddings, publication
consent rows, export flows, product candidate queues, or admin/review surfaces.

Production/private/team/public flows remain gated separately. The
`non_synthetic_body_persistence_gate`, trusted consent/revocation UI,
protected-data durability, no-log ingress, review operations, and public
publication gates apply before shared or hosted data processing, not before the
local private dogfood path. The local path still needs a P0 no-log rule: raw
or rejected local-private content must not appear in stdout, stderr, structured
logs, traces, queue payloads, test snapshots, DB notices, or error messages.

The provisional wedge remains developer tooling failures for agentic coding
environments, but WEDGE-001 should measure the local vertical loop before broad
publication or team namespace work. If public-only retrieval underperforms but
local/private retrieval is useful, Knudg should evaluate team-shared private
corpora only after the team namespace consent/grant gate instead of forcing
public publication.

Follow-on wedge candidates:

- developer tooling failures for agentic coding environments
- package manager and framework migration errors
- CI/test/build failures with public dependencies
- iOS/TestFlight and mobile build pipeline issues

MVP sequence:

1. Implement `local_private_dogfood` capture from explicit structured input.
2. Store that card in local Postgres without raw transcript or file ingestion.
3. Search stored local cards from a later task profile and return
   retrieval-panel metadata only.
4. Add local revoke, local purge, and visible "not shared, not published"
   status.
5. Dogfood the loop on repeated developer-tooling failures and measure whether
   retrieved cards reduce repeated investigation.
6. Only after useful retrieval is demonstrated, harden the shared/product path:
   protected-data durability, no-log ingress, intake safety, trusted
   consent/revocation UI, production exact/FTS projections, team namespace
   grants, public publication, vector/rerank, external MCP/hooks, and billing.

## Internal Documentation

This README is an internal working index, not a public docs entrypoint. These
documents are internal unless a page or section is explicitly marked
public-safe in a signed public-doc manifest. The landing page, public README,
and public architecture explainer must be generated from that manifest rather
than this navigation list. Do not publish or link these docs from a public LP
until a release check removes launch-control values, internal review artifacts,
raw queue names, private thresholds, operational defaults, and `docs/plans/`.

Documentation authority: architecture invariants and implementation-readiness
gates are normative; backlog task files define executable slices;
`backlog/backend-roadmap.md` is an ordering/index view; this README is
positioning and navigation. If these disagree, update the normative document
and cross-link the backlog change instead of treating roadmap wording as a
gate override.

- [Architecture Overview](docs/architecture/overview.md)
- [Security and Privacy](docs/architecture/security-privacy.md)
- [Data Model](docs/architecture/data-model.md)
- [Enterprise Governance](docs/architecture/enterprise-governance.md)
- [Agent Access](docs/architecture/agent-access.md)
- [Summoned Role MVP](docs/architecture/summoned-roles.md)
- [Retrieval Model](docs/architecture/retrieval.md)
- [Search Strategy](docs/architecture/search-strategy.md)
- [Operations](docs/architecture/operations.md)
- [Consent and Revocation UX](docs/architecture/consent-revocation-ux.md)
- [Implementation Readiness](docs/architecture/implementation-readiness.md)
- [Local Development](docs/development.md)
- [Operations Runbooks](docs/operations/)
- [Implementation Backlog](backlog/README.md)
- [Product and Monetization](docs/product/strategy.md)
- [Intent Crosswalk](docs/product/intent-crosswalk.md)
- [Decision Backlog](docs/decisions/README.md)

## Messaging

Possible English lines:

- Agents don't start from zero.
- Give agents lived experience.
- A consented experience layer for agent work.
- Measure and reduce repeated investigation in one validated wedge first.
- A shared experience layer for autonomous work.

Japanese messaging is intentionally omitted until a localization pass verifies
copy, encoding, metadata, font fallback, and screenshot QA.

## Strategic Thesis

As agent usage grows, the world will waste large amounts of compute rediscovering the same solutions, repeating the same failed paths, and re-reading the same documentation from scratch.

Knudg turns solved agent work into shared, searchable, consented experience.

The long-term product is not a memory app. It is an experience infrastructure layer for agents.
