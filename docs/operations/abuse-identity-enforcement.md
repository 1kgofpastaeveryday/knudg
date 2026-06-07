# Abuse Identity Enforcement Preflight

Status: blocked preflight scaffold

This gate covers goal item 11: real user identification and BAN operations for
abuse prevention. The current contract is intentionally preflight-only. It does
not identify real users, create abuse subject rows, materialize protected
fingerprints, enforce bans, write audit events, or expose identity status to
public, B2B, respondent, retrieval, export, ranking, raw escrow, or dashboard
surfaces.

Artifacts:

- schema: `schemas/abuse-identity-enforcement-request-v0.schema.json`
- fixture: `fixtures/abuse-identity-enforcement.blocked.json`
- validator: `scripts/validate_abuse_identity_enforcement.py`
- tests: `tests/test_abuse_identity_enforcement.py`

Validate:

```powershell
npm run abuse:identity-enforcement
npm run py -- -m pytest tests/test_abuse_identity_enforcement.py
```

The fixture must keep:

- `request_class = preflight_only`
- `surface = abuse_identity_ban_operations`
- `status = blocked`
- `identity_resolution.mode = not_performed`
- `raw_identity_values = forbidden_in_fixture`
- `protected_fingerprint_created = false`
- `subject_rows = none`
- `real_subject_rows_created = false`
- `match_status_disclosure = none`
- `normalized_outward_response = generic_no_match_disclosure`
- `identity_processing_enabled = false`
- `real_enforcement_enabled = false`
- `real_ban_operations_enabled = false`
- every enforcement transition `real_effect_enabled = false`
- `audit_event_write_enabled = false`
- appeal and reinstatement paths required but not accepted
- all public, B2B, respondent, retrieval, export, ranking, raw escrow, and
  dashboard flags disabled

Required gates:

- `ED-006`
- `TNS-001`
- `PROTECTED_FINGERPRINT_PROFILE`
- `APPEAL_RECOVERY_PATH`

Symbolic transition-to-audit mappings must stay aligned with
`trust-and-safety-audit-v0`:

- `warn -> account_warned`
- `rate_limit -> account_rate_limited`
- `hold_for_review -> submission_held`
- `suspend -> account_suspended`
- `ban -> account_banned`
- `appeal -> appeal_opened`
- `reinstate -> reinstated`
- `revoke -> artifact_revoked`
- `purge -> artifact_purged`

Validator schema errors return only paths and validator names. Gate failures do
not echo raw values, match status, protected fingerprints, subject references,
or identity material.
