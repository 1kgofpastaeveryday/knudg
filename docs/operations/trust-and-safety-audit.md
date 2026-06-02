# Trust And Safety Audit Gate

Status: draft scaffold

This gate covers `TNS-001`, the trust-and-safety audit schema required before
real broader-domain abuse identity processing, public/company/place/service
submission surfaces, respondent inquiry, or B2B dashboards.

The current scaffold is intentionally symbolic. It does not store real
identity data, create abuse subjects, process user submissions, or enable BAN
operations.

Artifacts:

- schema: `schemas/trust-and-safety-audit-v0.schema.json`
- fixture: `fixtures/trust-and-safety-audit.draft.json`
- validator: `scripts/validate_trust_and_safety_audit.py`
- tests: `tests/test_trust_and_safety_audit.py`

Validate:

```powershell
npm run tns:audit
python -m pytest tests/test_trust_and_safety_audit.py
```

The fixture must keep:

- `real_identity_processing_enabled = false`
- real BAN operations, respondent inquiry, B2B dashboards, raw detail escrow,
  public candidate conversion/publication, B2B respondent portal, and
  company/store dashboard disabled
- all current experience domains listed in `covered_domains`
- `synthetic_audit_event_contract` uses opaque fixture identifiers,
  `sha256:*` decision digests, and fixture timestamps only
- `identity_controls.raw_identity_values = forbidden_in_fixture`
- `identity_controls.subject_rows = none`
- respondent, B2B, public, retrieval, export, and ranking surfaces listed as
  forbidden identity-disclosure surfaces
- blockers for PR-006, role model, protected fingerprint profile,
  appeal/recovery path, and no-disclosure negative tests
- validator schema errors sanitized to path and validator names only
- validator gate failures reject raw audit-event markers such as emails,
  localhost/IP-like development identifiers, URLs, and local paths

This gate is a prerequisite for implementing the real abuse identity lane, not
an implementation of that lane.

`abuse-identity-enforcement-request-v0` uses this audit vocabulary only as a
symbolic preflight mapping for item 11. The mapping names required audit event
types for warn, rate-limit, hold, suspend, ban, appeal, reinstate, revoke, and
purge flows, but `audit_event_write_enabled` remains false until TNS-001,
protected fingerprinting, role model, and appeal/recovery gates are accepted.
