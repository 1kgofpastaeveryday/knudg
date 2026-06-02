# Experience Domains Backlog

Status: design reflected, gated scaffolding in progress

Authority:

- `docs/architecture/experience-domains.md` for domain taxonomy, redaction
  policy, retrieval boundaries, and public-candidate gates.
- `docs/architecture/data-model.md` for logical card payload fields.
- `docs/product/strategy.md` for wedge ordering and non-approval of broad
  implementation before technical closed-launch value is proven.
- `backlog/production-readiness.md` for product-path, public, consent, and
  safety blockers.

The goal is to make Knudg capable of storing and retrieving structured
experience beyond technical work while preserving domain separation. This is
not permission to ingest raw chat, job-search artifacts, restaurant reviews,
email, calendar data, receipts, or interviews.

## ED-001: Domain Policy Registry

Status: proposed

Implement a small registry for domain policy metadata:

- domain key
- allowed intents
- default visibility
- default retrieval policy
- public eligibility
- redaction class
- default TTL class
- cross-domain search rule

Initial keys:

- `technical_work`
- `personal_reasoning`
- `career_private`
- `place_service_experience`
- `public_experience_candidate`
- `public_aggregate_signal`

Acceptance:

- schema or code fixture rejects unknown domains
- technical retrieval defaults to `technical_work`
- career/place/personal domains are not searched during technical tasks
- public search can read only published public artifacts or
  `public_aggregate_signal`

## ED-002: Candidate Payload Facets

Status: proposed

Extend the candidate/card payload contract with logical facets from
`docs/architecture/experience-domains.md`:

- `domain`
- `experience_intent`
- `subject`
- `claim_type`
- `evidence_strength`
- `sensitivity`
- `retrieval_policy`
- `source_policy`

Acceptance:

- current closed-launch technical path remains compatible
- broader-domain payloads are rejected until a domain policy explicitly allows
  them
- company and place names can be stored as subject names when allowed
- person-level details, selection status, exact dates, messages, account IDs,
  and receipt IDs are rejected or redacted according to domain policy

## ED-003: Private Reasoning And Career Draft Surface

Status: proposed

Add a private-only draft/review surface for broader-domain candidates. The
surface must show human-readable content and redaction summary before retention.

Acceptance:

- no raw transcript storage
- write candidate shows exact redacted artifact before approval
- `career_private` defaults to private-only and publication-ineligible
- company names may remain visible; selection status and people are redacted
- discard supports keep-private versus delete semantics

## ED-004: Place And Service Experience Draft Surface

Status: proposed

Add private place/service candidate handling after ED-001 and ED-002.

Acceptance:

- business/product names may remain visible
- staff identity, exact timestamps, receipt/account IDs, and direct quotes are
  redacted by default
- subjective impressions are labeled as subjective
- single-observation negative impressions remain private by default

## ED-005: Public Experience Candidate Gate

Status: blocked; preflight contract scaffold present

Define the public candidate lane for company/place/service signals. This does
not open public search or publication.

Acceptance:

- private cards cannot become public by changing visibility in place
- public candidate is a newly redacted artifact with a new digest
- exact-artifact approval and reviewer publish are required
- moderation/reporting, manipulation checks, stale-signal expiry, takedown,
  and correction flows are defined
- single-observation complaints are rejected or kept private unless a reviewer
  approves a public-safe aggregate or public-source-supported artifact

Blocked by:

- PR-003 consent/revocation human UI
- PR-005 public search and publication
- PR-006 core intake safety gate
- domain-specific legal/privacy review

## ED-006: Abuse Identity Enforcement Lane

Status: blocked; preflight lane scaffold present

Add a protected anti-abuse lane for repeated malicious submissions before any
user-submitted career/place/service/public candidate surface launches.

Acceptance:

- protected identity subjects are separate from experience cards and search
  indexes
- account/contact/device/session/network/submission signals are minimized,
  keyed or encrypted, purpose-scoped, and audited
- repeat malicious submissions can trigger warn, rate-limit, hold-for-review,
  suspend, ban, appeal, reinstate, revoke, and purge flows
- ban evasion checks do not reveal which signal matched
- business/respondent surfaces never receive submitter identity, raw source
  material, device/network signals, or re-identification hints
- high-confidence bans require trust-and-safety review and appeal/recovery
  paths before affecting public or B2B-facing outputs

Blocked by:

- PR-006 core intake safety gate
- TNS-001 trust-and-safety audit schema and role model
- domain-specific moderation policy

Current scaffold:

- `schemas/abuse-identity-lane-v0.schema.json`
- `fixtures/abuse-identity-lane.draft.json`
- `scripts/validate_abuse_identity_lane.py`
- `tests/test_abuse_identity_lane_schema.py`
- `schemas/abuse-identity-enforcement-request-v0.schema.json`
- `fixtures/abuse-identity-enforcement.blocked.json`
- `scripts/validate_abuse_identity_enforcement.py`
- `tests/test_abuse_identity_enforcement.py`

## ED-007: Retrieval Evaluation By Domain

Status: proposed

Evaluate whether broader-domain retrieval improves wall-bouncing without
polluting technical work.

Acceptance:

- technical tasks do not retrieve career/place/personal cards by default
- career prompts retrieve only `career_private` and explicitly authorized
  personal reasoning cards
- place/service prompts retrieve only `place_service_experience`
- every result labels domain, claim type, evidence strength, and subjective
  status
- abstention remains valid when the authorized domain has no low-noise match

## Later Surface Backlog

These items are intentionally not implementation-ready until PR-003, PR-006,
TNS-001, and the domain-specific moderation policy pass.

| Item | Status | Required blockers before implementation |
|---|---|---|
| Actual career/company/place/service experience storage | DDL scaffold present; product writes/retrieval blocked | PR-003 consent/revocation UI, PR-006 intake safety, ED-001/ED-002 policy enforcement, TNS-001 audit schema when user submissions are involved |
| Public candidate conversion | blocked | PR-003, PR-005 public search/publication, PR-006, reviewer publish path, exact-artifact approval |
| B2B respondent portal | blocked; preflight contract scaffold present | public candidate gate, no-disclosure negative tests, respondent inquiry policy, moderation/reporting workflow |
| Real abuse identity and BAN operations | blocked; preflight contract scaffold present | ED-006 scaffold, TNS-001 accepted, protected fingerprint profile, role model, appeal/recovery path |
| Raw detail escrow | blocked; preflight contract scaffold present | PR-003 consent, PR-006 intake safety, protected-data durability, encrypted TTL review escrow, purge path, reviewer access policy, no-raw-echo tests, key profile |
| Company/store dashboard | blocked; preflight contract scaffold present | aggregate signal policy, public/B2B disclosure policy, moderation workflow, no identity leakage tests, minimum source count policy, manipulation resistance policy, no single-observation display tests, no suppression surface tests, correction/takedown policy |

Implementation may proceed on schemas, fixtures, validators, dormant DDL
scaffolds, and negative tests for these surfaces, but not on product write
paths, real data ingestion, retrieval-visible records, public serving, B2B
delivery, identity processing, raw escrow handling, or dashboard product
behavior until the blockers above are accepted.
