# Consent Revocation Gate

Status: draft scaffold, trusted completion disabled

`fixtures/consent-revocation-gate.draft.json` is the PR-003 scaffold for the
trusted human consent and revocation surfaces. It keeps trusted completion,
team sharing, public publication, and terminal publication completion disabled.

Validate it:

```powershell
npm run consent:gates
```

The scaffold tracks the five launch-blocking consent surfaces:

- `private_candidate_collection_consent`
- `private_retention_consent`
- `team_namespace_grant_consent`
- `public_publication_consent`
- `intake_review_escrow_consent`

Each surface maps to one canonical database consent scope. Scope aliases are
invalid. CLI and MCP clients may create handoffs, but cannot complete private
retention, team grants, public publication, or any worker-driven consent.

Acceptance requires trusted browser or OS-mediated completion, step-up auth,
comprehension gates, CSRF/state binding, clickjacking protection, exact origin
redirect validation, anti-enumeration failures, and serializable consent,
tombstone, and audit transaction tests.
