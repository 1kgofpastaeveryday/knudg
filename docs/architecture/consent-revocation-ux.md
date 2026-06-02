# Consent and Revocation UX

Knudg can postpone a polished knowledge-base UI, but it cannot postpone consent and revocation UX. Publication is a human decision surface and a launch blocker for public or team sharing.

Terminology:

- `public publication`: exact redacted artifact enters the public publication
  lifecycle and can become public-search eligible only after consent, review,
  safety, and publication gates pass.
- `team namespace sharing`: private/team retrieval using `private_retention`
  consent plus a separate `team_namespace_grant` consent/grant record. Private
  retention is necessary but not sufficient for team sharing. It is not public
  publication and does not use `approved_for_publication`.
- `future team-publication`: reserved for a later RFC; it cannot be inferred
  from current team namespace sharing.

## Consent Surface Matrix

| Surface | Default | User-visible artifact | Inherits public-card consent | Separate consent required | Revocation effect | Monetization allowed |
|---|---|---|---|---|---|---|
| Redacted public card | off | exact redacted card version | no | yes | block retrieval immediately, purge projections | no direct sale by default |
| Private candidate | off until acknowledged | draft card, source classes, redaction state, retention period | no | `private_candidate_collection` consent/acknowledgement before first collection | discard candidate, remove private retrieval projections immediately, then revoke or purge after undo window | no |
| Private card retention | off beyond MVP TTL | private card version, readers, purpose, TTL | no | yes for retention beyond default TTL or outside the originating workspace | block private retrieval, delete or crypto-shred by TTL | no |
| Team namespace sharing | off | exact private/team card version, reader group, namespace, purpose, TTL | no | yes through `private_retention` plus separate `team_namespace_grant` consent/grant | block team retrieval and remove team projections | no by default |
| Canonical trail | off | deterministic cluster summary and source list | yes, only for deterministic aggregation of already-public cards | yes if edited or meaning changes | remove source, recompute or unpublish if invalid | no by default |
| Aggregate stats | off | metric definition, no raw/card text | yes only for internal operational aggregate processing after the public-search privacy test profile passes | yes for externally shared, customer-facing, benchmark, monetized, rare, or identifying cohorts | stop new use immediately; recompute within the private surface SLA | allowed only after separate consent and policy review |
| Verified rewrite | off | rewritten artifact and verifier notes | no | yes | unpublish rewrite if required source is revoked | no by default |
| Curated pack | off | pack preview, included artifacts, commercial terms | no | yes | remove source or unpublish pack if source is required | yes only with explicit commercial consent |
| Model/eval use | off | purpose, retention, dataset type | no | yes | stop new use immediately; add to deny manifest within the private revocation SLA; remove from unsealed future datasets before any next run | no by default |
| Raw/source retention | off | raw artifact class, readers, purpose, TTL | no | yes | block reads immediately, delete or crypto-shred by TTL | no |

If a surface is not listed here, consent is denied by default.

Default TTLs:

- private candidate metadata and redacted draft bodies: 14 days
- approval handoff artifacts and expired challenges: private deployment TTL
- private retained cards under the originating workspace default: private
  deployment TTL; no indefinite retention
- raw/source artifacts: explicit user-selected TTL with a private-deployment
  maximum; no indefinite retention

M1 private candidate collection requires the
`non_synthetic_body_persistence_gate` before any agent-work artifact is stored.
The `private_candidate_collection` consent/acknowledgement artifact must state the purpose, fields
collected, default TTL, readers, opt-out path, discard/purge path, and whether
data can leave the local workspace. CLI, MCP, and hook clients must show or
link this notice and record acknowledgement before first collection; broad
workspace terms alone are insufficient.

Longer private retention requires explicit consent on the exact retained
artifact, and purge must cover Postgres rows, caches, local approval artifacts,
and backup/PITR handling according to the retention policy.

Backup and restore policy:

- backups and WAL archives are encrypted and retained for the shortest period
  allowed by the deployment RPO/RTO policy
- purged or revoked data is excluded from retrieval immediately even if it
  remains inside immutable backups until backup expiry
- restored clusters start quarantined, replay revocation tombstones and consent
  expiry before serving traffic, and must pass revocation probes before cutover
- crypto-shredded artifacts must not be recoverable from object storage or
  restored clusters after key destruction

`Default off` means the product surface is not launched or enabled by default. If that surface is later launched, the same row still governs whether consent can be inherited or must be renewed.

