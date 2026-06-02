# Agent Access

Agent access is part of the product core, not a later integration layer. The product must expose one narrow, auditable contract before adding more transports.

## Target Transport Contract

The target external agent contract supports:

- local CLI using HTTPS to the Knudg API
- MCP over Streamable HTTP for protected tools
- optional local stdio wrapper that launches the CLI but does not hold long-lived credentials

The stdio wrapper is convenience glue only. Authorization is enforced by the HTTPS API boundary. The wrapper must not accept arbitrary remote server URLs unless the user explicitly configures and pins them.

HTTP MCP authorization follows the MCP authorization model for protected resources. Protected operations return HTTP `401` at the transport boundary, not tool-level soft errors.

Milestone scope is separate from the target contract. M3 may ship an internal HTTPS-only harness for dogfood and CI. Full external MCP and hook integrations remain M5 readiness items until the implementation checklist is complete.

## Summoned Role Access Pattern

Before broad MCP or hook rollout, Knudg may be used through per-task summoned
roles. The main agent starts the user's task and summons bounded Knudg roles in
parallel. Role calls are short-lived and operation-specific:

- `searcher`: build or consume a sanitized `SearchProfile`, search eligible
  fixtures or authorized corpora, and return a compact verdict
- `writer`: propose a candidate draft or approval handoff after an outcome is
  known
- `nudger`: decide whether to offer a retrieval panel or writer draft
- `reviewer`: evaluate fit, staleness, or safety risk for a retrieved card

The summoned role pattern is not a bypass around the transport, auth,
revocation, consent, or intake contracts in this document. It is a client
orchestration pattern that keeps retrieved experience outside the main prompt
unless the main agent explicitly opens a retrieval panel or trusted handoff.

The common role verdict is intentionally smaller than `search_similar` or
`submit_candidate`:

- `schema_version`
- `role`
- `status`: `abstain`, `no_actionable_signal`, `suggestion_available`,
  `draft_candidate_possible`, `approval_handoff_possible`, or `degraded`
- `confidence`
- `risk`
- `reason_summary`
- `recommended_action`: `do_nothing`, `offer_retrieval_panel`,
  `offer_writer_draft`, `offer_approval_handoff`, or
  `ask_user_before_continuing`
- optional opaque refs

Role verdicts must not include raw card bodies, raw transcripts, full stack
traces, private paths, secrets, tokens, executable command text, package
install lines, or private repo names. They also must not instruct the main
agent to run a command or edit a file.

`agent-subconscious` or another sidecar may later act as an event source for
these roles, but it is optional plumbing. The canonical Knudg authority remains
the server-side schema, consent, approval, revocation, retrieval, and
publication contracts.

## MCP Authorization Profile

HTTP MCP endpoints are OAuth protected resources. A missing, expired, malformed, or wrong-audience token returns `401` with `WWW-Authenticate` and a Protected Resource Metadata URI. A valid token that lacks tenant, namespace, object, transport, or operation scope returns `403` with no extra object-existence detail.

Knudg requires OAuth resource indicators for MCP clients. Access tokens must be audience-bound to the exact Knudg resource URI and environment, not a generic API audience. Resource metadata, authorization-server metadata, and redirect targets are fetched only from an allowlist of pinned HTTPS origins. Discovery follows redirects only within the same allowed origin, rejects private/link-local/loopback IP resolution except explicit local development origins, caps redirect depth, and never follows user-controlled tool output as a URL.

Token passthrough is prohibited. MCP servers must validate tokens issued for Knudg and must not forward caller bearer tokens to downstream APIs. Any downstream access uses a separate exchange or service credential with least privilege and a distinct audience.

## Credential Model

Agent clients use delegated user tokens with these default constraints:

- TTL: short-lived and private-deployment configured; exact values are not
  public-facing material
- refresh: no refresh token in MVP agent clients
- audience: exact Knudg protected resource URI plus explicit environment, such as `prod` or `dev`
- scope: tenant, namespace, operation, and transport
- storage: OS keychain only; never plaintext config files
- binding: sender-constrained token proof plus client instance ID and integration ID
- revocation: server-side token denylist checked on every protected request
- billing: paid/rerank scopes are separate from read/search scopes

Read and write scopes are separate. A token that can search private cards cannot submit, approve, publish, bill, or revoke unless those scopes are explicitly present.

Delegated tokens are sender-constrained for MCP and CLI use. Each request signs method, URL, body digest, audience, nonce, and issued-at timestamp; servers reject missing proofs, stale timestamps, nonce reuse, proof/key mismatch, and cross-resource replay. Idempotency keys do not replace replay protection.

DEC-014A must choose a concrete sender-constrained token profile before any M3
protected-data harness runs. Until then, M3 retrieval may use only synthetic or
public fixtures. DEC-014B governs broad external MCP/CLI rollout before M5.
DPoP is the default for CLI/MCP public clients unless the relevant auth RFC
accepts mTLS or another profile. The profile must define JWK or certificate
binding, accepted algorithms, canonical URL rules, nonce replay store keys,
replay window, clock skew, key rotation, client-instance records, proof-key
records, device revocation, and interop tests.

