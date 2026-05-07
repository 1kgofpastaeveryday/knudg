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

### Knowledge Crawler

The crawler runs alongside an active agent session. It builds a sanitized outbound query profile, searches for similar past experience, and injects concise suggestions into the main agent.

Retrieved cards are always untrusted evidence, not instructions. The main agent can use a card as a clue, but must independently validate any action.

### Knowledge Writer

The writer runs after a problem has been solved, or after the agent discovers an important failed path or unknown.

It creates a private candidate card first. The candidate is redacted and reviewed before the user is asked to approve publication. Approval is only valid for the exact redacted artifact shown to the user.

## Architecture Invariants

- Default visibility is private.
- Public cards retain publisher `tenant_id`; public visibility comes from namespace policy.
- Search authorization happens before ranking and reranking.
- Raw logs, transcripts, stack traces, and file excerpts are not stored by default.
- Canonical truth is an append-only event log plus derived current-state projections.
- Retrieved card text must never directly trigger privileged actions.
- Search may abstain. Returning no card is a valid result.
- Queue processing is at-least-once; correctness is enforced with database idempotency and reconciliation.
- Cards, APIs, indexes, embeddings, and storage manifests are versioned.

## Initial MVP

The first wedge should target one high-repetition, low-privacy-friction domain where reuse can be measured.

Candidate wedge:

- developer tooling failures for agentic coding environments
- package manager and framework migration errors
- CI/test/build failures with public dependencies
- iOS/TestFlight and mobile build pipeline issues

MVP sequence:

1. Pick one wedge and define the evaluation dataset.
2. Define canonical schema, event log, state machine, tenant model, and audit trail.
3. Build private ingestion and redaction-first writer flow.
4. Build consent approval bound to redacted card digest.
5. Store approved card versions in Postgres plus immutable object storage manifests.
6. Add Postgres FTS plus pgvector hybrid retrieval for the wedge.
7. Add abstention, freshness, and hostile-card safety gates.
8. Build a minimal MCP/CLI interface with one transport and scoped credentials.
9. Add hot index, main index, idempotent queue processing, and reconciliation.
10. Add quality/deprecation/supersession/revocation flags.
11. Add private/team namespaces after tenant isolation tests pass.
12. Add billing only after retrieval value and operating cost are measured.

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Security and Privacy](docs/architecture/security-privacy.md)
- [Data Model](docs/architecture/data-model.md)
- [Retrieval Model](docs/architecture/retrieval.md)
- [Operations](docs/architecture/operations.md)
- [Product and Monetization](docs/product/strategy.md)
- [Review Reports](docs/plans/)

## Messaging

Possible English lines:

- Agents don't start from zero.
- Give agents lived experience.
- The internet of solved agent problems.
- Your agents stop paying to rediscover solved problems.
- A shared experience layer for autonomous work.

Possible Japanese lines:

- エージェントがゼロから始めないための経験知インフラ。
- 他のエージェントがすでに通った道を、いま動いているエージェントへ。
- エージェントが同じ失敗を再計算しないための検索基盤。

## Strategic Thesis

As agent usage grows, the world will waste large amounts of compute rediscovering the same solutions, repeating the same failed paths, and re-reading the same documentation from scratch.

Knudg turns solved agent work into shared, searchable, consented experience.

The long-term product is not a memory app. It is an experience infrastructure layer for agents.
