import json
import subprocess
import sys
from pathlib import Path

import pytest
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
    assert data["status"] == "private_retention_accepted"
    assert data["enablement"]["trusted_completion_enabled"] is True
    assert data["agent_boundaries"]["cli_mcp_can_complete_publication"] is False
    assert data["experience_domain_boundaries"]["career_private"]["real_ingest_enabled"] is True
    assert data["experience_domain_boundaries"]["career_private"]["private_retention_completion_enabled"] is True
    assert data["experience_domain_boundaries"]["public_experience_candidate"]["real_ingest_enabled"] is False
    assert data["experience_domain_boundaries"]["place_service_experience"]["requires_domain_scoped_revocation"] is True


def test_consent_revocation_gate_fixture_keeps_public_team_launch_enablement_off():
    data = load_fixture()
    assert data["enablement"] == {
        "trusted_completion_enabled": True,
        "team_sharing_enabled": False,
        "public_publication_enabled": False,
        "terminal_publication_completion_enabled": False,
    }
    assert data["agent_boundaries"] == {
        "cli_mcp_can_create_handoff": True,
        "cli_mcp_can_complete_private_retention": False,
        "cli_mcp_can_complete_team_grant": False,
        "cli_mcp_can_complete_publication": False,
        "workers_can_complete_consent": False,
    }


def test_consent_revocation_gate_draft_validates_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "status": "ok",
        "trusted_completion_enabled": True,
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


def test_consent_revocation_gate_blocks_draft_trusted_completion(tmp_path):
    data = load_fixture()
    data["status"] = "draft_scaffold"
    data["enablement"]["trusted_completion_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"


@pytest.mark.parametrize("flag", [
    "trusted_completion_enabled",
    "team_sharing_enabled",
    "public_publication_enabled",
    "terminal_publication_completion_enabled",
])
def test_consent_revocation_gate_rejects_any_enabled_draft_surface(tmp_path, flag):
    data = load_fixture()
    data["status"] = "draft_scaffold"
    data["enablement"]["trusted_completion_enabled"] = False
    data["enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == (3 if flag == "trusted_completion_enabled" else 2)
    assert payload["status"] == ("blocked" if flag == "trusted_completion_enabled" else "rejected")


@pytest.mark.parametrize("flag", [
    "cli_mcp_can_complete_private_retention",
    "cli_mcp_can_complete_team_grant",
    "cli_mcp_can_complete_publication",
    "workers_can_complete_consent",
])
def test_consent_revocation_gate_rejects_any_agent_or_worker_completion(tmp_path, flag):
    data = load_fixture()
    data["agent_boundaries"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_consent_revocation_gate_rejects_missing_experience_domain_boundary(tmp_path):
    data = load_fixture()
    del data["experience_domain_boundaries"]["career_private"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_consent_revocation_gate_rejects_public_candidate_conversion(tmp_path):
    data = load_fixture()
    data["experience_domain_boundaries"]["public_experience_candidate"]["public_candidate_conversion_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_consent_revocation_gate_blocks_draft_trusted_transport(tmp_path):
    data = load_fixture()
    data["status"] = "draft_scaffold"
    data["enablement"]["trusted_completion_enabled"] = False
    for surface in data["surfaces"]:
        if surface["surface_type"] == "private_retention_consent":
            surface["completion_transport"] = "trusted_browser_or_os_surface"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "private_retention_consent cannot use trusted completion transport before acceptance" in payload["blocking_gates"]


def test_consent_revocation_gate_private_retention_only_keeps_public_and_team_disabled(tmp_path):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface_type"] == "public_publication_consent":
            surface["status"] = "trusted_completion_ready"
            surface["completion_transport"] = "trusted_browser_or_os_surface"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert (
        "public_publication_consent cannot be trusted-completion ready for private-retention-only acceptance"
        in payload["blocking_gates"]
    )


def test_consent_revocation_gate_blocks_duplicate_surface(tmp_path):
    data = load_fixture()
    data["surfaces"].append(dict(data["surfaces"][0]))

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "duplicate consent surfaces: private_candidate_collection_consent" in payload["blocking_gates"]


def test_consent_revocation_gate_accepted_requires_trusted_surfaces(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "accepted consent gate must not have blocked_until entries" in payload["blocking_gates"]
    assert "private_candidate_collection_consent is not trusted-completion ready" in payload["blocking_gates"]