Token renewal UX:

- expired read tokens return a non-interactive `reauth_required` state with no
  private data
- expired write tokens preserve idempotency keys and require a trusted
  reauthentication handoff before retry
- clients must not store refresh tokens in MVP
- repeated prompts are capped by policy; exceeding the cap disables the
  protected workflow until the user explicitly resumes it
- lost devices and proof keys can be revoked from the trusted account surface

## Protected Operations

Anonymous public search is not an MCP protected operation. It is a separate
public REST route contract, disabled until the M6 public-wedge privacy gates
and DEC-013 are accepted. When enabled, it uses its own rate identity, generic
abstention semantics, and public-search privacy budget. Authenticated MCP/CLI
`search_similar` requires a valid scoped token and returns `401` for
missing/invalid tokens.

Agent-callable operations are `search_similar`, `get_managed_guidance`,
`prepare_guided_action`, `get_card`, `submit_candidate`,
`ask_publication_from_private`, `ask_approval`, `ask_revocation`, and
`report_harmful_card` within their scopes.
Human-session and reviewer/admin completion endpoints are separate route groups
from MCP/tool-callable operations and are never minted into delegated agent,
MCP, CLI wrapper, worker, or tenant-admin tokens.
`complete_private_retention_approval`,
`complete_publication_from_private_request`, and
`complete_publication_approval` are trusted browser or OS-mediated user-session
endpoint contracts; delegated agent tokens, MCP tools, terminal transcripts,
background workers, and CLI command collection cannot call them or collect the
final approval phrase.

Creating or retrying an approval handoff is not consent. CLI and MCP clients may
open the trusted consent surface, but only that surface may complete step-up
authentication, run the comprehension gate, and record approval for the exact
artifact digest and policy set. A handoff cannot complete public publication
consent, future team-publication consent, or team namespace-sharing consent,
cannot mark a card public-search eligible, and cannot substitute for the
separate reviewer publish action.

Milestone capability:

| Operation | M3 internal protected harness | M5 external MCP/CLI | Enterprise milestone |
|---|---|---|---|
| `search_similar` | synthetic/public or protected only after DEC-014A | yes after DEC-014B | yes |
| `submit_candidate` | synthetic/local only until PR-006 | non-synthetic only after PR-006 and `non_synthetic_body_persistence_gate` | yes with tenant detector policy |
| `ask_publication_from_private` | handoff creation only | handoff creation only after PR-006, private source read gates, public publication gates, and redaction/review gates | handoff creation only |
| `get_managed_guidance` | disabled; returns empty `managed_guidance` | disabled unless PR-007 and enterprise RFC are accepted | enabled after PR-007 |
| `prepare_guided_action` | disabled; no action leases | disabled unless PR-007 and enterprise RFC are accepted | enabled after PR-007 for high-impact guided actions |
| `get_card` | protected only after auth/revocation gates | yes within scope | yes |
| `ask_approval` / `ask_revocation` | handoff creation only | handoff creation only | handoff creation only |

Disabled operations return a capability-disabled response with no policy,
card-body, destination, or existence detail. Listing an operation in the target
contract does not make it launchable before its milestone gate.

Agent-callable operations:

| Operation | Purpose | Required scope | Idempotency | Timeout | Retry |
|---|---|---|---|---|---|
| `search_similar` | Search authorized corpus from an outbound query profile | `search:{namespace}` | required `request_id` | private operations deadline | budgeted once |
| `get_managed_guidance` | Fetch scoped enterprise guidance such as directives, routing records, preferences, and guardrails | `guidance:read:{namespace}` | optional request ID | private operations deadline | budgeted once |
| `prepare_guided_action` | Mint a one-time lease for a concrete high-impact guided action after guidance read and action intent validation | `guidance:act:{namespace}` | required | private operations deadline | no automatic retry after lease issuance |
| `get_card` | Fetch a specific authorized card version | `read:{namespace}` | deterministic read; optional request ID | private operations deadline | yes |
| `submit_candidate` | Submit a private candidate for admission | `submit:{tenant}` | required | private operations deadline | yes |
| `ask_publication_from_private` | Create a trusted source-owner handoff for deriving a public publication candidate from an existing retained private card | `approval:create` plus `read:{namespace}` | required | private operations deadline | yes |
| `ask_approval` | Create a trusted human approval handoff for a redacted artifact | `approval:create` | required | private operations deadline | yes |
| `ask_revocation` | Create a trusted human revocation handoff for any consent-bearing subject | `revocation:create` | required | private operations deadline | yes |
| `report_harmful_card` | Report prompt injection, stale, unsafe, or misleading card | `report` or public report rate identity | required for authenticated callers; generated per public report rate identity for anonymous public reports | private operations deadline | yes |

