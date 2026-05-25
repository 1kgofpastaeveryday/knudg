# RFC 0002 - Codex Subconscious Sidecar

Status: superseded, non-normative

Superseded by: standalone Agent Subconscious repository

This file is retained as historical review context only. The standalone local
Agent Subconscious design now lives outside Knudg so it is not confused with
Knudg's production retrieval, consent, revocation, namespace, authorization, or
team-corpus architecture.

Implementation banner: do not implement this draft as Knudg production behavior. It is a design sketch for a local experiment only; production work requires an accepted RFC plus reconciliation with Knudg consent, revocation, namespace, authorization, and retrieval contracts.

This RFC is an exploratory local Codex sidecar design. It is not accepted Knudg architecture and must not be implemented as a Knudg production component until the blocking decisions in this document are resolved.

## Summary

Build a Codex-native sidecar experiment that observes local work and produces concise second-opinion notes. The sidecar is not primarily a memory manager. Its purpose is to test whether a background reviewer can catch drift, stale assumptions, and missed constraints without polluting the main agent context.

This replaces the Claude Subconscious shape:

```text
Claude hooks -> transcript formatter -> Letta-compatible server -> memory blocks -> guidance injection
```

with a local Codex experiment:

```text
sanitized local observation -> sidecar agent -> append-only event store -> active-notes projection
```

The experiment is deliberately local-first and advisory. It does not write Knudg public cards, does not bypass Knudg consent, and does not create a central memory surface.

## Product Boundary

RFC 0002 is separate from Knudg's central search infrastructure.

Knudg remains:

- central search infrastructure plus shared experience database
- consent-bound writer pipeline
- structured cards, not raw transcripts
- agent-readable retrieval through MCP/CLI/hooks

The sidecar experiment is:

- a local developer-tool experiment for concise second opinions
- a possible future client-side access pattern for Knudg
- not the canonical Knudg writer, retrieval, consent, or public-card path

If this design later becomes part of Knudg's normative architecture, a follow-up RFC must map sidecar concepts to the existing `search_similar` response contract, trust labels, authorization model, rollout gates, and consent/revocation rules.

## Goals

- Test whether a sidecar can produce useful concise notes with low prompt pollution.
- Keep sidecar output short, explicit, scoped, and advisory.
- Use sanitized observation profiles rather than raw session transcripts.
- Treat local durable state as implementation machinery with TTL, audit, and purge behavior.
- Make active notes rebuildable projections, not source of truth.
- Keep external writes and shared watch-task destinations out of v0.
- Make sidecar failures non-blocking for the main Codex agent.

## Non-Goals

- Do not preserve Letta API compatibility.
- Do not build a personal memory product.
- Do not store raw transcripts as long-term data.
- Do not write to arbitrary external files.
- Do not use Codex OAuth credentials until a separate credential RFC is accepted.
- Do not support real-time `interrupt` delivery in v0.
- Do not execute tools or privileged actions from sidecar output.

## Blocking Decisions Before Implementation

The following decisions are required before coding beyond a prototype spike. Until they are accepted, v0 scope is limited to event-source discovery, sanitizer fixtures, and offline draft-generation evaluation. It must not generate active notes for routine agent consumption.

1. Event source: session JSONL, Codex app-server events, plugin hooks, or manual export.
2. Sanitized observation profile: exact allowed fields, forbidden fields, redaction, and tests.
3. Local state engine: SQLite event store or append-only JSONL with equivalent guarantees.
4. Active-note lifecycle: TTL, dismissal, stale cleanup, projection rebuild, and trust rendering.
5. Backend: official API backend for v0; Codex OAuth only after a credential RFC.
6. Rollout: shadow-only, manual-read notes, active notes, and any future interrupt mode.
7. Local encryption: per-OS keychain integration, key rotation, backup/restore behavior, and failure modes.
8. Namespace controls: reserved local paths, collision handling, and proof that sidecar state cannot masquerade as Knudg cards or approval records.

## Observation Profile

The observer must not send raw Codex session JSONL directly to any model backend.

All model requests must be built from `SidecarObservationProfile`, a sanitized object generated locally.

