import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "consent-revocation-gate.draft.json"
SCHEMA = ROOT / "schemas" / "consent-revocation-gate.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_consent_revocation_gate.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "consent-gate.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_consent_revocation_gate_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["enablement"]["trusted_completion_enabled"] is False
    assert data["agent_boundaries"]["cli_mcp_can_complete_publication"] is False


def test_consent_revocation_gate_draft_validates_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "status": "ok",
        "trusted_completion_enabled": False,
        "public_publication_enabled": False,
        "surface_count": 5,
    }


def test_consent_revocation_gate_rejects_agent_publication_completion(tmp_path):
    data = load_fixture()
    data["agent_boundaries"]["cli_mcp_can_complete_publication"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_consent_revocation_gate_blocks_missing_surface(tmp_path):
    data = load_fixture()
    data["surfaces"] = [surface for surface in data["surfaces"] if surface["surface_type"] != "team_namespace_grant_consent"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing consent surfaces: team_namespace_grant_consent" in payload["blocking_gates"]


def test_consent_revocation_gate_blocks_scope_alias(tmp_path):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface_type"] == "public_publication_consent":
            surface["canonical_scope"] = "private_retention"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "public_publication_consent maps to wrong canonical scope" in payload["blocking_gates"]


def test_consent_revocation_gate_blocks_enabled_draft_surface(tmp_path):
    data = load_fixture()
    data["enablement"]["trusted_completion_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_consent_revocation_gate_accepted_requires_trusted_surfaces(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "accepted consent gate must not have blocked_until entries" in payload["blocking_gates"]
    assert "private_candidate_collection_consent is not trusted-completion ready" in payload["blocking_gates"]