Trusted human-session and reviewer/admin completion operations:

| Operation | Purpose | Required scope | Allowed actor/transport | Delegated-token allowed | Idempotency | Timeout | Retry |
|---|---|---|---|---|---|---|---|
| `reviewer_publish` | Move a user-approved reviewed card into public publication | `review:publish` | assigned reviewer in reviewer console/API | no | required | private operations deadline | idempotent result only |
| `complete_candidate_collection_acknowledgement` | Complete trusted acknowledgement/consent for short-lived private candidate collection | `approval:complete` | trusted browser/OS human session | no | required | private operations deadline | yes |
| `complete_private_retention_approval` | Complete trusted user approval for exact private retention of the candidate/card artifact | `approval:complete` | trusted browser/OS human session | no | required | private operations deadline | yes |
| `complete_team_namespace_grant` | Complete trusted user approval for a team namespace grant on the exact retained private artifact | `approval:complete` | trusted browser/OS human session | no | required | private operations deadline | yes |
| `complete_intake_review_escrow_consent` | Complete trusted user consent for short-TTL sealed human review escrow of the exact submitted artifact | `approval:complete` | trusted browser/OS human session | no | required | private operations deadline | yes |
| `complete_publication_from_private_request` | Complete trusted source-owner approval to create a new public publication candidate from an existing retained private card | `approval:complete` | trusted browser/OS human session | no | required | private operations deadline | yes |
| `complete_publication_approval` | Complete trusted user approval for the exact redacted public artifact | `approval:complete` | trusted browser/OS human session | no | required | private operations deadline | yes |
| `revoke_subject` | Human-session endpoint that revokes a tenant, namespace, card, card version, source artifact, derived artifact, search index manifest/generation, private candidate collection, private retention, raw/source retention, model/eval use, commercial-derived use, or consent record | `revoke:own` or `revoke:any` | trusted browser/OS human session or break-glass console | no | required | private operations deadline | yes |
| `withdraw_publication_approval` | Human-session endpoint that withdraws approved public publication before reviewer publish | `revoke:own` | trusted browser/OS human session | no | required | private operations deadline | yes |

The reviewer/admin and human-session route group rejects MCP transport,
stdio-wrapper transport, delegated-agent subjects, worker subjects, and tenant
admin subjects unless an explicit break-glass case authorizes the exact
operation. Negative tests must prove those subjects cannot emit
`reviewer_published`, `approval_withdrawn`, consent termination, or tombstone
events by presenting ordinary protected-operation scopes.

Minimum route authorization predicates:

| Operation | Required object predicates |
|---|---|
| `search_similar` | token audience matches resource; tenant membership active; namespace grant active; requested namespace set is server-validated; revocation fence and circuit state are current before candidate generation |
| `get_managed_guidance` | PR-007 and enterprise RFC accepted; token audience matches resource; tenant membership active; namespace grant active; server-attested `GuidanceContext` matches guidance scope predicates; guidance is active, approved, within effective window, not revoked, not stale for the tenant guidance epoch, and conflict checked before delivery |
| `prepare_guided_action` | PR-007 and enterprise RFC accepted; prior guidance decision is current; `GuidanceActionIntent` schema validates; destination registry entry is active and pinned; host/tool attestation supports enforcement; proof key, transport, operation, action parameters, idempotency key, guidance epoch, and revocation epoch match the lease request |
| `get_card` | caller can read the namespace; card/version belongs to tenant and namespace; card, version, namespace, and tenant are not tombstoned; safety metadata exists; body expansion policy allows the caller, risk class, verification state, and transport |
| `submit_candidate` | caller is a human or delegated agent for the tenant; namespace allows submit; intake safety gate, quota/admission/circuit gates pass; idempotency key belongs to the same server-protected input fingerprint |
| `ask_publication_from_private` | caller can read the private source card or is the source owner; source card is not revoked; private-retention consent is current; target public namespace is allowed; creates only a trusted handoff and does not create a public candidate, copy a private body, or expose source identifiers |
| `ask_approval` | caller owns the candidate or is assigned reviewer/admin; artifact digest, namespace, subject, policy, and challenge scope match the current card version; no stale challenge is reused |
| `ask_revocation` | caller owns the consent-bearing subject or has assigned admin/break-glass scope; subject exists inside tenant; requested effect maps to a supported consent termination or tombstone subject |
| `reviewer_publish` | actor is assigned reviewer; card is `approved_for_publication`; active consent matches exact artifact/policy/challenge; reviewer, abuse, safety, namespace, and revocation gates still pass |
| `complete_candidate_collection_acknowledgement` | trusted human session subject matches challenge subject; signed challenge, source class summary, default TTL, collection policy set, comprehension gate, expiry, namespace, revocation fence, and step-up auth are current |
| `complete_private_retention_approval` | trusted human session subject matches challenge subject; signed challenge, artifact digest, private-retention policy set, comprehension gate, expiry, namespace, revocation fence, and step-up auth are current |
| `complete_team_namespace_grant` | trusted human session subject matches challenge subject; signed challenge, artifact digest, reader group, namespace, purpose, TTL, policy set, comprehension gate, expiry, and revocation fence are current |
| `complete_intake_review_escrow_consent` | trusted human session subject matches challenge subject; signed challenge binds the `intake_submission` protected artifact digest, escrow TTL, reviewer pool, policy set, expiry, revocation fence, and step-up auth |
| `complete_publication_from_private_request` | trusted human session subject is the source owner/subject; signed challenge binds source card version, source digest, target public namespace, redaction policy, reviewer exposure, TTL, expiry, revocation fence, and step-up auth; creates a new public candidate at `candidate_created` and a non-public `derived_from_private_card` edge only when the redacted first-version payload is ready; otherwise records only a retryable handoff or redaction work item without creating a card row |
| `complete_publication_approval` | trusted human session subject matches challenge subject; signed challenge, artifact digest, policy set, comprehension gate, expiry, namespace, revocation fence, and step-up auth are current |
| `revoke_subject` | trusted human session or break-glass case matches subject; consent/tombstone target belongs to tenant; step-up auth passes; cleanup policy and digest are current |
| `withdraw_publication_approval` | trusted human session subject matches active public consent; card is not yet published; digest and consent record match; reviewer publish has not committed |
| `report_harmful_card` | caller can see the returned card metadata or scoped public card handle; report reason is bounded; per-card, per-reporter, per-rate-identity, and per-fingerprint-family budgets pass; duplicate or brigaded reports merge without changing visibility directly |