Team namespace sharing is not public publication in M0. It requires
`private_retention` consent for the retained card and a separate
`team_namespace_grant` consent/grant bound to the exact card version, reader
group, namespace, purpose, and TTL. It does not use `public_publication`, does
not create `approved_for_publication`, and does not make a card public-search
eligible. A future RFC may add a separate team-publication scope only if it
defines its lifecycle, consent challenge, withdrawal, revocation, and tests.

Plain-language hierarchy:

- Private candidate: Knudg may hold a draft briefly so the user can review it.
- Private retained card: Knudg keeps the card for private/team retrieval only under the chosen TTL and reader list.
- Intake review escrow: Knudg may place the exact raw submitted artifact in a short-TTL, encrypted, single-use human safety review escrow only after separate `intake_review_escrow` consent.
- Public card: Knudg may show the exact approved redacted card to authorized public search paths.
- Derived/commercial/model use: Knudg needs separate permission for each listed use.

Aggregate-stat inheritance requires a named privacy test profile, not only a
`k` threshold. The profile must include cohort floors, differencing probes,
auxiliary-information probes, timing envelopes, distributed query budgets,
kill criteria, and evidence that the metric cannot single out a tenant, user,
repo, host, customer, or incident.

Public publication and public-search eligibility require a comprehension gate before the approval event can be completed. Team namespace sharing requires the private-retention consent and namespace-grant checks described above, not the public publication lifecycle. The trusted consent surface must require the user to acknowledge, in plain language, the exact artifact, visibility, revocation limits for already-delivered copies, paid retrieval disclosure if applicable, and each separate derived-use permission. Failing or skipping the public-publication gate leaves the card private or rejected; it must not enter public search.

The comprehension gate is testable, not decorative. Before M2 launch it must
require correct answers for at least artifact visibility, revocation limits,
paid retrieval scope, derived commercial/model-use separation, and raw/source
retention separation. Passing requires all safety-critical answers correct; a
failed attempt writes no consent event and returns to the review surface. Audit
events record challenge ID, locale, pass/fail, and non-sensitive error
category. Durable consent audit records must not store assistive-technology
mode. If accessibility QA needs client capability telemetry, that telemetry
requires a separate privacy-reviewed contract, short retention, no identifiers,
and exclusion from product analytics, reviewer scoring, commercial use, and
publication decisions.

Public-card paid retrieval is a disclosure and billing-scope requirement for the retrieval event. It does not grant commercial reuse, resale, curated-pack inclusion, sponsorship, model/eval use, or other derived commercial rights. Those uses require separate explicit commercial consent on the exact artifact and terms shown to the user.

Milestone sequencing:

- M1 may support private candidates, default-TTL private retention, local approval queues, and revocation controls only after the `non_synthetic_body_persistence_gate` passes.
- M2 public publication and team namespace sharing are blocked until the human consent/revocation UI, signed approval challenges, withdrawal-before-publish where publication applies, namespace-grant checks where team sharing applies, and accessibility acceptance criteria are implemented.
- Long-term private retention beyond the M1 default TTL requires the same explicit consent mechanics as public-card approval.

## Approval Flow

The approval surface must offer separate actions:

- `Consent to reviewer publication of this exact redacted card`
- `Request more redaction`
- `Keep private`
- `Discard candidate`
- `Set derived use permissions`
- `Opt in to raw/source retention`

Agent-generated private draft review should prefer a static generated HTML
viewer over a long-running local review server. The generator may render a
single draft or batch from local JSON into a self-contained HTML file with
stable `draft_id` anchors. Static HTML is a review surface, not the state
authority; decisions that need local file movement or deletion are recorded as
decision artifacts for Codex/knudgctl to apply, or are handed off to a trusted
hosted endpoint. Avoid background local BFF processes unless the task
explicitly needs interactive local state.

The first screen should be summary-first, not JSON-first. Show concise fields
such as `内容` and `除いた内容`; reserve the exact structured JSON for an
explicit details or advanced section. `除いた内容` names redaction classes such
as paths, hostnames, usernames, repository names, env values, and logs, but does
not reveal the removed values. Draft JSON must carry the human-facing summary
alongside the agent-oriented fields, using `human_summary.content` for `内容`
and `human_summary.redaction_summary` for `除いた内容`. Human summary fields are
stored with the candidate for knowledge viewers, but are not agent retrieval
text.

For the first-pass draft viewer, the primary buttons are:

- `Accept`: send this exact redacted draft to the configured hosted handoff or
  reviewer final-check queue. This records permission to submit the artifact for
  review; it must not imply immediate publication.
