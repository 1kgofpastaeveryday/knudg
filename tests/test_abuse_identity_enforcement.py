import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "abuse-identity-enforcement-request-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "abuse-identity-enforcement.blocked.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "abuse-identity-enforcement.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_abuse_identity_enforcement.py"), "--input", str(path)],
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


def test_abuse_identity_enforcement_fixture_matches_schema():
    data = load_fixture()
    validator().validate(data)
    assert data["objective_item"] == 11
    assert data["surface"] == "abuse_identity_ban_operations"
    assert data["status"] == "blocked"
    assert data["request_class"] == "preflight_only"
    assert data["requested_operation"]["action"] == "ban"
    assert data["requested_operation"]["actor_ref"]["ref_kind"] == "opaque_preflight_actor_ref"
    assert data["requested_operation"]["purpose"] == "abuse_preflight"
    assert data["requested_operation"]["reason_class"] == "ban_evasion"
    assert data["requested_operation"]["case_digest"] != data["requested_operation"]["decision_digest"]
    assert data["requested_operation"]["decision_digest"] != data["requested_operation"]["idempotency_digest"]
    assert data["authorization_model"]["actor_role_model_accepted"] is False
    assert set(data["authorization_model"]["high_risk_review_required_for"]) == {"suspend", "ban"}
    assert data["authorization_model"]["two_person_review_required_for"] == ["ban"]
    assert data["anti_enumeration_contract"]["no_subject_existence_disclosure"] is True
    assert data["anti_enumeration_contract"]["lockout_status_disclosure"] == "none"
    assert data["anti_enumeration_contract"]["rate_limit_reason_disclosure"] == "generic_only"
    assert data["identity_minimization_contract"]["raw_identifier_collection"] == "forbidden"
    assert data["identity_minimization_contract"]["identity_assurance_mode"] == "not_performed"
    assert data["identity_resolution"]["mode"] == "not_performed"
    assert data["identity_resolution"]["raw_identity_values"] == "forbidden_in_fixture"
    assert data["identity_resolution"]["subject_rows"] == "none"
    assert data["identity_resolution"]["protected_fingerprint_created"] is False
    assert data["identity_resolution"]["match_status_disclosure"] == "none"
    assert data["enforcement_model"]["real_enforcement_enabled"] is False
    assert set(data["audit_event_contract"]["required_event_fields"]) >= {
        "actor_id",
        "purpose",
        "decision_digest",
        "subject_ref",
    }
    assert data["audit_event_contract"]["raw_evidence_in_audit"] == "forbidden"
    assert data["appeal_recovery_contract"]["generic_notice_required"] is True
    assert set(data["appeal_recovery_contract"]["appeal_ref_required_for"]) == {"suspend", "ban"}
    assert data["appeal_recovery_contract"]["mistaken_identity_recovery_required"] is True
    assert data["result_contract"]["enforces_ban"] is False


