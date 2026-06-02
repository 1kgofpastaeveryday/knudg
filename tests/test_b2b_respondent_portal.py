import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "b2b-respondent-portal-request-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "b2b-respondent-portal.blocked.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "b2b-respondent-portal.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_b2b_respondent_portal.py"), "--input", str(path)],
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


def test_b2b_respondent_portal_fixture_matches_schema():
    data = load_fixture()
    validator().validate(data)
    assert data["objective_item"] == 10
    assert data["surface"] == "b2b_respondent_portal"
    assert data["status"] == "blocked"
    assert data["blocked_until"] == [
        "ED-005",
        "NO_DISCLOSURE_NEGATIVE_TESTS",
        "RESPONDENT_POLICY",
        "MODERATION_WORKFLOW",
    ]
    assert data["source_public_candidate"]["domain"] == "public_experience_candidate"
    assert data["source_public_candidate"]["public_serving_enabled"] is False
    assert data["respondent_scope"]["identity_verification_status"] == "not_verified_preflight"
    assert data["respondent_scope"]["contact_channel_available"] is False
    assert data["response_draft"]["response_available"] is False
    assert data["surface_enablement"]["portal_enabled"] is False
    assert data["surface_enablement"]["b2b_delivery_enabled"] is False
    assert data["respondent_visibility_contract"]["visibility_state"] == "not_available_preflight"
    assert data["respondent_visibility_contract"]["identity_disclosure"] == "none"
    assert data["respondent_visibility_contract"]["raw_detail_disclosure"] == "none"
    assert data["respondent_visibility_contract"]["response_submission_policy"] == "disabled_until_gates_pass"
    assert set(data["respondent_visibility_contract"]["visible_fields"]) == set(data["output_contract"]["requested_outputs"])
    assert data["portal_view_contract"]["view_model_kind"] == "redacted_respondent_preview"
    assert data["portal_view_contract"]["view_model_state"] == "model_only_not_served"
    assert data["portal_view_contract"]["route_allocation"] == "none"
    assert data["portal_view_contract"]["access_token_issued"] is False
    assert data["portal_view_contract"]["server_render_enabled"] is False
    assert data["portal_view_contract"]["contains_submit_control"] is False
    assert data["portal_view_contract"]["contains_contact_channel"] is False
    assert data["respondent_action_contract"]["allowed_actions"] == []
    assert data["respondent_action_contract"]["action_token_issued"] is False
    assert set(data["respondent_action_contract"]["disabled_actions"]) == {
        "submit_response",
        "upload_raw_detail",
        "request_submitter_identity",
        "message_submitter",
        "claim_business_profile",
        "open_dashboard",
    }
    assert data["result_contract"]["opens_portal"] is False
    assert data["result_contract"]["delivers_to_b2b"] is False


