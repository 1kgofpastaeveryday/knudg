import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "m3-retrieval-gates.draft.json"
SCHEMA = ROOT / "schemas" / "m3-retrieval-gates.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_m3_gates.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "gates.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_m3_retrieval_gate_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["status"] == "draft_scaffold"
    assert data["protected_data_enablement"]["enabled"] is False
    assert data["proof_profile"]["status"] == "open"
    assert data["proof_profile"]["accepted_profile"] is None


def test_m3_retrieval_gate_draft_validates_but_remains_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {"status": "ok", "protected_data_enabled": False}


def test_m3_retrieval_gate_rejects_protected_data_enablement(tmp_path):
    data = load_fixture()
    data["protected_data_enablement"]["enabled"] = True
    path = write_json(tmp_path, data)

    code, payload = run_validator(path)
    assert code == 2
    assert payload["status"] == "rejected"


def test_m3_retrieval_gate_blocks_premature_accepted_status(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"
    path = write_json(tmp_path, data)

    code, payload = run_validator(path)
    assert code == 3
    assert payload["status"] == "blocked"
    assert "accepted gate requires exact_fts.rank_formula" in payload["blocking_gates"]
    assert "accepted gate requires authoritative DEC-014A accepted proof profile" in payload["blocking_gates"]


def test_m3_retrieval_gate_blocks_self_asserted_dec_014a_acceptance(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"
    data["exact_fts"]["tokenizer_profile"] = "postgres-english"
    data["exact_fts"]["rank_formula"] = "ts_rank_cd_plus_exact_v0"
    data["exact_fts"]["score_normalization"] = "minmax_per_replay_band_v0"
    data["proof_profile"]["status"] = "accepted"
    data["proof_profile"]["accepted_profile"] = "DPoP"
    path = write_json(tmp_path, data)

    code, payload = run_validator(path)
    assert code == 3
    assert payload["status"] == "blocked"
    assert "accepted gate requires existing exact/FTS accepted spec artifact" in payload["blocking_gates"]
    assert "accepted gate requires authoritative DEC-014A accepted proof profile" in payload["blocking_gates"]
