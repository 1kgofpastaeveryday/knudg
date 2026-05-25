import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "auth-verifier-gate.draft.json"
SCHEMA = ROOT / "schemas" / "auth-verifier-gate.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_auth_verifier_gate.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "auth-gate.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_auth_verifier_gate_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["local_hs256"]["allowed_environments"] == ["local"]
    assert data["local_hs256"]["production_enabled"] is False


def test_auth_verifier_gate_draft_validates_local_only():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "status": "ok",
        "profile_type": "unset",
        "production_hs256_enabled": False,
    }


def test_auth_verifier_gate_rejects_production_hs256(tmp_path):
    data = load_fixture()
    data["local_hs256"]["production_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_auth_verifier_gate_blocks_missing_negative_test(tmp_path):
    data = load_fixture()
    data["negative_tests"].remove("alg_none_rejected")

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing negative tests: alg_none_rejected" in payload["blocking_gates"]


def test_auth_verifier_gate_blocks_draft_profile_selection(tmp_path):
    data = load_fixture()
    data["non_local_profile"]["profile_type"] = "asymmetric_jwks"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "draft auth verifier gate cannot self-select a non-local profile" in payload["blocking_gates"]


def test_auth_verifier_gate_accepted_requires_complete_profile(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "accepted auth verifier gate must select a non-local profile" in payload["blocking_gates"]
    assert "accepted auth verifier gate must select sender-constrained proof" in payload["blocking_gates"]
    assert "accepted auth verifier gate must not have blocked_until entries" in payload["blocking_gates"]