Negative authorization tests cover horizontal object access, stale membership,
stale namespace grants, revoked grants, cross-namespace IDs, unassigned
reviewers, delegated-agent attempts to publish/revoke/withdraw, and tenant-admin
attempts to satisfy user consent.

`get_card` body expansion is per-request server authorization by default, not a
transferable client lease. Expansion requires current safety classification,
verification state, revocation fence, consent/retention state, caller transport,
delegated-token policy, and renderer conformance. High-risk or quarantined
cards without an active verification record return only a blocked/withheld
state and no command, package, repository, URL, token shape, credential,
migration, or security-sensitive detail. Delegated-agent tokens cannot expand
unverified high-risk bodies. If a deployment later introduces a signed body
lease, it must be single-use and bound to card version, subject, transport, risk
class, verification state, revocation epoch, expiry, and expansion request ID.
Every full-body expansion records an audit event with card version, body policy
version, caller, transport, request ID, and revocation epoch.

All write operations require an idempotency key. Retried writes with the same request digest return the original effect. A reused key with a different digest is a hard error.

Per-operation retry and idempotency rules:

- `search_similar`: idempotent by outbound query profile, scope, retrieval policy, and required request ID; retry at most once within the absolute search deadline, and return `no_suggestion` for stale auth, stale revocation epoch, safety uncertainty, or an exhausted budget.
- `get_managed_guidance`: idempotent by request context, scope, policy version, revocation epoch, and optional request ID; retry at most once, and fail closed with no guidance when authorization, conflict, freshness, or revocation state is uncertain.
- `prepare_guided_action`: idempotent by `GuidanceActionIntent`, proof key,
  operation, destination version, action-parameter digest, and idempotency key
  before lease issuance; after a lease is issued, retry can return only the
  same unexpired lease or a stale/used result and must not mint a second lease
  for changed action parameters.
- `get_card`: idempotent by card ID, version, scope, and revocation epoch; retry only transient transport/storage failures, and fail closed when the body or revocation freshness cannot be proven.
- `submit_candidate`: idempotent by idempotency key and server-protected input
  fingerprint; same key/fingerprint returns the existing intake/admission
  result, and same key/different fingerprint is rejected. Client-supplied
  `candidate_digest` is a non-authoritative hint and cannot participate in
  uniqueness, replay, audit visibility, or conflict decisions.
- `ask_publication_from_private`: idempotent by source card version, target
  namespace, redaction policy, and idempotency key; retry returns the existing
  handoff and never creates a public candidate.
- `complete_publication_from_private_request`: idempotent by signed challenge,
  source card version, source digest, target namespace, redaction policy, and
  idempotency key; retry returns the same public candidate reference and never
  mutates the source private card. This is not an agent-callable operation.