- `Discard`: open a modal with `Keep private` and `Delete`. The modal may offer
  a `make this option primary` preference that can later be changed in settings
  or by Codex.

`Keep private` means the draft is not published and remains available only for
local/private use under the selected TTL. Use plain completion copy such as:
`今回のknowledgeは公開されていません。あなたのマシン内でのみ活用されます。`
`Delete` removes the candidate after any undo window. Do not collapse these
states into a single `Reject` action.

Hosted publication handoff URLs must use a one-time token, digest reference, or
server-side candidate ID. They must not put the redacted artifact body in a URL
query string such as `?content=...`.

The trusted browser or OS-mediated approval surface must show:

- exact redacted artifact
- redaction diff or summary
- remaining identifying-risk warnings
- target namespace and visibility
- derived-use selections
- retention period
- revocation path
- digest that will be approved

CLI and MCP approval review surfaces show only digest, namespace, TTL,
non-sensitive risk summary, derived-use flags, revocation path, and handoff
status. They must not display the full exact public-publication artifact or any
future team-publication artifact, and they must not complete publication
consent.

Any edit, re-redaction, namespace change, derived-use change, or retention change invalidates the approval digest and returns the candidate to review.

User-facing copy must not imply that the user publishes the card. User approval records consent for the exact redacted artifact. A reviewer performs the separate publish action after checking that approval, review, redaction, and policy gates still match.

Users may withdraw publication approval any time before the publish event is committed. Withdrawal moves the candidate to `publication_withdrawn`, terminates the active public consent, invalidates outstanding publish work, and notifies reviewers that publication is blocked. Keeping the card as private content requires a separate private-retention approval challenge that returns the candidate to `awaiting_user_approval`; withdrawal must not silently create `approved_private`.

Approval recovery states:

| Event | Resulting state | User recovery |
|---|---|---|
| `Request more redaction` | back to `pending_redaction` | show requested changes and regenerate digest |
| `Keep private` | new private approval challenge | card can move to `approved_private` only after separate private-retention consent |
| `Discard candidate` | `discard_pending` with undo window if no publish/revoke event exists; private retrieval projections are removed immediately | restore to review queue during the undo window, otherwise finalize to `revoked`; physical purge continues as post-revoke cleanup, not a lifecycle state |
| challenge expired | remains `awaiting_user_approval` | issue a new challenge after reloading current artifact |
| failed step-up auth | remains `awaiting_user_approval` | retry auth; no consent event is written |
| replay or digest mismatch | no state change; audit event | reload current artifact and start a new challenge |
| reviewer rejects after approval | `rejected` or `pending_redaction` with reason | notify user and preserve private copy only through a separate private-retention challenge |
| network retry with same digest | no duplicate effect | show completed result |

Undo is allowed only for local candidate actions that have not produced a publish, revoke, raw-retention, commercial-use, or model/eval event. Every approval, rejection, withdrawal, publish, failed publish, and revocation state change sends a notification through the user's configured channel and appears in consent history.

## Approval Security

Publication approval uses a one-time signed approval challenge:

- challenge binds subject, tenant, namespace, card version, redacted digest, derived-use policy, raw-retention policy, origin, and expiry
- challenge TTL is short-lived and private-deployment configured; exact value is
  not public-facing material
- challenge is single-use
- publish, raw retention, commercial derived use, and model/eval use require step-up reauthentication
- CSRF protection and same-site browser protections are required for web approval
- web approval requires `Content-Security-Policy: frame-ancestors 'none'`,
  `X-Frame-Options: DENY` until all supported browsers enforce CSP, and refusal
  to complete approval inside untrusted embedded webviews
- the step-up session is rebound to the approval challenge after
  authentication; a session established before the challenge cannot silently
  approve a later or different digest
- replay returns a hard error and creates an audit event

CLI and MCP clients may list pending approvals, display the digest, namespace, TTL, derived-use flags, and revocation path, and open a trusted browser or OS-mediated approval handoff. They must not display the full exact public-publication or future team-publication approval artifact or collect the final approval phrase for publication inside an agent, terminal transcript, MCP tool result, or background worker. Private-retention review may show a terminal-safe preview only when the client sends a terminal-safe preview attestation and the server records it with the handoff. The attestation must name the client instance, transcript mode (`disabled`, `redacted`, or `unknown`), preview renderer version, and redaction policy digest. `unknown` mode cannot receive a preview and must fall back to a browser or OS-mediated handoff. Terminal previews are marked non-public, omit raw/source bodies, and cannot complete any publication consent event from that surface. The trusted approval surface must enforce step-up authentication and refuse approval when the challenge expires or the artifact no longer matches the digest.

