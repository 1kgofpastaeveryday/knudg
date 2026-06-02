import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "raw-detail-escrow-request-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "raw-detail-escrow.blocked.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "raw-detail-escrow.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_raw_detail_escrow.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_raw_detail_escrow_fixture_matches_schema():
    data = load_fixture()
    validator().validate(data)
    assert data["objective_item"] == 12
    assert data["surface"] == "raw_detail_escrow"
    assert data["status"] == "blocked"
    assert data["request_class"] == "preflight_only"
    assert data["escrow_request"]["mode"] == "not_created"
    assert data["escrow_request"]["raw_source_material"] == "forbidden_in_fixture"
    assert data["escrow_request"]["raw_review_body"] == "forbidden_in_fixture"
    assert data["escrow_request"]["escrow_handle_created"] is False
    assert data["escrow_request"]["encrypted_blob_created"] is False
    assert data["escrow_request"]["reviewer_lease_created"] is False
    assert data["escrow_policy_contract"]["purpose_binding"] == "intake_review_only"
    assert data["escrow_policy_contract"]["b2b_release_allowed"] is False
    assert data["consent_revocation"]["required_scope"] == "intake_review_escrow"
    assert data["protected_storage"]["key_material"] == "forbidden_in_fixture"
    assert data["cryptographic_envelope_contract"]["envelope_created"] is False
    assert data["cryptographic_envelope_contract"]["key_separation_required"] is True
    assert data["cryptographic_envelope_contract"]["aad_binds_source_and_consent"] is True
    assert data["reviewer_access_contract"]["lease_mode"] == "disabled_preflight_only"
    assert data["reviewer_access_contract"]["copy_export_allowed"] is False
    assert data["retention_purge_contract"]["retention_mode"] == "no_retention_preflight"
    assert data["retention_purge_contract"]["backup_purge_required"] is True
    assert data["audit_echo_contract"]["audit_reference_mode"] == "digest_only"
    assert data["audit_echo_contract"]["raw_in_b2b_or_dashboard"] == "forbidden"
    assert data["result_contract"]["stores_raw_detail"] is False