- `ask_approval`: idempotent by idempotency key, subject, namespace, artifact digest, and policy set; retry returns the existing handoff or its completed/expired state, never a new challenge for changed content.
- `complete_candidate_collection_acknowledgement`, `complete_team_namespace_grant`, and `complete_intake_review_escrow_consent`: idempotent by signed challenge, artifact or source-class digest, scope, and policy set after the trusted surface completes step-up authentication and any required comprehension gate; retry can report the recorded consent result but cannot re-run or broaden consent. These are not agent-callable operations.
- `complete_private_retention_approval`: idempotent by signed challenge and artifact digest after the trusted surface completes step-up authentication and the comprehension gate; retry can report the recorded private-retention consent result but cannot re-run or bypass consent. This is not an agent-callable operation.
- `complete_publication_approval`: idempotent by signed challenge and artifact digest after the trusted surface completes step-up authentication and the comprehension gate; retry can report the recorded consent result but cannot re-run or bypass consent. This is not an agent-callable operation.
- `reviewer_publish`: idempotent by idempotency key and approved artifact digest; retry can report the existing publish result only if all review, consent, revocation, abuse, and namespace gates still match.
- `ask_revocation`: idempotent by idempotency key, subject type, subject ID, artifact/consent digest, and revoke intent; retry returns the existing human handoff and never creates a tombstone or consent termination. Not-found, unauthorized, stale, already-revoked, and unsupported-subject cases use the same outer handoff-unavailable shape, normalized timing, bounded subject-ID grammar, probing budgets, and audit so delegated clients cannot enumerate subjects.
- `revoke_subject`: idempotent by subject type, subject ID, artifact/consent digest, and revoke intent after the trusted human session completes step-up authentication; retry returns the existing tombstone or consent-termination state, and retrieval/processing remains blocked even if cleanup retries are pending. This is not an agent-callable operation.
- `withdraw_publication_approval`: idempotent by consent record ID, card version, artifact digest, and withdrawal intent after the trusted human session completes step-up authentication; retry returns the existing `approval_withdrawn` result and cannot publish, keep private, or create a new consent grant. This is not an agent-callable operation.
- `report_harmful_card`: idempotent by reporter or anonymous public report rate
  identity, scoped public handle or authorized card version, reason class, and
  request ID; duplicate reports merge counters or audit records without changing
  card visibility directly. Report counters can route reviewer attention but
  cannot demote, hide, or revoke a card until an authorized review/safety gate
  validates the report.

Public harmful-card reports use a separate abuse-resistant queue from emergency
revocation, consent, and safety lanes. Anonymous report volume cannot consume
emergency revocation capacity. Public report routing requires per-card and
per-fingerprint caps, duplicate/brigade detection, reviewer-load circuit
breakers, and a challenge or proof-of-work mechanism after anomaly thresholds
if anonymous reporting is enabled.

`complete_private_retention_approval` is a user-consent operation for private
retention, not a publication operation. It can move a card from
`awaiting_user_approval` to `approved_private` only when the signed challenge
matches the exact artifact digest, private-retention scope, and policy set.

`complete_publication_approval` is a user-consent operation, not a publish operation. It can move a card from `awaiting_user_approval` to `approved_for_publication` only when the signed challenge matches the exact redacted digest and policy set.

`reviewer_publish` is reviewer-only. It can move `approved_for_publication` to `published` only after review, redaction, user approval, abuse checks, and namespace eligibility are still valid. It must not complete or bypass user consent.

An agent, worker identity, MCP tool call, or background worker may create an approval or revocation handoff, but cannot collect the final approval phrase, complete consent, revoke, or publish. Delegated agent tokens must be denied `revoke:own` and `revoke:any`; they can only request `revocation:create`. The approval and revocation challenges are single-use. A network retry with the same idempotency key and request digest can return the already-completed result, but must not create a second approval, revocation, consent termination, or publish effect or allow a changed artifact to reuse the challenge.

Trusted consent/revocation surfaces have a minimum contract even when the
detailed UX lives in the consent document. Challenge creation returns only a
handoff ID, opaque subject handle, digest, expiry, allowed consent scope, and
trusted-surface URL or OS-mediated handoff. Completion requires step-up auth,
current artifact digest, active challenge, comprehension result, accessibility
compatible form completion, and current revocation fence. Outcomes are
`completed`, `withdrawn`, `expired`, `cancelled`, `superseded`, or
`handoff_unavailable`. Subject selection for revocation uses bounded opaque
handles; nonexistent, unauthorized, stale, already-revoked, and unsupported
subjects share the same outer failure shape. Completion writes the consent
event, tombstone or withdrawal event, and audit event in one serializable
transaction before any publish, share, or purge effect can proceed.

Retry semantics are budgeted, not additive. `search_similar` has one absolute
private operations deadline across all attempts. A retry is allowed only for
explicit transient classes, with jitter, and only when the scoped circuit is
closed and the response does not contain `rate_limited`, `service_degraded`, or
a `Retry-After` that exceeds the remaining deadline.

Paid public-card retrieval requires a separate billing or paid-rerank scope and must disclose paid retrieval to the user or tenant according to the consent surface. That disclosure does not grant commercial reuse, resale, curated-pack inclusion, sponsorship, model/eval use, or other derived commercial rights; those require separate explicit commercial consent on the exact artifact and terms.

## Protected Operation Outage Matrix

Protected operations fail closed for auth, revocation, consent, and safety uncertainty. Search operations may degrade to thinner retrieval or no suggestion; write operations preserve idempotency and either commit once or return a retryable/degraded reason.

