import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_loop.py"


def run_validator(*args):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def write_json(tmp_path, value):
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_review_loop_self_test_passes():
    result = run_validator("--self-test")
    assert result.returncode == 0
    assert "self-test validated 4 schema file(s)" in result.stdout


def test_review_loop_target_manifest_rejects_loop_artifacts(tmp_path):
    manifest = {
        "artifact_type": "target-manifest",
        "schema_version": 1,
        "run_id": "review-loop-test",
        "round": 1,
        "target_class": "ordinary-review-target",
        "included_paths": ["README.md", ".codex/review-loop/run/ledger.md"],
        "excluded_paths": [],
        "target_hashes": [],
    }
    result = run_validator("--schema", "target-manifest", "--file", str(write_json(tmp_path, manifest)))
    assert result.returncode == 1
    assert "ordinary target includes loop artifact" in result.stderr


def test_review_loop_round_status_blocks_pass_with_missing_lanes(tmp_path):
    status = {
        "artifact_type": "round-status",
        "schema_version": 1,
        "run_id": "review-loop-test",
        "round": 1,
        "engine": "adversarial-review",
        "status": "PASS",
        "summary": "",
        "required_lanes_missing": ["coherence-auditor"],
    }
    result = run_validator("--schema", "round-status", "--file", str(write_json(tmp_path, status)))
    assert result.returncode == 1
    assert "PASS cannot have missing required lanes" in result.stderr


def test_review_loop_ledger_record_accepts_in_progress(tmp_path):
    ledger = {
        "artifact_type": "ledger-record",
        "schema_version": 1,
        "run_id": "review-loop-test",
        "engine": "adversarial-review",
        "stop_conditions": ["PASS", "DEGRADED", "BLOCKED", "PARKED"],
        "rounds": [],
        "final_status": "IN_PROGRESS",
    }
    result = run_validator("--schema", "ledger-record", "--file", str(write_json(tmp_path, ledger)))
    assert result.returncode == 0
    assert "matches ledger-record.json" in result.stdout