def test_raw_detail_escrow_preflight_blocks_fixture():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload["status"] == "blocked"
    assert payload["escrow_allowed"] is False
    assert payload["objective_item"] == 12
    assert payload["surface"] == "raw_detail_escrow"
    assert payload["command_effect"] == "preflight_only"
    assert payload["purpose_binding"] == "intake_review_only"
    assert payload["cryptographic_envelope_bound"] is True
    assert payload["reviewer_access_contract_bound"] is True
    assert payload["retention_purge_contract_bound"] is True
    assert payload["audit_digest_only_contract_bound"] is True
    assert payload["stores_raw_detail"] is False
    assert payload["creates_escrow_handle"] is False
    assert payload["creates_encrypted_blob"] is False
    assert payload["stores_key_material"] is False
    assert payload["opens_reviewer_access"] is False
    assert payload["creates_reviewer_lease"] is False
    assert payload["decrypts_escrow"] is False
    assert payload["sends_raw_to_model_input"] is False
    assert payload["echoes_raw_in_validator_errors"] is False
    assert payload["echoes_raw_in_audit_or_client_response"] is False
    assert payload["opens_public_surface"] is False
    assert payload["delivers_to_b2b"] is False
    assert payload["serves_dashboard"] is False
    assert payload["performs_identity_processing"] is False
    assert payload["makes_retrievable"] is False
    assert payload["exports_raw_detail"] is False
    assert payload["writes_audit_event"] is False
    assert payload["required_gates"] == [
        "ACCESS_LEASE_POLICY",
        "AUDIT_DIGEST_ONLY_POLICY",
        "CRYPTOGRAPHIC_ENVELOPE_PROFILE",
        "ESCROW_TTL_POLICY",
        "KEY_PROFILE_ACCEPTED",
        "NO_RAW_ECHO_NEGATIVE_TESTS",
        "PR-003",
        "PR-006",
        "PROTECTED_DATA_DURABILITY",
        "PURGE_PATH",
        "RAW_DETAIL_PURPOSE_BINDING",
        "RESTORE_BACKUP_PURGE_POLICY",
        "REVIEWER_ACCESS_POLICY",
    ]
    assert "intake review escrow consent is not completed" in payload["blocking_gates"]
    assert "protected-data durability is disabled" in payload["blocking_gates"]
    assert "raw detail escrow surface is disabled" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "flag",
    [
        "raw_detail_escrow_enabled",
        "escrow_write_enabled",
        "encrypted_blob_storage_enabled",
        "reviewer_access_enabled",
        "decrypt_operation_enabled",
        "reviewer_lease_creation_enabled",
        "model_input_includes_raw",
        "validator_errors_include_raw",
        "audit_or_client_response_includes_raw",
        "real_data_ingest_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "identity_processing_enabled",
        "dashboard_enabled",
        "retrieval_enabled",
        "export_enabled",
        "ranking_enabled",
    ],
)
def test_raw_detail_escrow_rejects_surface_enablement(tmp_path, flag):
    data = load_fixture()
    data["surface_enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "stores_raw_detail",
        "creates_escrow_handle",
        "creates_encrypted_blob",
        "stores_key_material",
        "opens_reviewer_access",
        "creates_reviewer_lease",
        "decrypts_escrow",
        "sends_raw_to_model_input",
        "echoes_raw_in_validator_errors",
        "echoes_raw_in_audit_or_client_response",
        "opens_public_surface",
        "delivers_to_b2b",
        "serves_dashboard",
        "performs_identity_processing",
        "makes_retrievable",
        "exports_raw_detail",
        "writes_audit_event",
    ],
)
def test_raw_detail_escrow_rejects_blocked_result_effects(tmp_path, flag):
    data = load_fixture()
    data["result_contract"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "escrow_handle_created",
        "encrypted_blob_created",
        "reviewer_access_enabled",
        "reviewer_lease_created",
        "decrypt_operation_enabled",
    ],
)
def test_raw_detail_escrow_rejects_escrow_request_effects(tmp_path, flag):
    data = load_fixture()
    data["escrow_request"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "trusted_consent_completion_enabled",
        "escrow_consent_completed",
        "purge_path_accepted",
        "ttl_policy_accepted",
    ],
)
def test_raw_detail_escrow_rejects_completed_consent_or_policy(tmp_path, flag):
    data = load_fixture()
    data["consent_revocation"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    ["durable_storage_enabled", "backup_retention_enabled", "restore_quarantine_enabled", "access_audit_enabled"],
)
def test_raw_detail_escrow_rejects_protected_storage_enablement(tmp_path, flag):
    data = load_fixture()
    data["protected_storage"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["escrow_policy_contract", "public_release_allowed"], True),
        (["escrow_policy_contract", "b2b_release_allowed"], True),
        (["escrow_policy_contract", "respondent_release_allowed"], True),
        (["escrow_policy_contract", "model_training_allowed"], True),
        (["cryptographic_envelope_contract", "envelope_created"], True),
        (["cryptographic_envelope_contract", "key_separation_required"], False),
        (["cryptographic_envelope_contract", "aad_binds_source_and_consent"], False),
        (["cryptographic_envelope_contract", "nonce_uniqueness_required"], False),
        (["reviewer_access_contract", "lease_mode"], "enabled"),
        (["reviewer_access_contract", "copy_export_allowed"], True),
        (["reviewer_access_contract", "bulk_access_allowed"], True),
        (["retention_purge_contract", "retention_mode"], "retain_until_ttl"),
        (["retention_purge_contract", "backup_purge_required"], False),
        (["retention_purge_contract", "restore_quarantine_required"], False),
        (["audit_echo_contract", "raw_in_model_input"], "allowed"),
        (["audit_echo_contract", "raw_in_b2b_or_dashboard"], "allowed"),
    ],
)
def test_raw_detail_escrow_rejects_control_contract_weakening(tmp_path, path, value):
    data = load_fixture()
    target = data
    for item in path[:-1]:
        target = target[item]
    target[path[-1]] = value

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_raw_detail_escrow_blocks_missing_required_gate(tmp_path):
    data = load_fixture()
    data["required_gates"] = [item for item in data["required_gates"] if item != "PURGE_PATH"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing required gates: PURGE_PATH" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "gate",
    [
        "RAW_DETAIL_PURPOSE_BINDING",
        "CRYPTOGRAPHIC_ENVELOPE_PROFILE",
        "ACCESS_LEASE_POLICY",
        "RESTORE_BACKUP_PURGE_POLICY",
        "AUDIT_DIGEST_ONLY_POLICY",
    ],
)
def test_raw_detail_escrow_blocks_missing_control_gate(tmp_path, gate):
    data = load_fixture()
    data["required_gates"] = [item for item in data["required_gates"] if item != gate]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert f"missing required gates: {gate}" in payload["blocking_gates"]


@pytest.mark.parametrize("field", ["source_record_digest", "redacted_artifact_digest", "raw_payload_digest"])
def test_raw_detail_escrow_blocks_missing_audit_digest_field(tmp_path, field):
    data = load_fixture()
    data["audit_echo_contract"]["digest_fields_required"] = [
        item for item in data["audit_echo_contract"]["digest_fields_required"] if item != field
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert f"missing audit digest fields: {field}" in payload["blocking_gates"]


def test_raw_detail_escrow_blocks_missing_forbidden_output(tmp_path):
    data = load_fixture()
    data["forbidden_outputs"] = [item for item in data["forbidden_outputs"] if item != "escrow_key_material"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing forbidden outputs: escrow_key_material" in payload["blocking_gates"]


def test_raw_detail_escrow_blocks_missing_withheld_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["withheld_outputs"] = [
        item for item in data["output_contract"]["withheld_outputs"] if item != "raw_source_material"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing withheld outputs: raw_source_material" in payload["blocking_gates"]


def test_raw_detail_escrow_rejects_requested_forbidden_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["requested_outputs"].append("raw_source_material")

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_raw_detail_escrow_rejects_active_status(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_raw_detail_escrow_rejects_schema_errors_without_echo(tmp_path):
    data = load_fixture()
    data["source_context"]["domain"] = "raw-private-domain"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-domain" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


def test_raw_detail_escrow_blocks_raw_marker_without_echo(tmp_path):
    data = load_fixture()
    data["blocked_until"][0]["reason"] = "contact user@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "raw detail escrow request contains raw markers" in payload["blocking_gates"]
    assert "user@example.com" not in json.dumps(payload)