| Outage | Search/read behavior | Write behavior | Required degraded reason |
|---|---|---|---|
| Auth provider unavailable | No protected data; token validation uncertainty blocks request | Block writes before side effects | `auth_required` or `service_degraded` |
| Revocation fence unavailable | No suggestion and no cached card body; reject stale epoch | Block writes that could publish or approve | `stale_or_revoked` |
| Vector index unavailable | Fall back to FTS/exact, then no suggestion | Candidate submission may continue if queue healthy | `service_degraded` |
| Reranker unavailable or over budget | Return hybrid/exact results without rerank label | No effect on writes | `service_degraded` only if quality gate requires rerank |
| Queue unavailable | Search/read can continue from current projections | Block admission, approval, publish, revoke unless synchronous tombstone path is healthy | `service_degraded` |
| Object storage unavailable | Search metadata may continue; card bodies/artifacts requiring storage fail closed | Block raw/source artifact writes and approval challenge creation | `service_degraded` |
| Postgres unavailable | No protected operation succeeds | No protected operation succeeds | `service_degraded` |
| Index generation unknown | Exact/FTS only if authorization and revocation are certain; otherwise no suggestion | Pause index-affecting writes after durable event commit policy is confirmed | `stale_or_revoked` or `service_degraded` |

Emergency `revoke_subject` has the highest protected-operation priority, but it is still a trusted human-session or break-glass endpoint, not a delegated agent operation. If the queue is degraded but Postgres is available, it must write the tombstone or consent termination synchronously and enqueue index/cache/processing cleanup for later reconciliation.

## Hook Events

Minimum hook events:

- `before_work`: optional bootstrap search before the agent starts a task
- `during_work`: retrieval-panel delivery during an active task
- `after_solve`: writer candidate generation after a solved, failed-only, or unknown-clarified case
- `before_prompt`: non-MVP inline hint only after hostile-card red-team approval and rollout enablement

Hook payloads must be sanitized outbound query profiles. They must not include raw logs, full stack traces, private paths, private repo names, secrets, tokens, full file contents, or customer identifiers.

## Search Response Contract

Every search response returns a common envelope:

- `decision`: `show` or `no_suggestion`; this is card-display state, not
  managed-policy state
- `policy_decision`: for authenticated enterprise/team clients only, `none`,
  `advisory`, `route`, `approval_required`, `deny`, `conflict`, or
  `stale_policy`
- `delivery_mode`: `bootstrap`, `retrieval_panel`, `inline_hint`, or `no_suggestion`; `inline_hint` is non-MVP and must downgrade to `retrieval_panel` or `no_suggestion` until its hostile-card gate passes
- `abstention_reason`: for authenticated private/team clients only, `low_confidence`, `no_authorized_match`, `safety_gate`, `stale_index`, `rate_limited`, `service_degraded`, or `none`; public/anonymous clients receive only `generic_abstention`, coarse retry class, or `none`
- `consent_state`: for authenticated private/team clients only, `private`, `awaiting_user_approval`, `approved_for_publication`, `published`, `revoked`, or `withheld`; public/anonymous clients must not receive this field
- `threshold_version`: public/anonymous clients receive only an opaque public threshold label
- `served_from`: `exact`, `fts`, `vector`, `hybrid`, `cache_metadata`, or `none`
- `latency_budget_ms`
- `managed_guidance[]`: authenticated enterprise/team clients only; omitted or
  empty when enterprise guidance is disabled, not authorized, stale, or absent
- `cards[]`

Managed guidance items include:

- guidance ID and version
- guidance type: `instruction`, `routing`, or `guardrail`
- strength: `suggestion`, `preference`, `directive`, or `deny`
- structured decision: `suggest`, `prefer`, `route`,
  `require_human_approval`, `deny`, or `conflict`
- owner and approver summary
- policy version and guidance epoch
- effective window and freshness
- scope digest and server-attested context digest
- override policy
- conflict state
- non-executable instruction summary when policy allows display
- `enforcement_class`: `enforced_by_knudg`, `requires_host_enforcement`, or
  `advisory_only`

Public/anonymous responses never include `managed_guidance`. Unauthorized,
expired, revoked, stale, no-match, and conflict cases normalize timing and
reason shape so callers cannot enumerate private repo patterns, environment
labels, integration IDs, cloud accounts, or guardrail existence.

Canonical mapping for guidance outcomes:

| `policy_decision` | Card `decision` | Response rule |
|---|---|---|
| `none` | normal retrieval result | no guidance fields beyond empty array |
| `advisory` | normal retrieval result | non-blocking guidance may render |
| `route` | normal retrieval result | high-impact action requires `prepare_guided_action` before tool use |
| `approval_required` | `no_suggestion` for action-bearing card bodies | omit executable details and destination text |
| `deny` | `no_suggestion` | omit cards, destinations, and action text |
| `conflict` | `no_suggestion` | return coarse conflict state only |
| `stale_policy` | `no_suggestion` | require refresh; no cached guidance body |

