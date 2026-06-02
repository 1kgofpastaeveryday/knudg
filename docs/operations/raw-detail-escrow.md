# Raw Detail Escrow Preflight

Status: blocked preflight scaffold

This gate covers goal item 12: raw detail escrow for ambiguous or review-bound
experience submissions. The current contract is intentionally preflight-only.
It does not store raw detail, create escrow handles, create encrypted blobs,
handle key material, grant reviewer access, create reviewer leases, decrypt
escrow, write raw audit detail, or expose raw content to public, B2B,
respondent, retrieval, export, ranking, identity, or dashboard surfaces.

Artifacts:

- schema: `schemas/raw-detail-escrow-request-v0.schema.json`
- fixture: `fixtures/raw-detail-escrow.blocked.json`
- validator: `scripts/validate_raw_detail_escrow.py`
- tests: `tests/test_raw_detail_escrow.py`

Validate:

```powershell
npm run raw:detail-escrow
python -m pytest tests/test_raw_detail_escrow.py
```

The fixture must keep:

- `request_class = preflight_only`
- `surface = raw_detail_escrow`
- `status = blocked`
- `escrow_request.mode = not_created`
- `raw_source_material = forbidden_in_fixture`
- `raw_review_body = forbidden_in_fixture`
- `escrow_handle_created = false`
- `encrypted_blob_created = false`
- `reviewer_access_enabled = false`
- `reviewer_lease_created = false`
- `decrypt_operation_enabled = false`
- `trusted_consent_completion_enabled = false`
- `escrow_consent_completed = false`
- `purge_path_accepted = false`
- `ttl_policy_accepted = false`
- `key_material = forbidden_in_fixture`
- `durable_storage_enabled = false`
- `model_input_includes_raw = false`
- `validator_errors_include_raw = false`
- `audit_or_client_response_includes_raw = false`
- every public, B2B, respondent, retrieval, export, ranking, identity, raw
  escrow, and dashboard flag disabled

Required gates:

- `PR-003`
- `PR-006`
- `PROTECTED_DATA_DURABILITY`
- `PURGE_PATH`
- `ESCROW_TTL_POLICY`
- `REVIEWER_ACCESS_POLICY`
- `NO_RAW_ECHO_NEGATIVE_TESTS`
- `KEY_PROFILE_ACCEPTED`

Validator schema errors return only paths and validator names. Gate failures do
not echo raw source material, raw review bodies, escrow handles, ciphertext,
key material, reviewer notes, or private source metadata.
