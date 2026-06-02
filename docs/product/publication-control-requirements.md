# Publication Control Requirements

Status: Internal safety requirements, synchronized May 12, 2026

Document authority:

- classification: internal product/safety design, not public landing-page copy
- owns: launch-blocking consent, approval, scope, withdrawal, and deprecation
  requirements for future team or public publication flows
- does not own: landing-page copy, deployment steps, rollback procedure, or
  static-site smoke checks

These controls are product launch blockers for any future public or team
publication flow. Landing pages may summarize them at a high level, but must
not expose this checklist as public copy.

## Launch-Blocking Requirements

- block raw Knudg logs, transcripts, stack traces, command output, and file
  excerpts from leaving the local environment before explicit user approval
- allow pre-approval live nudge/search only through sanitized query profiles or
  equivalent bounded metadata that excludes raw logs, secrets, private paths,
  source excerpts, customer identifiers, and full stack traces
- preview the exact redacted artifact before approval
- record the approver and approval authority
- make publication scope explicit before sharing
- separate approval for private retention, team sharing, public publication,
  raw artifact retention, and commercial or derived use
- ensure withdrawal removes or disables the shared artifact from future reuse
- give deprecated or unsafe clues a visible stop-reuse path
- keep audit evidence for approval, scope changes, withdrawal, and deprecation
  before team or public publication opens

## Public-Copy Boundary

Public pages may say:

- raw Knudg logs do not leave the local environment before explicit approval
- shared experience is not automatic
- human review and scoped sharing are launch requirements
- withdrawal and stale-clue stop paths are required before publication opens

Public pages must not expose:

- approval queue internals
- artifact identifiers
- policy tables
- audit storage details
- operational workflow detail that helps reconstruct publication mechanics