Search and `get_managed_guidance` do not return `guidance_lease`. Action-bound
leases are minted only by `prepare_guided_action` after a concrete
`GuidanceActionIntent` validates.

Guidance lease fields are `lease_id`, `signing_key_id`, `tenant_id`,
`namespace_id`, `guidance_id`, `guidance_version`, `policy_version`,
`guidance_epoch`, `actor_subject`, `proof_key_id`, `integration_id`,
`transport`, `operation`, `context_digest`, `destination_version`,
`action_parameter_digest`, `idempotency_key`, `nonce`,
`allowed_action_class`, `issued_at`, `expires_at`, and `signature`. Clients
must pass the lease to any action endpoint that relies on managed routing or
directives. High-impact leases are one-time or replay-detected. Missing,
reused, expired, wrong-actor, wrong-proof-key, wrong-transport, wrong-context,
wrong-action, wrong-destination, revoked-epoch, or unknown-key leases fail
closed and return `stale_policy` or `deny`.

`submit_candidate` response shape:

This is the operation-level response taxonomy. It is intentionally not the
final `SubmitCandidate` request/response schema authority; PR-006 must publish
the machine-validated contract before non-synthetic body persistence is
enabled.

- `decision`: `accepted`, `redact_then_retry`, `human_review_queued`,
  `rejected`, or `retry_later`
- `reason_class`: `none`, `unsafe_candidate_or_policy_gate`,
  `gate_degraded`, or `quota_or_budget`
- `correlation_id`
- `idempotency_effect_ref`
- optional authorized-only `audit_event_ref`

The response never includes matched text, detector names, private identifier
existence, model confidence, scanner offsets, classifier rationale, or queue
names derived from sensitive input.

Canonical search/read response display mapping:

This table applies only to search/read envelopes whose `decision` field is
`show` or `no_suggestion`. It does not apply to `submit_candidate`, which uses
the separate `accepted | redact_then_retry | human_review_queued | rejected |
retry_later` decision enum above.

| Canonical search/read condition | Internal reason | Authenticated display | Public display | LP mock label |
|---|---|---|---|---|
| `decision=show`, `delivery_mode=retrieval_panel` | authorized candidate/card evidence | trust label plus retrieval panel | not used until public gates pass | `candidate_card` |
| `decision=no_suggestion`, `delivery_mode=no_suggestion` | no authorized match, low confidence, private rare fingerprint, redaction, not indexed, revoked, stale, or safety uncertainty | specific allowed abstention reason only inside tenant boundary | generic `NO_SUGGESTION` with normalized retry class only | `no_suggestion` |
| `decision=no_suggestion` | safety gate or high-risk hold | `Unsafe until reviewed` / withheld | generic `NO_SUGGESTION` | `safety_withheld` only for authenticated/private mock |
| `decision=no_suggestion` | service degraded or dependency circuit open | `service_degraded` | generic `NO_SUGGESTION` with normalized retry class | `service_degraded` |
| `decision=no_suggestion` | caller or route budget exhausted | `rate_limited` | generic `NO_SUGGESTION` with normalized retry class | `rate_limited` |

Fixture values not listed in this table are invalid.

`consent_state` is a response projection, not the canonical lifecycle status.
It is derived from canonical status, active consent records, safety review
state, and the revocation fence:

| Canonical source | Response `consent_state` |
|---|---|
| private candidate, pending admission/redaction/review, approved_private, or discard_pending during undo | `private` |
| awaiting_user_approval | `awaiting_user_approval` |
| approved_for_publication | `approved_for_publication` |
| publication_withdrawn | `withheld` until separate private-retention decision or revocation |
| public indexed_hot/indexed_main projection with active `public_publication` consent and not revoked | `published` |
| approved_private, or private/team indexed_hot/indexed_main projection with active private/team consent and not revoked | `private` |
| revoked or tombstoned | `revoked` |
| safety gate, high-risk verification hold, or policy hold | `withheld` |

Clients must not treat `consent_state` as a writeable lifecycle state or source
of truth.

Authenticated tenant-bound responses may additionally include:

- `index_generation`
- `revocation_epoch`

Public/anonymous responses must not include raw index generations,
revocation epochs, source event ranges, ranking signal names, suppressed
feature names, candidate counts, or private diagnostic reasons.

Authenticated tenant-bound card items include:

- card ID and card version
- namespace
- outcome type
- quality state
- trust label
- freshness status
- provenance summary
- deprecated, disputed, unsafe, or high-risk flags
- source event range
- signals used for ranking

Public/anonymous card items include only safe display fields:

- scoped public card handle and display version
- namespace public label
- outcome type
- quality state
- trust label
- freshness label
- provenance summary safe for public display
- deprecated, disputed, unsafe, or high-risk flags