```ts
type SidecarObservationProfile = {
  schemaVersion: "sidecar_observation.v0";
  sessionIdHash: string;
  workspaceIdHash: string;
  createdAt: string;
  source: {
    eventSource: "jsonl-spike" | "app-server" | "plugin-hook" | "manual";
    sourceRangeDigest: string;
    offsetStart?: number;
    offsetEnd?: number;
  };
  task: {
    userIntentSummary: string;
    currentPlanSummary?: string;
    recentOutcomeSummary?: string;
  };
  signals: Array<{
    kind:
      | "user_correction"
      | "tool_failure"
      | "plan_change"
      | "final_response_risk"
      | "stale_assumption"
      | "unfinished_work";
    summary: string;
    severityHint: "low" | "medium" | "high";
  }>;
};
```

Forbidden outbound fields:

- raw transcript text
- full tool output
- full stack traces
- secrets, tokens, cookies, credentials
- absolute private paths
- private repository names
- private customer, tenant, or personal identifiers
- full file contents
- arbitrary quoted prompt-injection text

If the sanitizer cannot decide whether a field is safe, it must omit the field and record a local `redaction_rejected` event. Backend calls fail closed when the sanitized profile is empty or invalid.

## Event Source Spike

V0 implementation cannot assume Codex JSONL is stable.

Before building the processor, run an event-source spike that documents:

- exact file discovery rules
- schema/version fields observed
- event IDs or fallback digests
- byte-offset and line-offset semantics
- behavior on rotation, compaction, truncation, partial lines, and invalid JSON
- how to detect duplicate events
- what breaks if Codex changes log shape

Until the spike is accepted, `jsonl-spike` is the only allowed event source and must be marked experimental in generated events. No processor, active-note projection, watch task, or background backend call may depend on `jsonl-spike` output outside the spike harness.

Spike acceptance criteria:

- one supported event source is selected for implementation, or the RFC remains prototype-only
- source identity is stable across restart, rotation, truncation, and compaction
- partial lines, invalid JSON, duplicate events, and offset rollback have deterministic outcomes
- a source-root allowlist prevents reading outside the workspace-approved observation roots
- event-source discovery and reads canonicalize final paths, reject symlinks,
  junctions, reparse points, hardlinks, and path aliases, and verify file
  identity between discovery, open, and read
- repo-controlled roots are rejected for sensitive event streams unless a
  later accepted RFC grants a narrow test-fixture exception
- a compatibility failure produces no notes and records a local diagnostic

## Intervention Model

The sidecar emits draft interventions. The bus enriches, validates, and stores them.

Shared intervention fields:

```ts
type InterventionBase = {
  urgency: "silent" | "note";
  audience: "main-agent" | "background-store";
  topic: string;
  summary: string;
  evidenceRefs?: string[];
  confidence: "low" | "medium" | "high";
  riskClass: "none" | "privacy" | "security" | "correctness" | "scope" | "ux";
  suggestedAction?: string;
};
```

Sidecar output schema:

```ts
type DraftIntervention = InterventionBase & {
  schemaVersion: "draft_intervention.v0";
};
```

Stored intervention schema:

```ts
type StoredIntervention = InterventionBase & {
  schemaVersion: "stored_intervention.v0";
  draftSchemaVersion: "draft_intervention.v0";
  id: string;
  workspaceEventSeq: number;
  createdAt: string;
  source: "codex-subconscious";
  producerVersion: string;
  observationDigest: string;
  contentDigest: string;
  policyVersion: string;
  expiresAt: string;
  dismissedAt?: string;
  dismissalReason?: string;
};
```

V0 supports only:

- `silent`: stored locally, not shown to the main agent
- `note`: rendered into active notes at the next manual or opportunistic boundary

`interrupt` is intentionally excluded from v0. It requires a synchronous delivery path, acknowledgement, rate limits, snooze/dismiss controls, kill switch, accessibility behavior, and rollout metrics.

## Local State Contract

Use SQLite for v0 unless a follow-up RFC proves append-only JSONL is sufficient.

This store is a local sidecar journal. It is not the Knudg canonical event log, cannot be replayed into Knudg card state, and must not use RFC 0001 `event_seq` semantics. Ordering is scoped to one workspace-local sidecar database.

Local privacy boundary:

- local sidecar state is outside Knudg's central shared corpus
- state is disabled by default and per-workspace opt-in
- secrets are stored only in the OS keychain or injected process environment, never in SQLite or projections
- state directories must be excluded from cloud sync and backup by default where the platform supports it
- file permissions must restrict access to the current OS user
- encryption-at-rest is required before active notes are enabled outside a prototype spike
- purge must delete the database, WAL files, temporary files, projection files, and derived diagnostics, then verify absence
- default intervention retention is 7 days during prototype evaluation; longer retention requires explicit approval

Required tables:

```sql
CREATE TABLE sidecar_events (
  event_id TEXT PRIMARY KEY,
  workspace_event_seq INTEGER NOT NULL UNIQUE,
  schema_version TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN (
    'observation_recorded',
    'intervention_proposed',
    'note_rendered',
    'note_dismissed',
    'state_purged',
    'backend_rotated',
    'projection_rebuilt'
  )),
  logical_object_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  CHECK (json_valid(payload_json)),
  UNIQUE (logical_object_id, idempotency_key)
);

CREATE TABLE interventions (
  id TEXT PRIMARY KEY,
  workspace_event_seq INTEGER NOT NULL UNIQUE
    REFERENCES sidecar_events(workspace_event_seq) ON DELETE RESTRICT,
  schema_version TEXT NOT NULL CHECK (schema_version = 'stored_intervention.v0'),
  draft_schema_version TEXT NOT NULL CHECK (draft_schema_version = 'draft_intervention.v0'),
  urgency TEXT NOT NULL CHECK (urgency IN ('silent', 'note')),
  audience TEXT NOT NULL CHECK (audience IN ('main-agent', 'background-store')),
  topic TEXT NOT NULL,
  summary TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
  risk_class TEXT NOT NULL CHECK (risk_class IN ('none', 'privacy', 'security', 'correctness', 'scope', 'ux')),
  observation_digest TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  dismissed_at TEXT,
  dismissal_reason TEXT
);

CREATE INDEX interventions_active_notes_idx
  ON interventions(urgency, dismissed_at, expires_at, confidence, risk_class);

CREATE TABLE source_offsets (
  source_id TEXT NOT NULL,
  event_source TEXT NOT NULL CHECK (event_source IN ('jsonl-spike', 'app-server', 'plugin-hook', 'manual')),
  source_range_digest TEXT NOT NULL,
  offset_start INTEGER NOT NULL CHECK (offset_start >= 0),
  offset_end INTEGER NOT NULL CHECK (offset_end >= offset_start),
  status TEXT NOT NULL CHECK (status IN ('observed', 'processed', 'rejected', 'superseded')),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (source_id, source_range_digest)
);

CREATE TABLE schema_migrations (
  version TEXT PRIMARY KEY,
  checksum TEXT NOT NULL,
  applied_at TEXT NOT NULL
);

CREATE TABLE writer_lease (
  workspace_id_hash TEXT PRIMARY KEY,
  process_id TEXT NOT NULL,
  fencing_token INTEGER NOT NULL,
  acquired_at TEXT NOT NULL,
  heartbeat_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
```

Rules:

- One writer per workspace, enforced by `writer_lease` with heartbeat, expiry, and monotonically increasing fencing token.
- Duplicate processors must run read-only or exit.
- Every SQLite connection sets `PRAGMA foreign_keys=ON`.
- Writes use `BEGIN IMMEDIATE` transactions with WAL mode and a configured busy timeout.
- Offset advancement occurs in the same transaction as event/intervention persistence.
- `active-notes.md` is a disposable projection regenerated from valid, unexpired, undismissed interventions.
- Malformed local state is quarantined and not silently ignored. Startup must run `PRAGMA integrity_check`; failure disables projections and moves the database aside for user inspection.
- Offset metadata retention must be at least as long as the maximum replay and dedupe window for the selected source. The 7-day default is allowed only for prototype spike data that cannot emit active notes.
- A purge command must delete local state and regenerate empty projections.
- Local state must be encrypted at rest before any non-spike use. Keys must live in the OS keychain where available, not in repository files or model-visible config. If keychain access fails, the sidecar fails closed and records only a non-sensitive local error.

Digest and ID rules:

- IDs are UUIDv7 or another monotonic opaque identifier selected in the implementation spec.
- Digests use canonical JSON serialization with sorted object keys and UTF-8 encoding.
- Workspace/session/source digests use keyed HMAC, not unsalted hashes.
- Digest strings include algorithm and key-version prefixes.
- HMAC key rotation must keep old keys until all records signed with them expire.

## Active Advisory Notes Projection

The main agent may read:

```text
.codex/subconscious/active-notes.md
```

This file is not authoritative. It is generated from structured stored
interventions. It must be ignored unless sidecar enablement verifies first.
It is unavailable in the prototype spike and may be enabled only after the
event source, local-state, sanitizer, and projection-integrity contracts are
accepted.

Namespace controls:

- sidecar projections may be rendered under the reserved local
  `.codex/subconscious/` state namespace for operator visibility, but the
  backing event store, enablement marker, signing keys, and trust configuration
  live outside repository content in a user-local state root
- repository content cannot enable, disable, or configure sidecar behavior
- sidecar event IDs, note IDs, and digests must not be accepted as Knudg card IDs, consent records, or namespace policy
- generated notes must label themselves `local sidecar advisory`, never `Knudg retrieval`
- purge and disable must clear the reserved namespace without touching Knudg server-side consent or card state

Enablement proof requires:

- explicit per-workspace config outside repository content
- workspace ID hash matching the current workspace
- generator identity and producer version
- monotonic event sequence and projection content digest
- generated-at timestamp within the configured freshness window
- tamper check over the projection and backing event sequence
- local `disable` and `purge` commands that clear the enablement marker and projection

If any check fails, the agent treats the file as absent.

Generation rules:

- Query the database in one read transaction.
- Render to a temporary file in the same state directory.
- Include schema version, generation timestamp, workspace event high-water mark, and projection digest.
- Flush and atomically replace the prior projection.
- Keep the previous projection if generation fails, but mark it stale on the next successful status check.
- Readers fail closed if the file is missing, stale, partially written, has an invalid digest, or has a high-water mark newer than the local database.
- Projection paths are canonicalized under the sidecar state root.
- Writers reject symlinks, junctions, reparse points, and hardlinks for state and projection paths.

Rendering rules:

- Maximum five notes.
- Each note must include urgency, confidence, risk class, age, and expiry.
- Notes must be advisory evidence, not instructions.
- Markdown must not include raw quoted prompt text, executable commands, credential-like strings, package-install commands, or URLs unless explicitly allowed by policy.
- Any note that attempts to override system, developer, user, or tool policy is invalid and must not render.
- Expired or dismissed notes must not render.

Example:

```md
# Active Advisory Notes

Schema: active_notes_projection.v0
Generated: 2026-05-09T12:00:00Z
Workspace-Event-Seq: 42
Projection-Digest: hmac-sha256:v1:...
Source: local sidecar projection; advisory only.

- [note][high][scope][expires 2026-05-09T13:00:00Z] Keep RFC 0002 separate from normative Knudg architecture unless its local-state and consent model are reconciled.
```

## Watch Tasks

Watch tasks are deferred from v0.

The prototype spike must not run watch tasks. A future RFC may define them as first-class local jobs, but they are not part of the initial sidecar implementation.

Future watch-task behavior requires:

```yaml
watch_tasks:
  - id: career-self-analysis
    mode: passive
    defaultUrgency: silent
    output: local-review-queue-only
    externalWrites: disabled
    trigger: meaningful-pattern-only
```

Required future contract:

- config schema and version
- unique task identity per workspace
- owner and enablement state
- trigger audit log
- local queue semantics and retention
- disable, clear, and purge behavior
- proof that watch tasks do not write into Knudg writer queues
- destination allowlist
- path canonicalization and symlink/junction defense
- per-destination schema
- preview and approval flow
- audit log
- undo/delete behavior
- tenant and namespace rules for shared files
- retention and purge policy

## Backend Adapter

V0 backend:

- `OpenAIResponsesBackend` using an explicit API key or supported local credential flow.

Backend calls are disabled during the event-source spike unless the user explicitly runs offline draft-generation evaluation against saved sanitized profiles.

