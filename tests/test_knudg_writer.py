import json
import subprocess
import sys
from pathlib import Path

from scripts.card_payload import canonical_digest, validate_card_payload_v1
from scripts.knudg_writer import build_card_payload


ROOT = Path(__file__).resolve().parents[1]


def draft_payload(**overrides):
    payload = {
        "schema_version": "writer-draft-v0",
        "request_id": "draft_req_000001",
        "source_class": "synthetic",
        "outcome_type": "solved",
        "goal": "capture a repeated local setup fix",
        "symptom": "local dev server was not configured",
        "environment": {"agent_tool": "Codex", "coarse_os": "windows"},
        "context_fingerprint": {"repo_shape": "python-node-local-plugin"},
        "successful_path": ["set the local profile server URL", "pin server capabilities"],
        "failed_paths": [],
        "known_unknowns": [],
        "scope_limits": ["synthetic local dogfood only"],
        "risk_flags": [],
    }
    payload.update(overrides)
    return payload


def run_writer(tmp_path, payload, *extra_args):
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudg_writer.py"), "draft-card", "--input", str(path), *extra_args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, result.stdout


def test_build_solved_synthetic_card_payload_and_digest(tmp_path):
    code, stdout = run_writer(tmp_path, draft_payload())
    assert code == 0
    result = json.loads(stdout)
    assert result["ok"] is True
    assert result["status"] == "local_draft_only"
    assert result["stored"] is False
    assert result["publication_enabled"] is False
    validate_card_payload_v1(result["payload"])
    assert result["digest"] == canonical_digest(result["payload"])
    assert result["payload"]["privacy"]["source_class"] == "synthetic"
    assert result["payload"]["safety"]["safety_class"] == "low"


def test_failed_only_and_unknown_clarified_outcomes_are_supported():
    failed = build_card_payload(
        draft_payload(
            outcome_type="failed_only",
            successful_path=["ignored for failed only"],
            failed_paths=["retrying the same command did not help"],
        )
    )
    assert failed["successful_path"] is None
    assert failed["failed_paths"]
    validate_card_payload_v1(failed)

    unknown = build_card_payload(
        draft_payload(
            outcome_type="unknown_clarified",
            successful_path=None,
            known_unknowns=["the remote service behavior is not yet verified"],
        )
    )
    assert unknown["known_unknowns"]
    validate_card_payload_v1(unknown)


def test_writer_rejects_raw_private_fields_and_values(tmp_path):
    for payload in [
        draft_payload(raw_log="Traceback with private content"),
        draft_payload(goal="fix C:\\Users\\4\\private\\repo"),
        draft_payload(symptom="token leaked in command output"),
        draft_payload(context_fingerprint={"repo": "https://github.com/private/repo"}),
        draft_payload(source_class="private_session"),
    ]:
        code, stdout = run_writer(tmp_path, payload)
        result = json.loads(stdout)
        assert code == 2
        assert result["ok"] is False
        assert result["stored"] is False
        assert result["publication_enabled"] is False
        assert "private/repo" not in stdout
        assert "Traceback" not in stdout
        assert "token leaked" not in stdout


def test_writer_digest_and_canonical_modes(tmp_path):
    payload = draft_payload()
    code, digest = run_writer(tmp_path, payload, "--digest")
    assert code == 0
    assert digest.startswith("sha256:jcs-rfc8785:v1:")

    code, canonical = run_writer(tmp_path, payload, "--canonical")
    assert code == 0
    loaded = json.loads(canonical)
    validate_card_payload_v1(loaded)