Approval handoff is not consent. A CLI or MCP handoff can create or reopen the trusted consent surface, but the consent event is complete only after the user passes step-up authentication and the comprehension gate on that surface. Handoff retries must return the existing pending or completed handoff for the same artifact digest and idempotency key; they must not mint a new approval challenge for changed content.

## Raw Artifact Consent

Raw/source retention is never bundled with public-card approval.

Raw retention is:

- default off
- separate step
- TTL required with a private-deployment maximum; no indefinite retention
- reader role list required
- purpose required
- revocable independently
- visible in consent history

The CTA must describe the consequence, for example: `Store raw source for 7 days for reviewer redaction`, not `Continue`.

## Revocation Flow

Users need a clear revocation cockpit:

- `My published cards`
- `Pending publication approvals`
- `Consent history`
- `Derived uses`
- `Raw/source retention`
- `Revoke`

`Pending publication approvals` is a first-class cockpit section, not only a
notification. It lists every active `approved_for_publication` consent that has
not yet produced a reviewer publish event, with card version, digest,
namespace, challenge/approval time, reviewer status, notification delivery
state, and expiry or deadline if present. The primary action is `Withdraw
publication approval`. Withdrawing opens the same trusted human-session
challenge pattern as revocation, writes `approval_withdrawn`, invalidates
pending reviewer publish, and records whether the user also requested a
separate private-retention challenge. CLI and MCP clients may list these rows
and create the withdrawal handoff, but cannot collect the final withdrawal
phrase.

Every consent-bearing row has a first-class `revoke_subject` path. Supported
subjects include private candidate collection acknowledgement,
private-retention consent, public card, card version, raw/source artifact
retention, verified rewrite, canonical trail, aggregate-stat use,
curated-pack inclusion, derived/commercial-use consent, and model/eval use. The
cockpit maps each row to a trusted human-session revocation challenge; CLI and
MCP clients may create a handoff but cannot collect the final revocation phrase
or complete revocation inside an agent, terminal transcript, MCP tool result,
or background worker.

The data model is the canonical authority for `consent_records.scope` values:
`private_candidate_collection`, `private_retention`, `team_namespace_grant`,
`public_publication`, `intake_review_escrow`, `raw_source_retention`,
`derived_artifact`, `commercial_use`, and `model_eval_use`. UX surface names
such as canonical trail, aggregate stats, verified rewrite, curated pack,
commercial derived use, and model/eval use are stored as `surface_type` or
policy metadata under the canonical scope, not as alternate scope enum values.
Revocation of any listed surface writes a consent termination event even when
no card tombstone is needed. Unknown or legacy scope aliases fail closed and
cannot authorize publication, retrieval, derived use, or restore cutover.

Consent-record revocation is explicit. A user can revoke an individual
`consent_record` by its tenant-scoped ID when the desired effect is terminating
that consent grant without revoking the underlying card, card version, or
artifact. The termination event stores the consent record ID, scope, artifact
type, artifact ID, digest, and cleanup policy. If the same user action must also
block future retrieval of a card or artifact, the transaction writes both the
consent termination and the matching tombstone; otherwise the consent
termination alone is sufficient.

The cockpit must make that choice explicit before confirmation:

- `Stop this permission only`: terminate the selected consent record and show
  which future use stops.
- `Block this card or version from retrieval`: terminate relevant consent and
  create the card/card-version tombstone.
- `Remove dependent derived uses`: terminate the derived-use consent and show
  which canonical trails, rewrites, packs, model/eval sets, or aggregate stats
  enter cleanup.

Each choice shows a consequence preview, already-delivered-copy limitation,
expected cleanup states, and whether other private/team copies remain readable.

Before revocation, show:

- public card version
- derived artifacts that depend on it
- raw/source artifacts tied to it
- audit/legal records that cannot be physically deleted
- expected propagation states

After revocation, show:

- `retrieval blocked`
- `hot index purge pending/done`
- `main index purge pending/done`
- `derived artifact update pending/done`
- `local cache invalidation pending/done`
- `raw/source purge pending/done`

The user-facing rule is: retrieval blocks first, cleanup follows. If cleanup fails, the UI shows the failed projection and retry/escalation path.

