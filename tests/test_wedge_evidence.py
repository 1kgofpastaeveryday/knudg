import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64


def run_evidence(*args):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "wedge_evidence.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def snapshot():
    return {
        "snapshot_id": "summary_20260514_dryrun01",
        "protocol_version": "wedge-001-protocol-v0",
        "evidence_register": [
            {
                "evidence_id": "ev_seedcandidate000001",
                "evidence_type": "seed_candidate",
                "storage_location": "private://evidence/seedcandidate000001",
                "artifact_digest": DIGEST_A,
                "source_class": "synthetic_fixture",
                "consent_state": "not_required_for_synthetic",
                "retention_deadline": "policy:synthetic-retain",
                "owner": "role:knudg-operator",
                "allowed_repo_reference": "ev_seedcandidate000001#digest",
            }
        ],
        "seed_candidates": [
            {
                "candidate_id": "cand_seedcandidate000001",
                "source_class": "synthetic_fixture",
                "source_rights_state": "clear",
                "consent_artifact_id": "not_required_for_synthetic",
                "source_digest": DIGEST_B,
                "redacted_artifact_digest": DIGEST_C,
                "fallback_visibility": "synthetic",
                "outcome_type": "solved",
                "exact_error_signature": "npm-econnreset",
                "tool_coordinates": "npm:example-pkg",
                "environment_bounds": "node-20/windows",
                "risk_band": "low",
                "high_risk_flags": [],
                "redaction_minutes": 3,
                "review_minutes": 5,
                "reproduction_required": "no",
                "reproduction_minutes": "not_applicable",
                "reviewer_confidence": "high",
                "useful_summary_eligible": "yes",
                "decision": "accepted_private",
                "rejection_reason": "",
            }
        ],
    }


def write_json(tmp_path, value):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_wedge_evidence_writes_repo_safe_summary(tmp_path):
    input_path = write_json(tmp_path, snapshot())
    output_path = tmp_path / "summary.json"

    code, payload = run_evidence("summary", "--input", str(input_path), "--output", str(output_path))
    assert code == 0
    assert payload["status"] == "ok"

    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["candidate_count"] == 1
    assert set(summary) == {
        "allowed_repo_reference",
        "candidate_count",
        "candidate_count_by_decision",
        "candidate_count_by_risk_band",
        "candidate_count_by_source_class",
        "consent_count_by_state",
        "evidence_count_by_type",
        "high_risk_count",
        "protocol_version",
        "redaction_minutes",
        "reproduction_minutes",
        "review_minutes",
        "snapshot_digest",
        "snapshot_id",
        "source_rights_rejection_count",
        "useful_summary_eligible_count",
    }
    assert summary["candidate_count_by_source_class"] == {"synthetic_fixture": 1}
    assert summary["redaction_minutes"] == {"median": 3, "p90": 3}
    assert set(summary["allowed_repo_reference"]) == {"snapshot_digest", "snapshot_id"}
    assert set(summary["review_minutes"]) == {"median", "p90"}
    assert set(summary["reproduction_minutes"]) == {"median", "p90"}
    serialized = json.dumps(summary)
    assert "npm-econnreset" not in serialized
    assert "node-20/windows" not in serialized
    assert "private://evidence/seedcandidate000001" not in serialized
    assert summary["allowed_repo_reference"]["snapshot_digest"].startswith("sha256:")


def test_wedge_evidence_rejects_raw_private_values(tmp_path):
    data = snapshot()
    data["seed_candidates"][0]["exact_error_signature"] = "https://github.com/private/repo/issues/1"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw/private-looking value" in payload["error"]


def test_wedge_evidence_rejects_unknown_fields_and_unclear_public_rights(tmp_path):
    data = snapshot()
    data["seed_candidates"][0]["raw_transcript"] = "do not store this"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert "unknown fields" in payload["error"]

    data = snapshot()
    data["seed_candidates"][0]["source_rights_state"] = "unclear_private_only"
    data["seed_candidates"][0]["fallback_visibility"] = "public_candidate"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert "unclear rights" in payload["error"]


def test_wedge_evidence_unknown_field_errors_do_not_echo_raw_keys(tmp_path):
    data = snapshot()
    data["seed_candidates"][0]["https://github.com/private/repo"] = "x"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert "unknown fields" in payload["error"]
    assert "github.com" not in json.dumps(payload)
    assert "private/repo" not in json.dumps(payload)

    data = snapshot()
    data["https://github.com/private/repo"] = "x"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert "unknown fields" in payload["error"]
    assert "github.com" not in json.dumps(payload)
    assert "private/repo" not in json.dumps(payload)


def test_wedge_evidence_rejection_errors_do_not_echo_raw_values(tmp_path):
    data = snapshot()
    data["seed_candidates"][0]["source_class"] = "https://github.com/private/repo"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "invalid value" in payload["error"]
    assert "github.com" not in json.dumps(payload)
    assert "private/repo" not in json.dumps(payload)


def test_wedge_evidence_rejection_reason_is_code_only(tmp_path):
    data = snapshot()
    data["seed_candidates"][0]["decision"] = "rejected"
    data["seed_candidates"][0]["rejection_reason"] = "Customer Acme asked us to drop this"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "invalid value" in payload["error"]
    assert "Customer Acme" not in json.dumps(payload)

    data = snapshot()
    data["seed_candidates"][0]["decision"] = "rejected"
    data["seed_candidates"][0]["rejection_reason"] = "source_rights_rejected"
    input_path = write_json(tmp_path, data)

    code, payload = run_evidence("validate", "--input", str(input_path))
    assert code == 0
    assert payload["status"] == "ok"


def test_wedge_evidence_npm_wrapper_help():
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    assert npm is not None
    result = subprocess.run(
        [npm, "run", "wedge:evidence", "--", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "Validate and summarize WEDGE-001 opaque evidence snapshots" in result.stdout
