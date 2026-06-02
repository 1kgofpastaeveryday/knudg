import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "abuse-identity-lane-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "abuse-identity-lane.draft.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "abuse-identity-lane.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_abuse_identity_lane.py"), "--input", str(path)],
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


def test_abuse_identity_lane_fixture_validates_without_real_identity_data():
    data = load_fixture()
    validator().validate(data)
    assert data["identity_storage"]["raw_identity_values"] == "forbidden_in_fixture"
    assert data["identity_storage"]["real_subject_rows"] == "none"
    assert data["operation_model"]["mode"] == "simulation_only"
    assert data["operation_model"]["real_enforcement_enabled"] is False
    serialized = json.dumps(data)
    assert "@" not in serialized
    assert "127.0.0.1" not in serialized


def test_abuse_identity_lane_forbids_b2b_and_retrieval_identity_surfaces():
    data = load_fixture()
    forbidden = set(data["forbidden_surfaces"])
    assert "b2b_dashboard" in forbidden
    assert "b2b_respondent_portal" in forbidden
    assert "actual_experience_storage" in forbidden
    assert "raw_detail_escrow" in forbidden
    assert "company_store_dashboard" in forbidden
    assert "public_candidate_conversion" in forbidden
    assert "respondent_inquiry" in forbidden
    assert "retrieval" in forbidden
    assert "ban" in data["allowed_actions"]
    assert "appeal" in data["allowed_actions"]


def test_abuse_identity_lane_maps_actions_to_tns_audit_events():
    data = load_fixture()
    expected = {
        "warn": "account_warned",
        "rate_limit": "account_rate_limited",
        "hold_for_review": "submission_held",
        "suspend": "account_suspended",
        "ban": "account_banned",
        "appeal": "appeal_opened",
        "reinstate": "reinstated",
        "revoke": "artifact_revoked",
        "purge": "artifact_purged",
    }
    mapping = data["audit_event_mapping"]
    assert set(mapping["preflight_required_events"]) >= {"case_opened", "identity_signal_reviewed"}
    assert {item["action"]: item["audit_event_type"] for item in mapping["transition_events"]} == expected
    assert set(expected) == set(data["allowed_actions"])
    assert all(not transition["real_effect_enabled"] for transition in data["operation_model"]["transitions"])


def test_abuse_identity_lane_rejects_unmodeled_real_subject_rows():
    data = load_fixture()
    data["identity_storage"]["real_subject_rows"] = "present"
    errors = list(validator().iter_errors(data))
    assert errors


def test_abuse_identity_lane_validator_accepts_simulation_only_fixture():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {"status": "ok", "mode": "simulation_only"}


def test_abuse_identity_lane_rejects_real_ban_effect(tmp_path):
    data = load_fixture()
    for transition in data["operation_model"]["transitions"]:
        if transition["action"] == "ban":
            transition["real_effect_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_lane_blocks_missing_audit_event_mapping(tmp_path):
    data = load_fixture()
    data["audit_event_mapping"]["transition_events"] = [
        item for item in data["audit_event_mapping"]["transition_events"] if item["action"] != "purge"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing audit event mappings: purge" in payload["blocking_gates"]


def test_abuse_identity_lane_blocks_duplicate_audit_event_mapping(tmp_path):
    data = load_fixture()
    data["audit_event_mapping"]["transition_events"].append(
        {"action": "ban", "audit_event_type": "artifact_revoked"}
    )

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "duplicate audit event mappings: ban" in payload["blocking_gates"]


def test_abuse_identity_lane_blocks_incorrect_audit_event_mapping(tmp_path):
    data = load_fixture()
    for item in data["audit_event_mapping"]["transition_events"]:
        if item["action"] == "ban":
            item["audit_event_type"] = "account_warned"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "incorrect audit event mappings: ban" in payload["blocking_gates"]


def test_abuse_identity_lane_rejects_unknown_audit_event_type(tmp_path):
    data = load_fixture()
    for item in data["audit_event_mapping"]["transition_events"]:
        if item["action"] == "rate_limit":
            item["audit_event_type"] = "real_account_rate_limit"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_lane_blocks_missing_preflight_audit_event(tmp_path):
    data = load_fixture()
    data["audit_event_mapping"]["preflight_required_events"] = ["case_opened"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing preflight audit events: identity_signal_reviewed" in payload["blocking_gates"]


def test_abuse_identity_lane_blocks_missing_b2b_forbidden_surface(tmp_path):
    data = load_fixture()
    data["forbidden_surfaces"] = [item for item in data["forbidden_surfaces"] if item != "b2b_respondent_portal"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing forbidden surfaces: b2b_respondent_portal" in payload["blocking_gates"]


@pytest.mark.parametrize("surface", ["actual_experience_storage", "raw_detail_escrow", "b2b_respondent_portal"])
def test_abuse_identity_lane_blocks_missing_forbidden_surface(tmp_path, surface):
    data = load_fixture()
    data["forbidden_surfaces"] = [item for item in data["forbidden_surfaces"] if item != surface]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert f"missing forbidden surfaces: {surface}" in payload["blocking_gates"]


def test_abuse_identity_lane_blocks_raw_marker_in_reason(tmp_path):
    data = load_fixture()
    data["blocked_until"][0]["reason"] = "contact user@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "abuse identity lane contains raw markers: @" in payload["blocking_gates"]


def test_abuse_identity_lane_rejects_real_enforcement_enablement(tmp_path):
    data = load_fixture()
    data["operation_model"]["real_enforcement_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_lane_rejects_non_simulation_mode(tmp_path):
    data = load_fixture()
    data["operation_model"]["mode"] = "active"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_abuse_identity_lane_blocks_active_status_with_blockers(tmp_path):
    data = load_fixture()
    data["status"] = "active"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "active abuse identity lane must not have blockers" in payload["blocking_gates"]