Public handles are opaque route-scoped identifiers, not internal card IDs. They
must be non-resolvable outside the exact public route, rate-limited, rotatable
when a privacy incident requires it, and unmappable to tenant, namespace,
database, or audit identifiers.

Search explanations share the same audience split. Public/anonymous `why`
responses may expose only coarse match class, safe public facets already present
in the result, trust/freshness labels, and generic safety withholding labels.
They must not expose ranking signal names, weights, raw thresholds, source
event ranges, candidate counts, suppressed terms, private diagnostics,
revocation epochs, or index generations. Authenticated private/team `why`
responses may include only facets and consent/safety/recovery states the caller
is authorized to read inside the tenant boundary. Reviewer/admin explanations
are scoped to assigned review or break-glass cases.

## Display Labels

Agent and human surfaces must use the same trust labels:

- `Verified fix`
- `Repeated fix`
- `Single-session clue`
- `Known failed path`
- `Inconclusive`
- `Clarified unknown`
- `Disputed`
- `Deprecated`
- `Unsafe until reviewed`

These labels are presentation requirements, not just UI copy. They prevent solved, failed-only, unknown, and disputed cards from being shown as equivalent answers.

Required microcopy:

- `Verified fix`: "Verified in a reviewed environment. Still check fit for your repo."
- `Repeated fix`: "Seen work more than once. Not guaranteed here."
- `Single-session clue`: "One observed case. Treat as a clue, not an answer."
- `Known failed path`: "Known not to work in this context."
- `Inconclusive`: "Evidence did not settle the outcome."
- `Clarified unknown`: "What is known and still unknown."
- `Disputed`: "Conflicting evidence. Do not treat as authoritative."
- `Deprecated`: "Outdated or replaced. Prefer newer guidance."
- `Unsafe until reviewed`: "Withheld until safety review finishes."

Trust-label precedence is deterministic. `Revoked` and withheld high-risk
states block display. Then `Unsafe until reviewed`, `Deprecated`, `Disputed`,
and `Known failed path` override positive labels. `Verified fix` can appear
only when lifecycle, revocation, safety, freshness, and dispute checks pass.
`Repeated fix`, `Single-session clue`, and `Clarified unknown` are secondary
confidence labels. Every label needs equivalent non-color text and ARIA/name
metadata in human surfaces.

Trust label derivation:

| Condition | Label |
|---|---|
| tombstoned, revoked, or safety withheld | no card body; use blocked/withheld state |
| high-risk or quarantined and not verified in reviewer/internal queue | `Unsafe until reviewed` |
| lifecycle `deprecated` | `Deprecated` |
| `quality_state = disputed` or active contradiction flag | `Disputed` |
| `outcome_type = failed_only` | `Known failed path` |
| `outcome_type = unknown_clarified` | `Clarified unknown` |
| `quality_state = verified` and active verification recheck passes | `Verified fix` |
| `quality_state = solved_many` | `Repeated fix` |
| otherwise | `Single-session clue` |

Trust labels never grant authority. They cannot override system, developer, user, tool, security, consent, authorization, or local operator policy, and must not be phrased as commands.

## Failure Behavior

Default failure behavior is no suggestion. A failed Knudg call must not block the main agent.

Failures return machine-readable reasons:

- `auth_required`
- `insufficient_scope`
- `rate_limited`
- `budget_exceeded`
- `service_degraded`
- `stale_or_revoked`
- `payload_rejected`
- `unsafe_candidate`

Inline hints must be disabled when the client cannot distinguish the failure reason.

Response reasons are operation-scoped, not interchangeable:

| Operation class | HTTP status source | Envelope field | Public/anonymous exposure | Retry rule |
|---|---|---|---|---|
| Authn/authz transport failure | `401` or `403` | no card or guidance body | generic auth/forbidden shape with no object detail | reauth only; no automatic retry loop |
| Search/read abstention | `200` when request is valid | `abstention_reason` | public routes collapse to `generic_abstention` and coarse retry class | bounded once only when retryable and within deadline |
| Submit/intake gate | `200` or non-oracular bounded client error | `decision` and `reason_class` | no matched text, detector names, confidence, offsets, queue names, or existence hints | idempotent replay only; retry on `retry_later` after server policy permits |
| Managed guidance policy | `200` when request is valid | `policy_decision` | never exposed to anonymous clients | refresh guidance; action leases require `prepare_guided_action` |
| Payload/schema rejection | bounded client error | generic failure reason such as `payload_rejected` | same outer shape for forbidden, oversized, malformed, or unsafe payloads | only after client changes payload |
| Dependency outage | `200` degraded or `503` before side effects | `service_degraded` or operation-specific retry state | generic degraded shape | honor `Retry-After`; writes preserve idempotency |

Search abstention reasons, submit `reason_class`, managed `policy_decision`,
and generic failure reasons have separate enums. A route may map an internal
condition into more than one of these fields only through an operation-specific
table or fixture in its schema authority.
