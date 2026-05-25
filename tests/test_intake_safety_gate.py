import json
import subprocess
import sys
from pathlib import Path

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
