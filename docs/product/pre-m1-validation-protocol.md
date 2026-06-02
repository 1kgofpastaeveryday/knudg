# Pre-M1 Validation Protocol

This is the blocking validation artifact for WEDGE-001. The information-only
landing page is not an intake, analytics, waitlist, registration, or evidence
capture surface.

The companion workbook
[`wedge-001-validation-workbook.md`](wedge-001-validation-workbook.md)
defines the evidence register, seed-candidate record, dry-run summary, seed
corpus summary, baseline replay register, reviewer calibration evidence, and
RFC 0003 acceptance memo shape. The workbook is an operating template, not an
evidence store.

## Ownership

- Owner: Knudg operator
- Reviewers: product, security/privacy, and reviewer-operations owner before
  WEDGE-001 acceptance
- Status values: `draft`, `ready_for_research`, `accepted`, `rejected`,
  `superseded`

## Prospect Registry

Prospect and participant records live in a private registry outside repository
documentation unless the repository is explicitly approved for that data class.
RFC 0003 may reference only opaque IDs.

Registry fields:

- opaque participant or team ID
- segment and ICP fit
- recruiting source
- consent/authorization status
- contact owner
- allowed research activities
- evidence links
- retention and deletion date
- opt-out or deletion request path

The registry must not store raw logs, secrets, customer incidents, repository
URLs, or private diagnostic artifacts unless a separate approved data policy
allows them.

## Research Protocol

The accepted protocol must define:

- research questions and kill criteria
- participant criteria and minimum signed participants
- recruiting channels and outreach copy
- consent script and privacy pre-brief
- interview/usability artifacts
- evidence repository and allowed data classes
- source-rights review for seed artifacts
- decision thresholds for accepting, narrowing, pivoting, or killing WEDGE-001
- update path back into RFC 0003

## Seed Rights Matrix

Every seed artifact records:

- source class
- submitter authority
- license or terms review
- attribution obligations
- third-party contribution handling
- commercial-use compatibility
- takedown/revocation effect
- fallback visibility: synthetic, single-workspace private, team-only, or public

Public visibility alone is not consent or reuse authority.
