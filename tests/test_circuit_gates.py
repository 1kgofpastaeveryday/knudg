import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "circuit-gates.draft.json"
SCHEMA = ROOT / "schemas" / "circuit-gates.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_circuit_gates.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "circuits.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_circuit_gate_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["enablement"]["live_mutation_enabled"] is False
    assert data["enablement"]["public_publication_enabled"] is False


def test_circuit_gate_draft_validates_with_surfaces_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "status": "ok",
        "live_mutation_enabled": False,
        "public_publication_enabled": False,
    }


def test_circuit_gate_rejects_enabled_surfaces(tmp_path):
    for field in ["live_mutation_enabled", "public_publication_enabled"]:
        data = load_fixture()
        data["enablement"][field] = True
        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 2
        assert payload["status"] == "rejected"


def test_circuit_gate_requires_all_families(tmp_path):
    data = load_fixture()
    data["families"] = [item for item in data["families"] if item["family"] != "public_wedge_publication"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "missing circuit families: public_wedge_publication" in payload["blocking_gates"]


def test_circuit_gate_blocks_unsafe_auth_revocation_behavior(tmp_path):
    data = load_fixture()
    for family in data["families"]:
        if family["family"] == "auth_revocation_data_integrity_backup":
            family["postgres_unavailable_behavior"] = "disable_dependency_exact_fts_or_no_suggestion"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "auth_revocation_data_integrity_backup postgres-unavailable behavior mismatch" in payload["blocking_gates"]


def test_circuit_gate_blocks_auto_clear_for_every_family(tmp_path):
    for family_name in [item["family"] for item in load_fixture()["families"]]:
        data = load_fixture()
        for family in data["families"]:
            if family["family"] == family_name:
                family["auto_clear_allowed"] = True

        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 3
        assert f"{family_name} must not auto-clear" in payload["blocking_gates"]


def test_circuit_gate_blocks_stale_behavior_mismatch(tmp_path):
    for family_name in [item["family"] for item in load_fixture()["families"]]:
        data = load_fixture()
        for family in data["families"]:
            if family["family"] == family_name:
                family["stale_emergency_behavior"] = "remain_disabled_no_auto_clear"
                if family_name == "public_wedge_publication":
                    family["stale_emergency_behavior"] = "keep_deny_until_probe"

        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 3
        assert f"{family_name} stale emergency behavior mismatch" in payload["blocking_gates"]


def test_circuit_gate_blocks_postgres_behavior_mismatch_for_every_family(tmp_path):
    for family_name in [item["family"] for item in load_fixture()["families"]]:
        data = load_fixture()
        for family in data["families"]:
            if family["family"] == family_name:
                family["postgres_unavailable_behavior"] = "fail_closed"
                if family_name == "auth_revocation_data_integrity_backup":
                    family["postgres_unavailable_behavior"] = "publication_search_disabled"

        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 3
        assert f"{family_name} postgres-unavailable behavior mismatch" in payload["blocking_gates"]


def test_circuit_gate_rejects_duplicate_families(tmp_path):
    data = load_fixture()
    data["families"].append(dict(data["families"][0]))

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "duplicate circuit families: auth_revocation_data_integrity_backup" in payload["blocking_gates"]