def test_abuse_identity_enforcement_preflight_blocks_fixture():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload["status"] == "blocked"
    assert payload["enforcement_allowed"] is False
    assert payload["objective_item"] == 11
    assert payload["requested_action"] == "ban"
    assert payload["reason_class"] == "ban_evasion"
    assert payload["command_effect"] == "preflight_only"
    assert payload["authorization_allowed"] is False
    assert payload["anti_enumeration_contract_bound"] is True
    assert payload["identity_minimization_contract_bound"] is True
    assert payload["appeal_recovery_contract_bound"] is True
    assert payload["performs_identity_processing"] is False
    assert payload["stores_raw_identity"] is False
    assert payload["creates_subject_row"] is False
    assert payload["creates_protected_fingerprint"] is False
    assert payload["discloses_match_status"] is False
    assert payload["enforces_ban"] is False
    assert payload["opens_public_surface"] is False
    assert payload["delivers_to_b2b"] is False
    assert payload["serves_dashboard"] is False
    assert payload["stores_raw_detail"] is False
    assert payload["writes_audit_event"] is False
    assert payload["required_gates"] == [
        "ANTI_ENUMERATION_CONTRACT",
        "APPEAL_RECOVERY_PATH",
        "AUDIT_DURABILITY",
        "AUTHORIZATION_ROLE_MODEL",
        "ED-006",
        "HIGH_RISK_REVIEW_POLICY",
        "IDEMPOTENCY_WRITE_BEFORE_EFFECT",
        "IDENTITY_MINIMIZATION_POLICY",
        "NO_IDENTITY_DISCLOSURE_NEGATIVE_TESTS",
        "PROTECTED_FINGERPRINT_PROFILE",
        "RAW_IDENTITY_RETENTION_PURGE_POLICY",
        "TNS-001",
    ]
    assert "identity processing is disabled" in payload["blocking_gates"]
    assert "ban enforcement is disabled" in payload["blocking_gates"]
    assert "actor role model is not accepted" in payload["blocking_gates"]
    assert "audit event writes are disabled" in payload["blocking_gates"]
    assert "appeal path is not accepted" in payload["blocking_gates"]
    assert "reinstatement path is not accepted" in payload["blocking_gates"]
    serialized = json.dumps(payload)
    for forbidden in ["subject_found", "matched", "match_count", "lockout_status", "account_identifier"]:
        assert forbidden not in serialized


@pytest.mark.parametrize(
    "flag",
    [
        "identity_processing_enabled",
        "real_enforcement_enabled",
        "real_ban_operations_enabled",
        "protected_fingerprint_creation_enabled",
        "subject_row_creation_enabled",
        "actual_experience_storage_enabled",
        "public_candidate_conversion_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "respondent_inquiry_enabled",
        "dashboard_enabled",
        "retrieval_enabled",
        "export_enabled",
        "ranking_enabled",
        "raw_detail_escrow_enabled",
    ],
)
def test_abuse_identity_enforcement_rejects_surface_enablement(tmp_path, flag):
    data = load_fixture()
    data["surface_enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "performs_identity_processing",
        "stores_raw_identity",
        "creates_subject_row",
        "creates_protected_fingerprint",
        "discloses_match_status",
        "enforces_ban",
        "enforces_rate_limit",
        "creates_suspension",
        "opens_appeal_case",
        "opens_public_surface",
        "delivers_to_b2b",
        "serves_dashboard",
        "stores_raw_detail",
        "writes_audit_event",
    ],
)
def test_abuse_identity_enforcement_rejects_blocked_result_effects(tmp_path, flag):
    data = load_fixture()
    data["result_contract"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mode", "performed"),
        ("raw_identity_values", "present"),
        ("protected_fingerprint_created", True),
        ("subject_rows", "present"),
        ("real_subject_rows_created", True),
        ("match_status_disclosure", "matched"),
    ],
)
def test_abuse_identity_enforcement_rejects_identity_processing(tmp_path, field, value):
    data = load_fixture()
    data["identity_resolution"][field] = value

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_enforcement_rejects_raw_actor_ref_without_echo(tmp_path):
    data = load_fixture()
    data["requested_operation"]["actor_ref"] = "operator@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "operator@example.com" not in json.dumps(payload)