Already-delivered cards cannot be physically pulled back from external logs, screenshots, model context windows, or third-party caches. Revocation must stop future Knudg retrieval, invalidate Knudg-controlled caches, purge indexes, and show this limitation before the user confirms revocation.

## Revocation Security

Revocation uses a one-time signed revocation challenge parallel to approval:

- challenge binds subject type, subject ID, tenant, namespace when applicable,
  artifact or consent digest, cleanup policy, origin, and expiry
- challenge TTL is short-lived and private-deployment configured; exact value is
  not public-facing material
- challenge is single-use and records `used_at`, actor, and resulting
  tombstone or consent-termination event
- public publication, future team-publication, raw/source, commercial-derived,
  model/eval, and broad namespace revocations require step-up reauthentication
- web revocation uses the same CSRF, same-site, frame-blocking, and
  post-step-up session rebinding rules as approval
- terminal and MCP surfaces may show digest, subject class, expected effects,
  and handoff status, but not raw/source bodies or full public-publication or
  future team-publication artifacts
- replay, changed digest, expired challenge, stale cleanup policy, or subject
  mismatch returns a hard error and creates an audit event

Revocation notifications use in-app consent history as the source of truth.
Optional email, webhook, or OS notifications record delivery status, retry
count, and non-sensitive failure reason. Failed external notification never
rolls back revocation; the in-app history and cleanup status remain visible.

External recipient contract for public or paid retrieval:

- full-card public or paid retrieval is not designed for MVP and has no active
  launch route until a separate external-recipient certification and enforcement
  spec is accepted
- full-card public or paid retrieval is disabled until a full-card expansion
  launch gate passes client conformance tests, signed retention-class
  contracts, short-lived body leases, and audit review
- the certification spec must define certification authority, required
  conformance tests, cache/log retention controls, revocation-feed SLA, audit
  sampling, breach handling, lease revocation, de-certification, re-certification,
  downgrade path, and user-facing copy distinguishing Knudg-controlled retrieval
  from recipient-controlled copies
- public API/MCP responses carry cache-control and retention-class metadata
- certified clients must not log full card bodies by default and must honor
  revocation feeds or webhooks before serving cached content
- full-card body leases are short-lived and must be revalidated against
  revocation epoch before reuse
- full-card expansion emits an audit event with client identity and card version
- non-conforming clients may receive public search only without full-card body
  content; they receive summaries or metadata-only results
- consent copy must state that revocation blocks future Knudg retrieval but
  cannot remove copies already delivered to external clients

Withdrawal and revocation SLAs:

- future retrieval and new processing: immediate hard deny after the transaction commits
- search/index/cache propagation: private operations SLO for public publication
  retrieval surfaces and team namespace-sharing retrieval surfaces, with
  `no_suggestion` fail-closed until confirmed
- model/eval deny manifest: private revocation SLA
- aggregate recompute: private surface-specific SLA
- curated or commercial artifacts: unpublish or remove the required source within the private revocation SLA unless a documented legal-retention basis applies
- audit/legal records: retained only under the documented basis and excluded from retrieval, model/eval, aggregate, and commercial use

## Accessibility Baseline

Consent, revocation, warning, and retrieval-panel surfaces must meet WCAG 2.2 AA.

M2 also requires consent comprehension testing before public publication, and
separate private-retention/namespace-grant comprehension for team namespace
sharing. Tests must cover public approval, team sharing, raw retention,
derived-use permission, withdrawal-before-publish, model/eval use, commercial
use, and revocation limits for already-delivered copies. Launch is blocked if
users cannot reliably distinguish these outcomes.

Consent usability validation must define target participants, tasks,
comprehension questions, accessibility coverage, maximum failure/abandonment
thresholds, recovery copy, and the fallback rule for users who cannot complete
publication consent. Revocation and withdrawal remain available even when
publication consent is paused or the comprehension surface degrades.

Required behavior:

- keyboard access for every action
- deterministic focus order
- visible focus state
- screen-reader labels for state and risk
- ARIA live/status regions for async publish/revoke states
- target size suitable for touch
- no color-only risk signaling
- reduced-motion safe status updates
- clear error recovery text

Acceptance criteria:

- automated axe or equivalent checks pass for consent and revocation screens
- keyboard-only approval, withdrawal, and revocation flows complete without focus traps
- screen-reader smoke tests announce digest, risk, pending, success, and failure states
- CLI output has plain-text equivalents for every warning and state
- reduced-motion mode removes nonessential animation from progress updates
- actionable controls meet WCAG 2.2 AA target-size expectations or have an
  adjacent equivalent control; destructive and publishing actions are not
  adjacent without separation, focus confirmation, or undo-safe recovery

