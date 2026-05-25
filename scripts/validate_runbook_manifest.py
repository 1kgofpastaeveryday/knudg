#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "runbook-command-manifest.schema.json"
TRANSCRIPT_SCHEMA_PATH = ROOT / "schemas" / "runbook-drill-transcript.schema.json"
REQUIRED_RUNBOOKS = {"RB-001", "RB-002", "RB-003", "RB-004", "RB-005", "RB-006", "RB-007", "RB-008"}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def manifest_failures(data):
    failures = []
    transcript_schema = load_json(TRANSCRIPT_SCHEMA_PATH)
    ids = [row["command_id"] for row in data["commands"]]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    if duplicate_ids:
        failures.append(f"duplicate command IDs: {', '.join(duplicate_ids)}")
    covered = {row["runbook_id"] for row in data["commands"]}
    missing = sorted(REQUIRED_RUNBOOKS - covered)
    if missing:
        failures.append(f"missing runbook command coverage: {', '.join(missing)}")
    for row in data["commands"]:
        if row["drill_transcript_status"] in {"attached", "passed"}:
            transcript = row["drill_transcript_path"]
            transcript_path = ROOT / transcript if transcript else None
            if not transcript_path or not transcript_path.exists():
                failures.append(f"{row['command_id']} transcript status requires existing transcript path")
            else:
                try:
                    transcript_data = load_json(transcript_path)
                    errors = list(Draft202012Validator(transcript_schema).iter_errors(transcript_data))
                except json.JSONDecodeError:
                    failures.append(f"{row['command_id']} transcript must be valid JSON")
                    errors = []
                    transcript_data = {}
                if errors:
                    failures.append(f"{row['command_id']} transcript schema invalid")
                elif (
                    transcript_data.get("command_id") != row["command_id"]
                    or transcript_data.get("command") != row["command"]
                    or transcript_data.get("exit_code") not in row["stable_exit_codes"]
                ):
                    failures.append(f"{row['command_id']} transcript does not match manifest row")
                elif row["drill_transcript_status"] == "passed" and transcript_data.get("status") != "passed":
                    failures.append(f"{row['command_id']} passed transcript status requires transcript status passed")
        if row["drill_transcript_status"] == "missing" and row["drill_transcript_path"] is not None:
            failures.append(f"{row['command_id']} missing transcript must not name a path")
        if row["mutation_guard"] == "dry_run_or_apply_required" and "--dry-run" not in row["command"] and "--apply" not in row["command"]:
            failures.append(f"{row['command_id']} guarded mutation command must include --dry-run or --apply")
        if row["dry_run_behavior"] == "required_for_mutation" and "--dry-run" not in row["command"]:
            failures.append(f"{row['command_id']} mutation command must include --dry-run in draft manifest")
        if not row["command"].startswith("knudgctl "):
            failures.append(f"{row['command_id']} command must use knudgctl")
    if data["status"] == "drill_passed":
        not_passed = [row["command_id"] for row in data["commands"] if row["drill_transcript_status"] != "passed"]
        if not_passed:
            failures.append(f"drill_passed manifest requires passed transcripts: {', '.join(not_passed)}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate runbook command manifest scaffold.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        print(json.dumps({"status": "rejected", "errors": [error.message for error in errors]}, sort_keys=True))
        return 2
    failures = manifest_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    print(json.dumps({"status": "ok", "command_count": len(data["commands"]), "drill_passed": data["status"] == "drill_passed"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