`OpenAIResponsesBackend` contract:

- use only a configured model allowlist
- use strict structured outputs for `DraftIntervention`
- set request storage/retention controls explicitly, including `store=false`;
  if the selected backend cannot assert equivalent no-store/no-training
  behavior, remote backend calls fail closed
- disable remote MCP/tools, background mode, and external file access unless a later RFC approves them
- send only `SidecarObservationProfile`; never send raw transcripts, tool outputs, paths, secrets, or file contents
- enforce request timeout, retry limit, exponential backoff with jitter, and circuit breaker
- treat refusals, invalid JSON, schema mismatch, rate limits, and backend errors as no-note outcomes
- record local diagnostics without logging payload contents or credentials
- expose backend name, model, and retention mode in `status`

Optional future backends:

- `CodexOAuthBackend`
- `OpenRouterBackend`

`CodexOAuthBackend` is blocked until a credential RFC defines:

- supported endpoint/API surface
- token source
- storage requirements
- scope/audience model
- TTL and refresh behavior
- admin-policy detection
- revocation behavior
- logging restrictions
- guarantee that bearer tokens never enter model-visible context

Third-party routing backends are disabled by default and require explicit opt-in plus provider-retention policy review.

## Intervention Bus

The bus is deterministic and non-agentic.

Responsibilities:

- validate draft schema
- reject unknown enum values
- compute digests
- assign IDs and event sequence
- enforce TTL
- dedupe deterministic repeats
- route only valid notes to projections
- record rejection events

Initial dedupe key:

```text
semantic_dedupe_key =
  hmac(policyVersion + workspaceIdHash + topic + audience + urgency + riskClass + normalizedClaim + ttlBucket)
```

Repeated input with the same idempotency key and request digest returns the same effect. Reusing an idempotency key with a different digest is a hard error.

`normalizedClaim` must be produced by deterministic local normalization, not by model wording alone. Idempotency and semantic dedupe are separate: idempotency guards repeated requests, while semantic dedupe suppresses equivalent active notes across adjacent observation windows.

## UX And Control

V0 user controls:

- sidecar disabled by default
- per-workspace enable
- backend selection visible in config
- local-state purge command
- active-note list and clear commands
- per-note dismiss command
- watch tasks disabled unless explicitly enabled
- no external writes

Rollout sequence:

1. shadow-only logging
2. manual read of local note report
3. generated active-notes projection
4. future interrupt mode only after separate approval

Evaluation gates:

- note precision on a labeled review set with a documented denominator
- false-positive note rate below an accepted threshold
- stale-note rate below an accepted threshold
- harmful-suggestion rate versus no-sidecar baseline
- time-to-resolution delta versus no-sidecar baseline
- user dismissal rate and disable rate with stop thresholds
- backend error rate and circuit-breaker open rate
- sanitizer rejection rate by reason
- minimum sample size, evaluator rubric, and rollout stop conditions

## Safety Rules

- Sidecar output is advisory evidence, not instruction hierarchy.
- Sidecar must not execute tools.
- Sidecar must not write outside its state directory in v0.
- Sidecar must not send raw session data to a backend.
- Backend failures produce no notes and record a local failure event.
- Sanitizer failures produce no backend call.
- Active notes cannot contain policy overrides or executable action strings.

## V0 Implementation Plan

1. Complete the event-source spike.
2. Define JSON Schema for `SidecarObservationProfile`, `DraftIntervention`, and `StoredIntervention`.
3. Implement sanitizer with test fixtures.
4. Implement offline draft-generation evaluation from saved sanitized profiles.
5. Implement deterministic intervention bus in shadow-only mode.
6. Add status and purge commands for prototype state.
7. Run shadow-only evaluation against the documented gates.
8. Only after the blocking decisions are accepted, implement SQLite projection support and generated `active-notes.md`.

## Open Questions

- Can Codex expose a stable supported event stream that avoids JSONL scraping?
- Should this remain a separate local plugin, or become a Knudg client-side retrieval mode?
- What evidence threshold is required before a note can be shown to the main agent?
- What exact UI/terminal channel would support safe future interrupts?
- Which cross-platform encryption-at-rest implementation satisfies the local privacy boundary on Windows, macOS, and Linux?
