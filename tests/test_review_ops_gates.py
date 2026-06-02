import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "review-ops-gates.draft.json"
SCHEMA = ROOT / "schemas" / "review-ops-gates.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_review_ops_gates.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "review-ops.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_review_ops_gate_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator(schema).validate(data)
    assert data["status"] == "draft_scaffold"
    assert data["enablement"]["reviewer_publish_enabled"] is False
    assert data["enablement"]["public_display_enabled"] is False
    assert data["enablement"]["high_risk_body_expansion_enabled"] is False


def test_review_ops_gate_draft_validates_but_keeps_surfaces_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "high_risk_body_expansion_enabled": False,
        "status": "ok",
        "reviewer_publish_enabled": False,
        "public_display_enabled": False,
    }


def test_review_ops_gate_rejects_enabled_surfaces(tmp_path):
    for field in ["reviewer_publish_enabled", "public_display_enabled", "high_risk_body_expansion_enabled"]:
        data = load_fixture()
        data["enablement"][field] = True
        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 2
        assert payload["status"] == "rejected"


def test_review_ops_gate_blocks_self_asserted_dec_018_acceptance(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "accepted gate requires authoritative DEC-018 accepted review-ops decision" in payload["blocking_gates"]
    assert "accepted gate requires existing review-ops evidence artifact" in payload["blocking_gates"]


def test_review_ops_gate_requires_high_risk_dual_review(tmp_path):
    data = load_fixture()
    for lane in data["reviewer_lanes"]:
        if lane["risk_band"] == "high":
            lane["dual_review_required"] = False
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "every high-risk lane requires dual review" in payload["blocking_gates"]


def test_review_ops_gate_blocks_mixed_high_risk_dual_review(tmp_path):
    data = load_fixture()
    data["reviewer_lanes"].append(
        {
            "lane_id": "lane_high_risk_extra_v0",
            "risk_band": "high",
            "dual_review_required": False,
            "calibration_fixture_set_id": "calibration_high_risk_extra_v0",
        }
    )

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "every high-risk lane requires dual review" in payload["blocking_gates"]


def test_review_ops_gate_requires_at_least_one_high_risk_lane(tmp_path):
    data = load_fixture()
    data["reviewer_lanes"] = [lane for lane in data["reviewer_lanes"] if lane["risk_band"] != "high"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "at least one high-risk lane is required" in payload["blocking_gates"]
