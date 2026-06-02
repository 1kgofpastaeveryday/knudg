# Enterprise Governance

Enterprise Knudg adds managed guidance without turning retrieved experience
cards into authority. The database-side intake safety gate is a core Knudg
ingestion requirement for all non-synthetic candidate content; enterprise
deployments may add tenant-configured detectors and policies, but they do not
own the base gate.

## Managed Directives

Enterprise tenants may publish tenant-managed guidance objects for delegated
agents. These are separate from experience cards and are evaluated by a policy
retrieval path before normal card retrieval.

Guidance type:

- `instruction`: scoped tenant-authored operating instruction.
- `routing`: scoped internal path, account, region, repository, module, or
  service endpoint selection.
- `guardrail`: scoped deny, approval, or human-review policy before action.

Guidance strength:

- `suggestion`: optional context; the agent may ignore it.
- `preference`: tenant or team preference; clients may ignore only by recording
  a structured local exception when policy allows it.
- `directive`: tenant-approved instruction for a scoped condition.
- `deny`: blocks action for the scoped condition.

`preference` is a strength, not a guidance type. Product and backlog references
to managed preferences mean `strength=preference` on an `instruction`,
`routing`, or `guardrail` object.

Managed guidance must never be stored as ordinary cards. It needs a distinct
schema, lifecycle, owner, reviewer, effective window, digest, and audit trail.
It can be retrieved next to cards, but the response must label it as
tenant-managed policy or routing guidance rather than prior experience.

Minimum fields:

- `guidance_id`
- `tenant_id`
- `namespace_id`
- `guidance_type`
- `strength`
- `scope`: tenant, team, repo pattern, environment, task type, tool, cloud
  provider, data classification, and optional integration IDs
- `condition`: structured predicates, not only prose
- `instruction`: bounded human-authored text
- `rationale`
- `owner`
- `approver`
- `policy_version`
- `effective_at`
- `expires_at`
- `override_policy`
- `revocation_state`
- `payload_digest`

`override_policy` is an enum:

- `none_allowed`: no override route exists; conflicts return `deny` or
  `conflict`.
- `human_approval_required`: a trusted human-session approval must name the
  exact guidance version, context digest, reason class, expiry, and actor.
- `break_glass_only`: a break-glass case with two-person approval must exist
  before action.
- `tenant_admin_exception`: an authorized tenant admin may create a bounded
  exception after step-up auth; delegated agents cannot create or complete it.
- `local_operator_may_ignore`: allowed only for `suggestion` and `preference`
  guidance. The client may proceed after recording a structured local exception
  event with no privileged server-side effect. Tenant-managed `directive`,
  `routing`, `guardrail`, and `deny` guidance require a server-side exception
  or approval record before bypass.

Each override has an idempotency key, expiry, revocation behavior, audit event,
eligible actor class, and action-text display rule. Override state never changes
the underlying guidance object; it creates a separate exception record bound to
the guidance version and `GuidanceContext` digest.

Structured predicates use a closed JSON grammar. Unknown fields, unknown
operators, unnormalized Unicode, unbounded wildcards, regular expressions,
negative-only predicates, and free-form executable predicates are rejected.
Allowed operators for the first enterprise milestone are `equals`, `in`,
`prefix_match` for approved namespace/repo prefixes, and `contains_tag` for
server-issued tags. All predicate inputs are canonicalized before evaluation.
Repo names, cloud account IDs, integration IDs, and data-classification labels
must come from server-attested sources, not caller prose.

`GuidanceContext` is assembled by the server. Client-supplied task labels are
hints only. The authoritative context is built from delegated-token claims,
tenant membership, namespace grants, pinned integration IDs, connector
attestations, repo/workspace binding, server-known environment labels, and
verified data-classification metadata. A request with only client-claimed
context can receive at most `suggestion` guidance and must not receive
`directive`, `routing`, or `guardrail` decisions.

Example:

```yaml
managed_guidance:
  guidance_type: routing
  strength: directive
  scope:
    tenant: acme
    task_types: ["aws_provisioning", "deployment"]
    cloud_provider: aws
    environments: ["production"]
  condition:
    repo_pattern: "payments-*"
    data_classification: "internal"
  instruction: "Use the shared platform AWS account through approved Terraform modules."
  rationale: "Centralized audit, cost control, and incident ownership."
  owner: platform-infra
  approver: platform-security
  override_policy: human_approval_required
  expires_at: "2026-12-31"
```

## Authority Boundary

Managed guidance is stronger than retrieved experience, but it is not a system
or developer instruction. It cannot override platform safety rules, tool
policies, user consent requirements, authorization, revocation, legal holds, or
local operator policy. If a tenant directive conflicts with a higher-priority
policy, Knudg returns a conflict state and the acting agent must not treat the
directive as executable authority.

Guidance evaluation returns a structured decision, not raw policy text:

- `no_applicable_guidance`
- `suggest`
- `prefer`
- `route`
- `require_human_approval`
- `deny`
- `conflict`

Decision precedence is fixed:

```text
platform/tool safety policy
  > authorization and revocation
  > legal hold and data-retention policy
  > local operator policy
  > tenant guardrail
  > tenant directive
  > tenant routing
  > tenant preference
  > suggestion
  > experience card evidence
```

Combining rules:

- any applicable `deny` wins over route, directive, preference, and suggestion
- any higher-precedence conflict with a tenant directive returns `conflict`
  or `deny`; it never downgrades silently to a weaker hint
- multiple compatible routing records can be returned only when they name the
  same validated destination and policy version
- incompatible active directives or routing records return `conflict` with no
  executable destination text
- `require_human_approval` blocks action until a trusted approval route records
  a matching override decision
- retrieved experience cards never strengthen or weaken a managed-guidance
  decision

Conflicts must be explicit:

- overlapping directives with incompatible instructions return
  `guidance_conflict`
- expired, revoked, or stale guidance is omitted or returned only as
  non-actionable audit context for authorized admins
- weakly scoped prose guidance cannot be promoted to `directive`
- high-impact overrides require the configured human approval route

High-impact guidance includes production cloud routing, billing-affecting
changes, credential handling, CI/CD mutation, destructive data operations,
security posture changes, and any guidance that names an account, repository,
module, service endpoint, or approval path. High-impact guidance requires
two-person approval with distinct owner and approver roles, step-up
authentication, destination allowlist validation, signed payload digest, and an
emergency revocation drill before activation.

High-impact routing destinations are registry objects, not prose. A destination
record includes integration ID, cloud account or project ID, repository ID,
module/package ID, environment ID, canonical endpoint or URL policy, owner,
version, expiry, and revocation state. Guidance payload digests include the
destination object ID and version. Clients must revalidate the destination
registry immediately before a high-impact tool action; renamed, transferred,
DNS-mutated, expired, or unpinned destinations fail closed.

## Delivery Contract

Enterprise guidance can be delivered in the same response envelope as search,
but in a separate array from experience cards:

```yaml
decision: show
policy_decision: route
delivery_mode: retrieval_panel
managed_guidance:
  - guidance_type: routing
    strength: directive
    decision: route
    fit: applicable
    owner: platform-infra
    scope_digest: "sha256:..."
    policy_version: "enterprise-guidance-v1"
    guidance_epoch: 42
    freshness: current
    conflict_state: none
    enforcement_class: requires_host_enforcement
    instruction_summary: "Use the shared platform AWS account through approved Terraform modules."
    override_policy: human_approval_required
cards:
  - outcome_type: solved
    trust_label: Single-session clue
```

Top-level retrieval `decision` remains about card display only. Guidance adds
one canonical API field, `policy_decision`. The "Effect" column below is
descriptive documentation, not a response field named `policy_effect`:

| Guidance outcome | `decision` | `policy_decision` | Effect |
|---|---|---|---|
| no applicable guidance | normal retrieval result | `none` | cards may show if retrieval clears gates |
| suggestion/preference | normal retrieval result | `advisory` | cards may show; guidance is non-blocking |
| route/directive | normal retrieval result | `route` | cards may show; action requires `prepare_guided_action` before tool use |
| require human approval | `no_suggestion` for action-bearing card bodies | `approval_required` | show no executable guidance until approval |
| deny | `no_suggestion` | `deny` | no action-bearing cards or destinations returned |
| conflict/stale/revoked | `no_suggestion` | `conflict` or `stale_policy` | withhold action text and destinations |