def test_b2b_respondent_portal_preflight_blocks_fixture():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload["status"] == "blocked"
    assert payload["portal_allowed"] is False
    assert payload["objective_item"] == 10
    assert payload["command_effect"] == "preflight_only"
    assert payload["opens_portal"] is False
    assert payload["delivers_to_b2b"] is False
    assert payload["makes_response_available"] is False
    assert payload["opens_public_surface"] is False
    assert payload["serves_dashboard"] is False
    assert payload["performs_identity_processing"] is False
    assert payload["stores_raw_detail"] is False
    assert payload["required_gates"] == [
        "ED-005",
        "MODERATION_WORKFLOW",
        "NO_DISCLOSURE_NEGATIVE_TESTS",
        "RESPONDENT_POLICY",
    ]
    assert "b2b respondent portal surface is disabled" in payload["blocking_gates"]
    assert "b2b delivery is disabled" in payload["blocking_gates"]
    assert "respondent response is not available" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "flag",
    [
        "contains_raw_source",
        "contains_submitter_identity",
        "contains_device_or_network_signal",
        "contains_protected_fingerprint",
        "contains_reidentification_hint",
        "response_available",
    ],
)
def test_b2b_respondent_portal_rejects_response_draft_disclosure_flags(tmp_path, flag):
    data = load_fixture()
    data["response_draft"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "portal_enabled",
        "b2b_delivery_enabled",
        "response_submission_enabled",
        "public_serving_enabled",
        "identity_processing_enabled",
        "raw_detail_escrow_enabled",
        "dashboard_enabled",
    ],
)
def test_b2b_respondent_portal_rejects_surface_enablement(tmp_path, flag):
    data = load_fixture()
    data["surface_enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "opens_portal",
        "delivers_to_b2b",
        "makes_response_available",
        "opens_public_surface",
        "serves_dashboard",
        "performs_identity_processing",
        "stores_raw_detail",
    ],
)
def test_b2b_respondent_portal_rejects_blocked_result_effects(tmp_path, flag):
    data = load_fixture()
    data["result_contract"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_b2b_respondent_portal_blocks_missing_required_gate(tmp_path):
    data = load_fixture()
    data["required_gates"] = [item for item in data["required_gates"] if item != "RESPONDENT_POLICY"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing required gates: RESPONDENT_POLICY" in payload["blocking_gates"]


def test_b2b_respondent_portal_blocks_missing_blocked_until_gate(tmp_path):
    data = load_fixture()
    data["blocked_until"] = [item for item in data["blocked_until"] if item != "MODERATION_WORKFLOW"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing blocked_until gates: MODERATION_WORKFLOW" in payload["blocking_gates"]


def test_b2b_respondent_portal_blocks_missing_forbidden_output(tmp_path):
    data = load_fixture()
    data["forbidden_outputs"] = [item for item in data["forbidden_outputs"] if item != "escrow_key_material"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing forbidden outputs: escrow_key_material" in payload["blocking_gates"]


def test_b2b_respondent_portal_blocks_missing_visibility_withheld_field(tmp_path):
    data = load_fixture()
    data["respondent_visibility_contract"]["withheld_fields"] = [
        item for item in data["respondent_visibility_contract"]["withheld_fields"] if item != "escrow_handle"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "respondent visibility contract missing withheld fields: escrow_handle" in payload["blocking_gates"]


def test_b2b_respondent_portal_blocks_visibility_requested_output_mismatch(tmp_path):
    data = load_fixture()
    data["respondent_visibility_contract"]["visible_fields"] = [
        item for item in data["respondent_visibility_contract"]["visible_fields"] if item != "claim_type"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "respondent visible fields must match requested outputs" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "flag",
    ["access_token_issued", "server_render_enabled", "contains_submit_control", "contains_contact_channel"],
)
def test_b2b_respondent_portal_rejects_portal_view_enablement(tmp_path, flag):
    data = load_fixture()
    data["portal_view_contract"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_b2b_respondent_portal_rejects_allowed_action(tmp_path):
    data = load_fixture()
    data["respondent_action_contract"]["allowed_actions"] = ["submit_response"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_b2b_respondent_portal_rejects_action_token(tmp_path):
    data = load_fixture()
    data["respondent_action_contract"]["action_token_issued"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_b2b_respondent_portal_blocks_missing_disabled_action(tmp_path):
    data = load_fixture()
    data["respondent_action_contract"]["disabled_actions"] = [
        item for item in data["respondent_action_contract"]["disabled_actions"] if item != "open_dashboard"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "respondent action contract missing disabled actions: open_dashboard" in payload["blocking_gates"]


def test_b2b_respondent_portal_blocks_missing_withheld_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["withheld_outputs"] = [
        item for item in data["output_contract"]["withheld_outputs"] if item != "escrow_ciphertext"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing withheld outputs: escrow_ciphertext" in payload["blocking_gates"]


def test_b2b_respondent_portal_rejects_requested_forbidden_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["requested_outputs"].append("submitter_identity")

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_b2b_respondent_portal_schema_errors_do_not_echo_raw_values(tmp_path):
    data = load_fixture()
    data["respondent_scope"]["entity_type"] = "raw-private-value-123"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


def test_b2b_respondent_portal_rejects_raw_marker_without_echo(tmp_path):
    data = load_fixture()
    data["respondent_scope"]["raw_private_note"] = "user@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "user@example.com" not in json.dumps(payload)
