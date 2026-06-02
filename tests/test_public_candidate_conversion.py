import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "public-candidate-conversion-request-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "public-candidate-conversion.blocked.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "public-candidate-conversion.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_public_candidate_conversion.py"), "--input", str(path)],
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


def test_public_candidate_conversion_fixture_matches_schema():
    data = load_fixture()
    validator().validate(data)
    assert data["objective_item"] == 9
    assert data["surface"] == "public_candidate_conversion"
    assert data["status"] == "blocked"
    assert data["required_gates"] == ["PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"]
    assert data["blocked_until"] == ["PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"]
    assert data["source_private_record"]["private_record_mutation"] == "forbidden"
    assert data["source_private_record"]["source_raw_retention"] == "none"
    assert data["source_private_record"]["record_id"] != data["source_private_record"]["private_retention_consent_id"]
    assert data["new_public_candidate_artifact"]["domain"] == "public_experience_candidate"
    assert data["new_public_candidate_artifact"]["stored_public_card"] is False
    assert data["public_candidate_payload"]["schema_version"] == "public-experience-candidate-payload-v0"
    assert data["public_candidate_payload"]["publication_state"] == "candidate_only_not_served"
    assert data["public_candidate_payload"]["source_attribution"] == "redacted_private_experience_record"
    assert data["approval_path"]["exact_artifact_approval_required"] is True
    assert data["approval_path"]["reviewer_publish_required"] is True
    assert data["approval_path"]["approval_completed"] is False
    assert data["surface_enablement"]["conversion_enabled"] is False
    assert data["result_contract"]["mutates_private_record"] is False


def test_public_candidate_conversion_preflight_blocks_fixture_without_approval_or_surface_enablement():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload["status"] == "blocked"
    assert payload["conversion_allowed"] is False
    assert payload["command_effect"] == "preflight_only"
    assert payload["creates_public_card"] is False
    assert payload["mutates_private_record"] is False
    assert payload["opens_public_surface"] is False
    assert payload["delivers_to_b2b"] is False
    assert payload["serves_dashboard"] is False
    assert payload["stores_raw_detail"] is False
    assert payload["required_gates"] == ["PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"]
    assert "exact artifact approval is not completed" in payload["blocking_gates"]
    assert "reviewer publish is not completed" in payload["blocking_gates"]
    assert "public candidate conversion surface is disabled" in payload["blocking_gates"]


def test_public_candidate_conversion_rejects_in_place_private_mutation(tmp_path):
    data = load_fixture()
    data["source_private_record"]["private_record_mutation"] = "allowed"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_public_candidate_conversion_blocks_reused_private_digest(tmp_path):
    data = load_fixture()
    data["new_public_candidate_artifact"]["artifact_digest"] = data["source_private_record"]["record_digest"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "public candidate conversion requires a new artifact digest" in payload["blocking_gates"]


def test_public_candidate_conversion_blocks_same_record_and_consent_id(tmp_path):
    data = load_fixture()
    data["source_private_record"]["private_retention_consent_id"] = data["source_private_record"]["record_id"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "public candidate conversion source record and consent ids must be distinct" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "flag",
    [
        "conversion_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "identity_processing_enabled",
        "raw_detail_escrow_enabled",
        "dashboard_enabled",
    ],
)
def test_public_candidate_conversion_rejects_surface_enablement(tmp_path, flag):
    data = load_fixture()
    data["surface_enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "creates_public_card",
        "mutates_private_record",
        "opens_public_surface",
        "delivers_to_b2b",
        "serves_dashboard",
        "stores_raw_detail",
    ],
)
def test_public_candidate_conversion_rejects_blocked_result_effects(tmp_path, flag):
    data = load_fixture()
    data["result_contract"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_public_candidate_conversion_rejects_missing_exact_artifact_approval(tmp_path):
    data = load_fixture()
    data["approval_path"]["exact_artifact_approval_required"] = False

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_public_candidate_conversion_rejects_completed_approval_in_preflight(tmp_path):
    data = load_fixture()
    data["approval_path"]["approval_completed"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_public_candidate_conversion_blocks_missing_forbidden_output(tmp_path):
    data = load_fixture()
    data["forbidden_outputs"] = [
        item for item in data["forbidden_outputs"] if item != "submitter_identity"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing forbidden outputs: submitter_identity" in payload["blocking_gates"]


def test_public_candidate_conversion_blocks_missing_required_gate(tmp_path):
    data = load_fixture()
    data["required_gates"] = [gate for gate in data["required_gates"] if gate != "PR-006"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing required gates: PR-006" in payload["blocking_gates"]


def test_public_candidate_conversion_blocks_missing_blocked_until_gate(tmp_path):
    data = load_fixture()
    data["blocked_until"] = [gate for gate in data["blocked_until"] if gate != "REVIEWER_PUBLISH"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing blocked_until gates: REVIEWER_PUBLISH" in payload["blocking_gates"]


def test_public_candidate_conversion_blocks_missing_withheld_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["withheld_outputs"] = [
        item for item in data["output_contract"]["withheld_outputs"] if item != "raw_source_material"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing withheld outputs: raw_source_material" in payload["blocking_gates"]


def test_public_candidate_conversion_blocks_missing_payload_excluded_detail_class(tmp_path):
    data = load_fixture()
    data["public_candidate_payload"]["excluded_private_detail_classes"] = [
        item for item in data["public_candidate_payload"]["excluded_private_detail_classes"] if item != "staff_identity"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "public candidate payload missing excluded private detail classes: staff_identity" in payload["blocking_gates"]


def test_public_candidate_conversion_schema_errors_do_not_echo_raw_values(tmp_path):
    data = load_fixture()
    data["source_private_record"]["domain"] = "raw-private-value-123"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


def test_public_candidate_conversion_blocks_raw_marker_without_echo(tmp_path):
    data = load_fixture()
    data["public_candidate_payload"]["redacted_public_candidate_summary"] = "This candidate accidentally includes user@example.com in a public field."

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "user@example.com" not in json.dumps(payload)