Standalone `get_managed_guidance` uses the same `policy_decision` enum and
omits `cards`.

Clients must render managed guidance with owner, scope, strength, freshness,
override policy, and conflict state. Guidance text is still inert data; the
agent or user must separately decide and authorize any tool action.
Managed guidance text and summaries use the same hostile-content rendering
contract as retrieved cards: no hidden text, no executable tool-call syntax, no
terminal control characters, canonical Unicode normalization, safe copy
behavior, model-context serialization tests, and transport-specific golden
fixtures. Acting agents receive structured policy fields, not free-form
instruction text as executable authority.

No response may reveal whether a hidden repo pattern, customer name,
integration ID, or private environment exists. `no_applicable_guidance`,
unauthorized, expired, revoked, and stale guidance responses use normalized
timing and coarse reason classes. Detailed conflict, detector, and predicate
diagnostics are visible only to authorized admin/reviewer surfaces.

## Lifecycle

Managed guidance lifecycle is separate from card lifecycle. Allowed
transitions are explicit:

```text
draft
  -> pending_review
  -> active

pending_review -> rejected
pending_review -> active

active -> superseded
active -> expired
active -> revoked

superseded -> revoked
expired -> revoked
```

No guidance becomes `active` without an enterprise admin or reviewer approval
that is bound to the exact guidance digest and policy version. Revocation must
take effect on the read path before caches or search projections update.

Guidance serving uses a tenant-local `guidance_epoch`. Activating, expiring,
superseding, or revoking guidance increments the epoch transactionally with the
event write. Cache keys include tenant, namespace, guidance ID, guidance
version, policy version, guidance epoch, effective window, and
`GuidanceContext` digest. `directive`, `routing`, and `guardrail` responses are
not served stale-while-revalidate. Clients must revalidate the guidance epoch
before acting on high-impact guidance and must hide already displayed guidance
when a poll or push signal reports a newer epoch. Each tenant has a kill switch
for `suggestion`, `preference`, `directive`, `routing`, and `guardrail`
delivery.

Search and `get_managed_guidance` responses are read-only. They return policy
state, enforcement class, and non-executable summaries, but they do not mint
action-bound leases. High-impact action requires a separate
`prepare_guided_action` preflight after the acting client has a concrete
`GuidanceActionIntent`. The preflight validates the guidance version,
destination registry entry, host/tool attestation, action parameters,
idempotency key, proof key, transport, and revocation/guidance epochs before
minting a signed guidance lease. Offline clients or clients that cannot run the
preflight must treat high-impact guidance as non-actionable. Action endpoints
reject requests without a current preflight lease and record stale-lease
attempts.

Lease requirements by outcome:

| `policy_decision` | Lease requirement |
|---|---|
| `none` | no lease |
| `advisory` | no lease; local exception allowed only as above |
| `route` | `prepare_guided_action` lease required before any tool call, destination use, or action-bearing card expansion |
| `approval_required` | approval challenge must complete before `prepare_guided_action` can mint a lease |
| `deny` | no lease; action remains blocked |
| `conflict` or `stale_policy` | no lease; refresh or admin resolution required |

The `prepare_guided_action` lease schema is `lease_id`, `signing_key_id`, `tenant_id`,
`namespace_id`, `guidance_id`, `guidance_version`, `policy_version`,
`guidance_epoch`, `actor_subject`, `proof_key_id`, `integration_id`,
`transport`, `operation`, `context_digest`, `destination_version`,
`action_parameter_digest`, `idempotency_key`, `nonce`,
`allowed_action_class`, `issued_at`, `expires_at`, and `signature`. High-impact
leases are one-time or replay-detected. Action requests that rely on managed
routing or directives must include `guidance_lease.lease_id`,
`guidance_lease.signature`, the same `context_digest`, the same operation and
action-parameter digest, and the same idempotency key; missing, reused,
expired, wrong-actor, wrong-proof-key, wrong-transport, wrong-context,
wrong-action, wrong-destination, revoked-epoch, or unknown-key leases fail
closed with `stale_policy` or `deny` and an audit event.

