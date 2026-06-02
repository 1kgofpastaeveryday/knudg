import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "runbook-command-manifest.draft.json"
SCHEMA = ROOT / "schemas" / "runbook-command-manifest.schema.json"


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_runbook_manifest.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_runbook_manifest_fixture_matches_schema():
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(load_fixture())
    assert load_fixture()["status"] == "draft_scaffold"


def test_runbook_manifest_validates_without_claiming_drill_pass():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {"status": "ok", "command_count": 9, "drill_passed": False}


def test_runbook_manifest_blocks_drill_passed_without_transcripts(tmp_path):
    data = load_fixture()
    data["status"] = "drill_passed"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "drill_passed manifest requires passed transcripts" in payload["blocking_gates"][0]


def test_runbook_manifest_rejects_missing_transcript_with_path(tmp_path):
    data = load_fixture()
    data["commands"][0]["drill_transcript_path"] = "docs/operations/drills/rb-007.json"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing transcript must not name a path" in payload["blocking_gates"][0]


def test_runbook_manifest_requires_dry_run_for_mutation_drafts(tmp_path):
    data = load_fixture()
    for row in data["commands"]:
        if row["command_id"] == "cmd_queue_redrive_v0":
            row["command"] = "knudgctl queue redrive --job <job_id> --reason <reason>"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "mutation command must include --dry-run" in payload["blocking_gates"][0]


def test_runbook_manifest_requires_guarded_mutations_to_choose_dry_run_or_apply(tmp_path):
    data = load_fixture()
    for row in data["commands"]:
        if row["command_id"] == "cmd_circuit_set_v0":
            row["dry_run_behavior"] = "not_applicable"
            row["command"] = "knudgctl circuit set rerank disabled --reason <reason>"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "guarded mutation command must include --dry-run or --apply" in payload["blocking_gates"][0]

    data = load_fixture()
    for row in data["commands"]:
        if row["command_id"] == "cmd_circuit_set_v0":
            row["dry_run_behavior"] = "not_applicable"
            row["command"] = "knudgctl circuit set rerank disabled --reason <reason> --apply"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert payload["status"] == "ok"


def test_runbook_manifest_requires_initial_runbook_coverage(tmp_path):
    data = load_fixture()
    data["commands"] = [row for row in data["commands"] if row["runbook_id"] != "RB-006"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing runbook command coverage: RB-006" in payload["blocking_gates"]


def test_runbook_manifest_rejects_duplicate_ids_and_non_knudgctl_commands(tmp_path):
    data = load_fixture()
    data["commands"].append(dict(data["commands"][0]))
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "duplicate command IDs: cmd_db_backup_status_v0" in payload["blocking_gates"]

    data = load_fixture()
    data["commands"][0]["command"] = "curl https://example.invalid"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_runbook_manifest_accepts_existing_attached_transcript(tmp_path):
    transcript = ROOT / "docs" / "operations" / "drills" / "test-transcript.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text(
        json.dumps(
            {
                "schema_version": "runbook-drill-transcript-v0",
                "status": "passed",
                "command_id": "cmd_db_backup_status_v0",
                "command": "knudgctl db backup status",
                "exit_code": 2,
                "output_status": "not_configured",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        data = load_fixture()
        data["commands"][0]["drill_transcript_status"] = "attached"
        data["commands"][0]["drill_transcript_path"] = "docs/operations/drills/test-transcript.json"
        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 0
        assert payload["status"] == "ok"
    finally:
        transcript.unlink(missing_ok=True)


def test_runbook_manifest_rejects_mismatched_transcript(tmp_path):
    transcript = ROOT / "docs" / "operations" / "drills" / "test-transcript.json"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text(
        json.dumps(
            {
                "schema_version": "runbook-drill-transcript-v0",
                "status": "passed",
                "command_id": "cmd_db_backup_status_v0",
                "command": "knudgctl deps check --all",
                "exit_code": 2,
                "output_status": "not_configured",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        data = load_fixture()
        data["commands"][0]["drill_transcript_status"] = "passed"
        data["commands"][0]["drill_transcript_path"] = "docs/operations/drills/test-transcript.json"
        code, payload = run_validator(write_json(tmp_path, data))
        assert code == 3
        assert "transcript does not match manifest row" in payload["blocking_gates"][0]
    finally:
        transcript.unlink(missing_ok=True)