## User-Visible Retrieval States

`no_suggestion` is not silent, but public responses must not reveal why a result was absent. Public clients get one generic abstention label and a retry-after class when applicable. They must not distinguish no authorized match, low confidence, withheld safety result, rare private fingerprint, redacted result, not indexed, or no match.

Private/team clients may show coarse diagnostic states only after authorization and only inside the tenant boundary:

- no eligible match
- low confidence
- safety gate blocked result
- service degraded
- rate limited
- private identifiers required, no public query sent

Diagnostic states are for operator/user recovery, not public search semantics. They must not include counts, nearest matches, rarity explanations, suppressed terms, package names, repository URLs, path fragments, token shapes, or credential-bearing detail.

Safe recovery for `no_suggestion` is limited to generic actions: retry later, broaden the query, sign in, check client status, or contact the workspace admin. Clients must not suggest adding private identifiers, weakening redaction, or revealing hidden result reasons to improve recall.

Retrieval-panel suggestions must allow:

- dismiss
- snooze
- report harmful
- show provenance
- show why this was suggested
- disable inline hints for this workspace

`Show why this was suggested` uses audience-specific explanation schemas:

| Audience | Allowed explanation fields | Forbidden fields |
|---|---|---|
| Public/anonymous | coarse match class, public tool/framework/package family when already present in the returned card, trust label, freshness label, and generic safety withholding label | ranking signal names, weights, candidate counts, source event ranges, tenant/user/repo/host/path fragments, rarity explanations, suppressed terms, private diagnostic reasons, raw thresholds, revocation epochs, index generations |
| Authenticated private/team | authorized namespace, coarse matched facets, trust label, freshness status, consent state, safety gate category, and recovery action | cross-tenant counts, unauthorized namespace hints, raw secrets, full source logs, suppressed private identifiers, or evidence from objects the caller cannot read |
| Reviewer/admin | queue/review context, policy version, redaction/safety flags, and audit correlation IDs within assigned scope | data outside assigned tenant/case scope or fields blocked by revocation/retention policy |

Explanation tests must assert that public explanations stay invariant for rare
private fingerprints, redacted matches, withheld safety results, no authorized
matches, and empty indexes. Private/team explanation tests must prove every
field is authorized before ranking or reranking uses it.

Core local state controls must exist for CLI/MCP/hook clients:

- `status`: show enabled integrations, local cache epoch, and pending approvals
- `approval-handoff status`: read digest-bound handoff metadata, freshness,
  revocation visibility, and blocker booleans only. It is not consent,
  approval, withdrawal, revocation, publication, lifecycle authority, or a
  trusted completion surface.
- `list`: list pending approvals, cached metadata pointers, and revocation cleanup tasks
- `purge`: delete local query profiles, bodyless cache metadata, and expired approval challenges; audit metadata needed for security may remain server-side
- `disable`: stop hooks/inline hints and clear local delivery queues
- `export audit`: show local actions and revocation cleanup state without exporting card bodies

Revocation invalidates local metadata immediately. If the client cannot confirm
the server revocation epoch, it must reject cached metadata and return
`no_suggestion`.

## Retry and Idempotency Policy

All retries are bounded by the original operation deadline and use jittered backoff only for explicit transient failures. Clients must not retry after a terminal consent, auth, revocation, safety, digest-mismatch, or comprehension-gate failure.

Per-operation policy:

- search: idempotent by query profile and request ID; retry at most once inside the search deadline; stale auth, stale revocation epoch, rate limits, or safety uncertainty return `no_suggestion`.
- read: idempotent by card ID, version, scope, and revocation epoch; retries may return cached metadata only when the epoch is current; card bodies fail closed when freshness cannot be proven.
- write: every candidate, retention, derived-use, raw-retention, publish, or state-changing request requires an idempotency key and request digest; same key and digest returns the original result, while same key with a different digest is a hard error.
- revoke: retrieval-affecting tombstone creation is idempotent and highest
  priority; repeated requests return the existing tombstone and cleanup state.
  Consent-only termination is idempotent by consent record and does not create a
  tombstone unless the same action also blocks a retrieval subject. Cleanup
  retries never reopen retrieval.
- approval handoff: handoff creation is idempotent by artifact digest, subject, namespace, policy set, and idempotency key; retries may reopen the trusted surface but cannot complete consent outside that surface.