Knudg can enforce guidance only at Knudg-controlled endpoints and host/tool
integrations that attest support for the lease and decision contract. Responses
therefore include an enforcement class:

- `enforced_by_knudg`: Knudg endpoint checks the lease or deny state before the
  side effect.
- `requires_host_enforcement`: an external host/tool must attest it will enforce
  the lease, deny, and cache-invalidation contract before action.
- `advisory_only`: no enforcement point is attested; guidance can inform the
  user/agent but must not be described as blocking external tool execution.

## Intake Safety Gate

The database-side candidate intake path must include an intake safety gate
before admission, redaction, review routing, indexing, or storage of
non-synthetic candidate content. This is a core ingestion contract. Enterprise
governance may configure additional detectors, customer-name lists, private
repository lists, model providers, and reviewer queues.

The gate is a second check after client-side sanitization. It exists because a
user or delegated agent can accidentally submit secrets, customer data, private
repository identifiers, incident details, prompt-injection text, or policy
instructions embedded in logs.

The gate uses deterministic scanners and a no-tool LLM classifier:

- deterministic scanners for credentials, tokens, private keys, cloud account
  identifiers, absolute paths, hostnames, customer names where configured,
  private repo names, high-entropy strings, and dangerous command fragments
- LLM classifier for contextual sensitivity, accidental raw transcript upload,
  customer/incident leakage, internal architecture disclosure, and embedded
  prompt-injection or policy-override attempts
- structured output only, no network access, no tools, no retrieval, no write
  authority beyond returning a verdict

The LLM classifier boundary is protected data processing. Before raw text can
be sent to a classifier, deterministic scanners run first and remove or block
known credential classes. The classifier must run in a private deployment or a
contractual zero-retention inference environment with no provider training,
disabled provider logging where available, tenant-scoped encryption, prompt and
output retention limits, access audit, and purge capability. If these controls
cannot be proven for a deployment, the classifier may receive only derived
features and ambiguous raw content must use the sealed human-review escrow
below or return `redact_then_retry`; it must not be sent to an LLM.

Classifier policy is versioned. A policy manifest records model/provider,
prompt digest, scanner precedence, output schema, confidence handling,
disagreement routing, regression corpus, adversarial fixtures, drift thresholds,
false-negative stop conditions, rollout canary, and rollback rule. Model output
can only choose from the verdict enum and bounded reason-code enum.

Verdicts:

- `accept`: candidate can enter normal admission.
- `redact_then_retry`: store no candidate body; return coarse redaction classes
  and require a new digest.
- `human_review_required`: create a sealed, TTL-bound human-review escrow and
  quarantine metadata; no candidate body, index row, retrieval projection, or
  model exposure is created.
- `reject`: store only a redacted audit event and reason code.

External submit responses are intentionally non-oracular. They return only
coarse classes such as `credential_like`, `private_identifier_like`,
`raw_transcript_like`, `customer_or_incident_like`, `policy_override_like`, or
`classifier_unavailable`. They never return matched values, offsets, detector
names, private repo/customer existence hints, entropy scores, model confidence,
or detailed reason codes. Detailed findings are available only in an authorized
reviewer/admin UI with audit and probing budgets.

The public submit API may collapse sensitive classes to
`unsafe_candidate_or_policy_gate` when the caller does not need remediation
detail. Scanner, classifier, policy, and audit outages use the same outer shape
and normalized retry behavior as sensitive matches. Intake probing budgets are
checked before scanner/classifier work and include subject, tenant, source IP
or equivalent rate identity, idempotency key family, normalized content digest
family, and reason-class family. Budget exhaustion returns the same coarse
shape and records an abuse audit event.

The intake safety gate must fail closed when scanners, classifier, policy
versions, or audit persistence are unavailable. A model verdict can tighten a
decision but cannot approve public publication, bypass redaction, bypass user
consent, or override deterministic scanner findings.

