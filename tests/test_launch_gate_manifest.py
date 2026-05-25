import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "launch-gate-manifest.draft.json"
SCHEMA = ROOT / "schemas" / "launch-gate-manifest.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_launch_gate_manifest.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "launch-gates.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_launch_gate_manifest_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["status"] == "draft_all_closed"
    assert all(gate["status"] == "closed" for gate in data["gates"])


def test_launch_gate_manifest_draft_validates_all_closed():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["open_gates"] == []
    assert "non_synthetic_body_persistence_gate" in payload["closed_gates"]


def test_launch_gate_manifest_requires_all_production_gates(tmp_path):
    data = load_fixture()
    data["gates"] = [gate for gate in data["gates"] if gate["gate_id"] != "PR-006"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "missing gates: PR-006" in payload["blocking_gates"]


def test_launch_gate_manifest_rejects_duplicate_gate(tmp_path):
    data = load_fixture()
    data["gates"].append(dict(data["gates"][0]))

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "duplicate gates: PR-001" in payload["blocking_gates"]


def test_launch_gate_manifest_blocks_body_gate_without_prerequisites(tmp_path):
    data = load_fixture()
    for gate in data["gates"]:
        if gate["gate_id"] == "non_synthetic_body_persistence_gate":
            gate["status"] = "open"
            gate["public_safe_status_label"] = "open_evidence_current"
            gate["evidence_refs"] = ["evidence:opaque.body-gate"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "non_synthetic_body_persistence_gate open while PR-001 is not open" in payload["blocking_gates"]
    assert "non_synthetic_body_persistence_gate open while PR-006 is not open" in payload["blocking_gates"]


def test_launch_gate_manifest_blocks_open_label_on_closed_gate(tmp_path):
    data = load_fixture()
    data["gates"][0]["public_safe_status_label"] = "open_evidence_current"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "PR-001 closed gate cannot use open_evidence_current public label" in payload["blocking_gates"]


def test_launch_gate_manifest_rejects_private_paths_and_urls(tmp_path):
    data = load_fixture()
    data["gates"][0]["required_fixture_refs"] = ["C:/Users/private/raw.txt"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