@pytest.mark.parametrize("field", ["purpose", "reason_class", "decision_digest", "idempotency_digest"])
def test_abuse_identity_enforcement_rejects_missing_operation_control_fields(tmp_path, field):
    data = load_fixture()
    del data["requested_operation"][field]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["anti_enumeration_contract", "no_subject_existence_disclosure"], False),
        (["anti_enumeration_contract", "lockout_status_disclosure"], "locked"),
        (["anti_enumeration_contract", "rate_limit_reason_disclosure"], "specific_subject"),
        (["identity_minimization_contract", "raw_identifier_collection"], "allowed"),
        (["audit_event_contract", "raw_evidence_in_audit"], "allowed"),
        (["appeal_recovery_contract", "appeal_status_disclosure"], "specific"),
    ],
)
def test_abuse_identity_enforcement_rejects_control_contract_weakening(tmp_path, path, value):
    data = load_fixture()
    target = data
    for item in path[:-1]:
        target = target[item]
    target[path[-1]] = value

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_enforcement_blocks_missing_two_person_ban_review(tmp_path):
    data = load_fixture()
    data["authorization_model"]["two_person_review_required_for"] = []

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize("field", ["actor_id", "purpose", "decision_digest", "subject_ref"])
def test_abuse_identity_enforcement_blocks_missing_audit_event_contract_field(tmp_path, field):
    data = load_fixture()
    data["audit_event_contract"]["required_event_fields"] = [
        item for item in data["audit_event_contract"]["required_event_fields"] if item != field
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert f"missing audit event fields: {field}" in payload["blocking_gates"]


def test_abuse_identity_enforcement_rejects_real_enforcement_enablement(tmp_path):
    data = load_fixture()
    data["enforcement_model"]["real_enforcement_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_enforcement_rejects_active_status(tmp_path):
    data = load_fixture()
    data["status"] = "active"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_enforcement_rejects_real_ban_transition(tmp_path):
    data = load_fixture()
    for transition in data["enforcement_model"]["transitions"]:
        if transition["action"] == "ban":
            transition["real_effect_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_enforcement_blocks_missing_required_gate(tmp_path):
    data = load_fixture()
    data["required_gates"] = [item for item in data["required_gates"] if item != "PROTECTED_FINGERPRINT_PROFILE"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing required gates: PROTECTED_FINGERPRINT_PROFILE" in payload["blocking_gates"]


def test_abuse_identity_enforcement_blocks_missing_forbidden_output(tmp_path):
    data = load_fixture()
    data["forbidden_outputs"] = [item for item in data["forbidden_outputs"] if item != "protected_fingerprint"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing forbidden outputs: protected_fingerprint" in payload["blocking_gates"]


def test_abuse_identity_enforcement_blocks_missing_withheld_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["withheld_outputs"] = [
        item for item in data["output_contract"]["withheld_outputs"] if item != "device_or_network_signal"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing withheld outputs: device_or_network_signal" in payload["blocking_gates"]


def test_abuse_identity_enforcement_rejects_requested_forbidden_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["requested_outputs"].append("submitter_identity")

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_enforcement_blocks_missing_appeal_recovery_coverage(tmp_path):
    data = load_fixture()
    data["appeal_recovery"]["required_for"] = ["ban"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing appeal recovery coverage: suspend" in payload["blocking_gates"]


def test_abuse_identity_enforcement_blocks_missing_audit_event_mapping(tmp_path):
    data = load_fixture()
    data["audit_event_mapping"]["transition_events"] = [
        item for item in data["audit_event_mapping"]["transition_events"] if item["action"] != "appeal"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing audit event mappings: appeal" in payload["blocking_gates"]


def test_abuse_identity_enforcement_blocks_incorrect_ban_audit_mapping(tmp_path):
    data = load_fixture()
    for item in data["audit_event_mapping"]["transition_events"]:
        if item["action"] == "ban":
            item["audit_event_type"] = "account_warned"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "incorrect audit event mappings: ban" in payload["blocking_gates"]


def test_abuse_identity_enforcement_rejects_schema_errors_without_echo(tmp_path):
    data = load_fixture()
    data["requested_operation"]["action"] = "real-private-action"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "real-private-action" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


def test_abuse_identity_enforcement_blocks_raw_marker_without_echo(tmp_path):
    data = load_fixture()
    data["blocked_until"][0]["reason"] = "contact user@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "abuse identity enforcement request contains raw markers" in payload["blocking_gates"]
    assert "user@example.com" not in json.dumps(payload)