The `submit_candidate` contract must persist an `intake_gate_evaluated` or
`intake_gate_failed_closed` audit event before any candidate body can be stored.
The event includes decision ID, tenant, namespace, actor, protected input
fingerprint, policy versions, scanner versions, classifier policy version,
coarse reason codes, body-storage decision, and correlation ID. The fingerprint
is a tenant-keyed HMAC or equivalent protected digest over canonical ingress,
with key ID, rotation/dual-read rules, and security-only visibility; raw-content
SHA digests must not appear in audit, quarantine, exports, client responses, or
admin search. Database constraints must make `body_stored = false` mandatory
for `redact_then_retry`, `human_review_required`, and `reject`.

`human_review_required` uses two artifacts:

- `candidate_intake`: durable metadata row for idempotency, decision, coarse
  reason classes, protected fingerprint, expiry, and audit correlation.
- `candidate_review_escrow`: optional encrypted single-use raw-content escrow
  for authorized human review only. It is not a candidate body, not indexed, not
  copied to queues or DLQs, not exposed to models, and not readable by agents.
  It has TTL, reviewer step-up auth, access audit, revocation/purge behavior,
  and a body lease that expires after one review session. Escrow can be created
  only after the exact submitted artifact has active user consent with
  `scope=intake_review_escrow` bound to the `intake_submission` protected
  artifact digest.
  Tenant policy may preconfigure the consent surface and reviewer pool, but it
  cannot substitute for user-facing consent unless the submitted artifact, TTL,
  reviewer access, revocation behavior, and purge semantics are identical to the
  canonical consent record. Withdrawal or expiry purges the escrow and leaves
  only the metadata row. If consent or escrow creation is unavailable, the gate
  returns `redact_then_retry` or `retry_later`.

Quarantine metadata is allowlist-only:

- candidate ID or pending intake ID
- tenant and namespace IDs
- actor and delegated integration IDs
- protected input fingerprint, key ID, and canonicalization version
- verdict and coarse reason classes
- scanner, classifier, and policy versions
- body-storage decision
- created timestamp, expiry, correlation ID, and idempotency effect reference

Quarantine metadata must not include user-supplied titles, symptoms, snippets,
paths, repo names, package names not proven public, customer labels, matched
values, detector names, classifier rationale, reviewer queue names derived from
private identifiers, raw prompts, or raw model outputs.

Escrow payloads must not appear in logs, traces, metrics, queues, DLQs, object
storage manifests, prompt logs, audit payloads, cache entries, or temporary
files. Retry and DLQ records for `human_review_required` are metadata-only; if
the escrow expires, the only allowed outcomes are `redact_then_retry`,
`rejected`, or user resubmission.

Intake degraded states:

- `gate_degraded`: a required scanner, classifier, policy, or audit dependency
  is unavailable; no body is stored
- `retry_later`: transient gate dependency failure after bounded retries
- `human_review_queued`: metadata was quarantined and, when enabled, a sealed
  review escrow was created for authorized human review

Gate jobs use bounded per-stage deadlines, retry budgets, DLQ/replay
procedures, model-version canaries, per-tenant model-call budgets, and a hard
cap that fails closed instead of repeatedly calling the classifier.

Core provisional `SubmitCandidate` contract:

This section is the narrative source for the intake safety boundary. It is not
the final OpenAPI/JSON Schema authority. PR-006 must replace the provisional
request/response, scanner, classifier, audit, and transaction-order text with
machine-validated schemas and fixtures before non-synthetic submit can store a
body or move a candidate into admission.

