import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "intake-safety-gate.draft.json"
SCHEMA = ROOT / "schemas" / "intake-safety-gate.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_intake_safety_gate.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "intake-gate.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_intake_safety_gate_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["enablement"]["non_synthetic_submit_enabled"] is False
    assert data["enablement"]["body_persistence_enabled"] is False
    assert data["domain_coverage"]["career_private"] == "typed_only_no_ingest"
    assert data["domain_coverage"]["public_experience_candidate"] == "blocked_no_conversion"
    assert data["surface_coverage"]["actual_experience_storage"] == "blocked_no_storage"
    assert data["surface_coverage"]["b2b_respondent_portal"] == "blocked_no_surface"
    assert data["surface_coverage"]["raw_detail_escrow"] == "blocked_no_raw_escrow"
    assert data["raw_escrow_fallback_policy"]["allowed_decisions"] == ["redact_then_retry", "retry_later"]
    raw_escrow_case = data["synthetic_raw_escrow_preflight_cases"][0]
    assert raw_escrow_case["decision"] == "human_review_required"
    assert raw_escrow_case["client_response_class"] == "deferred_generic"
    assert raw_escrow_case["stores_body"] is False
    assert raw_escrow_case["escrow_handle_created"] is False
    assert raw_escrow_case["model_input_includes_raw"] is False
    assert raw_escrow_case["validator_errors_include_raw"] is False


def test_intake_safety_gate_draft_validates_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "status": "ok",
        "non_synthetic_submit_enabled": False,
        "body_persistence_enabled": False,
        "review_escrow_enabled": False,
    }


def test_intake_safety_gate_rejects_enabled_non_synthetic_submit(tmp_path):
    data = load_fixture()
    data["enablement"]["non_synthetic_submit_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_intake_safety_gate_blocks_missing_decision(tmp_path):
    data = load_fixture()
    data["decision_outcomes"] = [item for item in data["decision_outcomes"] if item["decision"] != "human_review_required"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing decisions: human_review_required" in payload["blocking_gates"]


def test_intake_safety_gate_blocks_body_storage_for_rejected_decisions(tmp_path):
    data = load_fixture()
    for item in data["decision_outcomes"]:
        if item["decision"] == "redact_then_retry":
            item["stores_body"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "redact_then_retry must not store body, create card, or index" in payload["blocking_gates"]


def test_intake_safety_gate_blocks_body_storage_for_accepted_decision_in_draft(tmp_path):
    data = load_fixture()
    for item in data["decision_outcomes"]:
        if item["decision"] == "accepted":
            item["stores_body"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "accepted must not store body, create card, or index" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "flag",
    ["stores_body", "escrow_handle_created", "model_input_includes_raw", "validator_errors_include_raw"],
)
def test_intake_safety_gate_blocks_raw_escrow_preflight_raw_flags(tmp_path, flag):
    data = load_fixture()
    data["synthetic_raw_escrow_preflight_cases"][0][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert (
        f"synthetic-raw-escrow:ambiguous-001 must not enable raw escrow flags: {flag}"
        in payload["blocking_gates"]
    )


def test_intake_safety_gate_blocks_missing_raw_escrow_human_review_case(tmp_path):
    data = load_fixture()
    data["synthetic_raw_escrow_preflight_cases"][0]["decision"] = "retry_later"
    data["synthetic_raw_escrow_preflight_cases"][0]["client_response_class"] = "retry_generic"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "raw escrow preflight must include human_review_required" in payload["blocking_gates"]


def test_intake_safety_gate_rejects_raw_escrow_detail_with_private_value(tmp_path):
    data = load_fixture()
    data["synthetic_raw_escrow_preflight_cases"][0]["audit_detail"] = "raw-private-value-123"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)


def test_intake_safety_gate_rejects_missing_domain_coverage(tmp_path):
    data = load_fixture()
    del data["domain_coverage"]["career_private"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_intake_safety_gate_rejects_public_candidate_conversion_enabled(tmp_path):
    data = load_fixture()
    data["domain_coverage"]["public_experience_candidate"] = "enabled"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_intake_safety_gate_rejects_enabled_b2b_surface(tmp_path):
    data = load_fixture()
    data["surface_coverage"]["b2b_respondent_portal"] = "enabled"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_intake_safety_gate_rejects_enabled_raw_escrow_surface(tmp_path):
    data = load_fixture()
    data["surface_coverage"]["raw_detail_escrow"] = "enabled"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_intake_safety_gate_blocks_missing_raw_escrow_fallback(tmp_path):
    data = load_fixture()
    data["raw_escrow_fallback_policy"]["allowed_decisions"] = ["redact_then_retry"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "raw escrow fallback must allow redact_then_retry and retry_later" in payload["blocking_gates"]


def test_intake_safety_gate_accepted_requires_all_schemas_and_no_blockers(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "accepted intake gate has missing schemas: audit_event, classifier_output, quarantine_metadata, scanner_output" in payload["blocking_gates"]
    assert "accepted intake gate must not have blocked_until entries" in payload["blocking_gates"]


def test_intake_safety_gate_rejects_raw_threshold_values(tmp_path):
    data = load_fixture()
    data["ingress_bounds"]["max_payload_bytes_ref"] = "1048576"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_intake_safety_gate_schema_errors_do_not_echo_raw_values(tmp_path):
    data = load_fixture()
    data["ingress_bounds"]["accepted_content_types"] = ["raw-private-value-123"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"
