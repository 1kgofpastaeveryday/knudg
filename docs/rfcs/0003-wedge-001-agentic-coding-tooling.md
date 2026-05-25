# RFC 0003 - WEDGE-001 Agentic Coding Tooling Failures

Status: draft gate

M1 product ingestion remains blocked while this RFC status is not `accepted`.
Acceptance requires every Pre-M1 checklist item below to contain named owners,
evidence, measured pass/fail values, and decision links. Estimates may appear
only as planning inputs in draft revisions; an estimated value cannot open a
launch gate or enable M1 product ingestion.

This RFC is the required WEDGE-001 artifact before M1 product ingestion or
non-synthetic private writer queue work starts. Local synthetic/model-only
scaffolding may proceed under the backlog gates, but it must not store
non-synthetic candidate bodies or imply product ingestion is enabled. This RFC
selects the first wedge, but it does not approve public search, public
publication, billing, or generalized ingestion.

The validation evidence shape is defined by
`docs/product/wedge-001-validation-workbook.md`. RFC 0003 may reference only
the allowed opaque IDs, digests, source classes, consent states, owners, and
private evidence links from that workbook.

## Selected Wedge

WEDGE-001 covers developer tooling failures encountered by agentic coding
environments:

- package manager failures
- framework migration failures
- CI/test/build failures involving public dependencies
- mobile build and TestFlight pipeline failures

Private repository identifiers, customer incidents, credentials, destructive
migrations, billing changes, and security-posture changes are private/team-only
unless a later RFC accepts their public profile.

## Pre-M1 Acceptance Checklist

M1 product ingestion cannot start until this RFC is accepted with measured
values for:

- private prospect registry entries for the first target users or teams,
  referenced by opaque IDs, segment, owner, consent/authorization state, and
  evidence links rather than real names in this RFC
- acquisition channels and design-partner consent terms
- pre-M1 validation protocol: owner, research questions, participant criteria,
  recruiting source, consent script, interview/usability artifacts, evidence
  repository, decision thresholds, update path back into this RFC, and
  conformance to `docs/product/pre-m1-validation-protocol.md`
- manual seed-corpus protocol
- baseline systems for evaluation
- sample sizes and evaluation bands
- expected useful-card yield
- high-risk fraction
- useful visible summary rate after safety withholding
- maximum cost per useful approved card
- maximum review and reproduction minutes per accepted card by risk band
- reviewer staffing source, qualification rubric, compensation or staffing
  model, calibration fixtures, false-approval threshold, and pause rules
- public-vs-private pivot thresholds
- commercial validation: buyer, user, weekly usage hypothesis, current
  alternative workflow, willingness-to-pay range, and procurement blocker

## Seed Dry Run

Pre-M1 evidence storage contract:

- dry-run and prospect artifacts live outside Knudg product tables until the M1
  protected-data durability gate passes
- allowed stores are the private prospect registry and a private research
  evidence repository named by the accepted validation protocol
- the RFC may reference only opaque participant IDs, artifact digests, source
  class, consent status, owner, and evidence links
- non-synthetic dry-run artifacts require the same
  `private_candidate_collection` consent/acknowledgement, opt-out path, TTL,
  and discard/purge path as M1 private candidates
- dry-run artifacts are either purged after the decision, kept only under the
  private research retention policy, or regenerated through the accepted
  PR-006 intake/redaction/consent/review path after M1; promotion into product
  tables by copying rows is forbidden

Before accepting the seed protocol, run a manual dry run with 30 to 50
candidate artifacts. This dry run is not sufficient to start M1 ingestion; it
validates the protocol, risk taxonomy, consent artifact, and review workflow.
For each candidate, record:

- source channel and consent artifact
- source-rights classification, license/ToS review, attribution obligations,
  third-party contribution handling, commercial-use compatibility, takedown
  path, and fallback visibility if rights are unclear
- redaction outcome and abandonment
- outcome type
- exact error signature
- tool/framework/package coordinates
- environment bounds
- high-risk flags
- reviewer confidence
- reproduction requirement and elapsed minutes
- useful-summary eligibility
- rejection reason if rejected

If useful visible summary rate is below the threshold accepted by this RFC, the
product must pivot to private/team-only retrieval before building public
publication machinery.

Before M1 ingestion is enabled, the accepted protocol must then produce at
least 100 labeled seed candidates, as required by Product Strategy. Those 100
candidates are the bootstrap inventory for the first evaluation; the 30 to 50
dry-run artifacts may count only if they used the accepted protocol and consent
artifact unchanged.

## Public/Private Pivot

The RFC must define numeric thresholds for:

- public useful retrieval lift versus baseline
- private/team useful retrieval lift versus baseline
- public approval rate
- cost per useful public card
- high-risk verification burden
- consent approval time and abandonment

If private/team retrieval clears its value threshold while public retrieval
fails privacy, approval, high-risk, or cost thresholds, WEDGE-001 continues as a
team-private product slice and public corpus expansion remains paused.

## Baselines

The evaluation must compare against:

- current agent web search
- official docs
- package/framework issue trackers
- Stack Overflow or equivalent public Q&A
- repo-local search
- team-local history search when available

The baseline set must be frozen before replay tasks run.

## Launch Slices

Internal dogfood may use synthetic fixtures or protected manual research
artifacts only under the pre-M1 evidence storage contract above. Employee
approval alone is insufficient for product-path storage. Private team alpha may
use consenting design-partner sessions only after the relevant
non-synthetic-body, consent, authorization, and retrieval gates pass. Public
pilot is blocked until public-search privacy attack modeling, abuse budgets,
reviewer QA, high-risk verification, useful visible summary rate, and
consent/revocation E2E tests pass.