```yaml
operation: submit_candidate
request:
  idempotency_key: required
  namespace_id: required
  candidate_digest: optional client hint; server recomputes protected fingerprint
  submitted_payload: required volatile inline bytes or server-issued opaque upload/stream lease
  client_content_hint: optional, never authoritative
  sanitized_profile: optional bounded object
response:
  decision: accepted | redact_then_retry | human_review_queued | rejected | retry_later
  reason_class: none | unsafe_candidate_or_policy_gate | gate_degraded | quota_or_budget
  correlation_id: required
  idempotency_effect_ref: required
  audit_event_ref: omitted from public clients; present for authorized private clients
transaction_order:
  - validate auth, namespace, idempotency, and quota
  - derive content class server-side
  - canonicalize volatile input and compute protected tenant-keyed fingerprint
  - apply probing budget
  - run deterministic scanners
  - run classifier only when policy and protected-data controls allow it
  - write intake audit event
  - write no candidate body for non-accept verdicts; `human_review_required`
    may create only the sealed review escrow described above
  - for `accepted`, synchronously redact inside the no-log ingress transaction
    and persist only the canonical redacted draft body after redaction succeeds
    and `private_candidate_collection` consent/acknowledgement, protected-data
    durability, and audit persistence are active and PR-006 is no longer
    blocked; this complete prerequisite set is the
    `non_synthetic_body_persistence_gate` for short-lived candidate drafts;
    promotion to `approved_private` or retention beyond the candidate TTL
    separately requires `private_retention` consent;
    asynchronous/bodyless `pending_redaction` for non-synthetic volatile ingress
    is not allowed until a later RFC defines a raw-source storage provider and
    retention consent
```

Idempotent replay with the same key and protected fingerprint returns the same
decision and effect reference. A reused key with a different protected
fingerprint is rejected before scanner/classifier work. Non-synthetic content
cannot use local/synthetic fixture bypasses.

Internal and external decision names are fixed by this mapping:

| Internal gate verdict | External `submit_candidate.decision` | Metric label |
|---|---|---|
| `accept` | `accepted` | `accepted` |
| `redact_then_retry` | `redact_then_retry` | `redact_then_retry` |
| `human_review_required` | `human_review_queued` | `human_review_required` |
| `reject` | `rejected` | `rejected` |
| `gate_degraded` | `retry_later` | `gate_degraded` |

`submitted_payload` is handled inside a volatile no-log ingress boundary until
the gate returns `accepted`. It must be either inline bytes or a server-issued
opaque upload/stream lease bound to tenant, actor, namespace, size,
content-class claim, TTL, and protected input fingerprint. Caller-supplied
URLs, filesystem paths, object-store keys, cross-tenant handles, and arbitrary
remote references are rejected before scanner/classifier work. The payload must
not be written to request logs, traces, metrics, queues, DLQs, object storage,
temp files, prompt logs, or audit payloads. The gateway and application logger
must redact or suppress the field before ordinary request instrumentation.
Scanner/classifier workers receive the payload by memory or an equivalent
encrypted single-use stream lease that expires before retry; failed and
non-accepted submissions retain only protected fingerprints, coarse reason
classes, and the allowlisted quarantine metadata above, except for the sealed
`candidate_review_escrow` used by `human_review_required`.

Content class is server-derived. The default for all agent/client submits is
`non_synthetic`. A submission can be treated as `synthetic` only when the
server verifies a signed synthetic-fixture manifest, test namespace, fixture
digest, generator identity, and non-production audience. Database constraints
must require an intake gate event before any candidate body row unless the row
references a verified synthetic-fixture provenance record.

## Audit And Metrics

Enterprise governance needs separate audit rows for guidance and intake safety:

- guidance created, reviewed, activated, superseded, expired, revoked
- guidance read by agent/client, including scope, policy version, and
  revocation epoch
- guidance conflict or override request
- intake gate verdict, detector versions, policy versions, reason codes, and
  whether any body was stored
- false-positive and false-negative review outcomes for gate calibration

Audit payloads must use allowlisted fields only. They must not store raw body
fragments, matched secret values, private path fragments, customer identifiers,
or full prompts. Security-relevant audit batches are append-only and
tamper-evident through hash chaining or signed batch manifests, and may be
exported to a separate security sink or SIEM. High-volume guidance reads can use
bounded sampling only for non-decision telemetry; policy decisions, conflicts,
overrides, revocations, failed-closed intake events, and body expansions are
mandatory audit events.

Audit operations are capacity-managed separately from product tables. Required
event classes are `security_blocking` for revocation, consent, reviewer publish,
failed-closed intake, guidance deny/conflict, and body expansion;
`policy_decision` for guidance evaluation and override; and `telemetry` for
sampled non-decision metrics. `security_blocking` events are synchronously
durable or the protected operation fails closed. `policy_decision` events may
use a bounded durable buffer only when replay preserves ordering and the
operation response includes the decision ID. Audit storage is partitioned by
tenant and event month or stronger deployment-specific partitioning, has
retention classes by event type, and defines SIEM/export backpressure behavior.

If the primary audit table or export path is unavailable, protected operations
must write a minimal `security_blocking` event to an independent append-only
fallback sink before returning. The fallback event contains only tenant,
namespace, actor class, operation, protected fingerprint or object ID, coarse
reason class, dependency state, timestamp, and correlation ID. If neither the
primary sink nor fallback sink can acknowledge the event, the operation fails
closed and the ingress payload is discarded; no candidate body, guidance lease,
publish, withdrawal, or revocation side effect may commit.

Launch metrics:

- applicable directive retrieval rate
- guidance conflict rate
- override request and approval rate
- stale or revoked guidance attempted-use rate
- intake `redact_then_retry`, `human_review_required`, and `reject` rates
- confirmed sensitive-data miss rate from reviewer audits
- latency and cost added by the intake safety gate

Operational overload contract:

| Priority | Work class | Overload behavior |
|---|---|---|
| P0 | revocation, consent withdrawal, tombstone write, guidance kill switch | reserved capacity; synchronous DB path when queue is degraded |
| P1 | reviewer publish, approval/revocation handoff, failed-closed audit | shed lower priorities first |
| P2 | intake safety gate, guidance evaluation, private search | bounded retries; fail closed with coarse degraded state |
| P3 | indexing, compaction, public reports, telemetry export | pause or enqueue until capacity returns |

Every implementation profile must define absolute deadlines, retry caps, queue
max age, queue max depth, per-tenant concurrency, global classifier call caps,
audit buffer limits, circuit-open criteria, and load-shedding order. If two
dependencies degrade at once, the stricter fail-closed outcome wins.

Enterprise launch is blocked until trusted admin UI exists for guidance
creation, review, revocation, conflict inspection, override approval, and
intake-gate audit review.

## Implementation Contracts

Enterprise guidance implementation requires a dedicated RFC before database
migrations:

- physical schemas for `managed_guidance`, `managed_guidance_events`, guidance
  approvals, override requests, guidance epochs, and audit events
- lifecycle transition table and partial unique indexes for active guidance
- RLS and object-authorization tests for cross-tenant, cross-namespace,
  stale-grant, spoofed-context, and revoked-guidance cases
- closed predicate JSON schema and property tests for overlaps and conflicts
- response schemas for `get_managed_guidance`, combined search guidance,
  conflict, no guidance, stale guidance, and failure-closed states
- migration plan with canary tenant, dual-read/write when needed, rollback,
  old-client behavior, cache invalidation, and revocation replay
- capability rollout states: disabled, shadow, admin-preview, tenant-canary,
  active, paused, revoked
- safe deployment criteria: max affected subjects, compatibility version,
  old-client fail-closed behavior, automatic rollback on conflict, deny,
  stale-lease, audit, or error-rate spikes, and emergency kill-switch drill

Core intake implementation requires a dedicated schema before non-synthetic M1
submission:

- `SubmitCandidate` request and response schema
- forbidden-field handling and coarse external reason-code enum
- scanner output schema and no-tool classifier output schema
- audit event schema and DB constraint proving no body is stored for
  `redact_then_retry`, `human_review_required`, or `reject`
- quarantine metadata and optional sealed review escrow schema for
  `human_review_required`
- idempotent replay behavior by idempotency key and protected fingerprint
- tests for every verdict, dependency outage, DLP-oracle resistance, body-store
  constraint, and reviewer outcome path
- acceptance fixtures listing auth context, protected-fingerprint family,
  scanner result, classifier result, expected DB writes, expected response,
  expected audit event, and expected absence or presence of body/index rows

Before PR-006 or PR-007 can move out of `blocked`, the RFC/schema must replace
the provisional YAML shapes above with machine-validated JSON Schema or OpenAPI
fixtures. Until then, `submit_candidate` for non-synthetic content and
`get_managed_guidance` for active enterprise policy remain non-operational.
