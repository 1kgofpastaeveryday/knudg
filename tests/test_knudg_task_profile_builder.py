import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "task-profile-v0.schema.json"


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_valid_profile(payload):
    errors = sorted(validator().iter_errors(payload), key=lambda error: error.path)
    assert errors == []


def builder_input(**overrides):
    payload = {
        "schema_version": "task-profile-builder-input-v0",
        "intent": "debug",
        "explicit_query": "capture closed API setup failure",
        "repo_shape_category": "python-node-closed-api",
        "retrieval_domains": ["technical_work"],
        "subsystems": ["closed-api", "retrieval"],
        "safe_file_refs": ["docs/operations/cloud-closed-launch-runbook.md"],
        "symbols": ["knudgctl", "server.status"],
        "error_fingerprints": ["server-url-missing"],
        "public_packages": ["pypi:jsonschema"],
        "public_frameworks_tools": ["Codex", "pytest"],
        "language_runtime": "python-3.12",
        "coarse_os": "windows",
        "dependency_major_versions": ["pytest:9"],
        "risk_tags": ["correctness"],
        "recent_event_kinds": ["task_start", "tool_failure"],
    }
    payload.update(overrides)
    return payload


def run_builder(tmp_path, payload, *extra_args):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_task_profile.py"),
            "build",
            "--input",
            str(path),
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def test_builder_emits_valid_task_profile(tmp_path):
    code, payload = run_builder(tmp_path, builder_input())
    assert code == 0
    assert payload["schema_version"] == "task_profile.v0"
    assert payload["explicit_query"] == "capture closed API setup failure"
    assert payload["retrieval_domains"] == ["technical_work"]
    assert payload["recent_event_kinds"] == ["task_start", "tool_failure"]
    assert_valid_profile(payload)


def test_builder_deduplicates_arrays_and_omits_empty_optional_fields(tmp_path):
    code, payload = run_builder(
        tmp_path,
        builder_input(
            subsystems=["retrieval", "retrieval", "  closed-api  "],
            safe_file_refs=[],
            symbols=[],
        ),
    )
    assert code == 0
    assert payload["subsystems"] == ["retrieval", "closed-api"]
    assert "safe_file_refs" not in payload
    assert "symbols" not in payload
    assert_valid_profile(payload)


def test_builder_can_emit_bounded_query_views(tmp_path):
    code, payload = run_builder(tmp_path, builder_input(), "--with-query-views")
    assert code == 0
    assert payload["schema_version"] == "task-profile-builder-result-v0"
    assert payload["status"] == "ok"
    assert_valid_profile(payload["task_profile"])
    names = {view["name"] for view in payload["query_views"]}
    assert "exact_identifiers" in names
    assert "structured_filters" in names
    serialized = json.dumps(payload)
    assert "server-url-missing" in serialized
    assert "successful_path" not in serialized


def test_builder_defaults_to_technical_retrieval_domain(tmp_path):
    source = builder_input()
    source.pop("retrieval_domains")
    code, payload = run_builder(tmp_path, source)
    assert code == 0
    assert payload["retrieval_domains"] == ["technical_work"]
    assert_valid_profile(payload)


def test_builder_rejects_non_technical_retrieval_domains(tmp_path):
    code, payload = run_builder(tmp_path, builder_input(retrieval_domains=["career_private"]))
    assert code == 2
    assert payload["reason"] == "input_rejected"


def test_builder_rejects_raw_private_input_without_echoing_it(tmp_path):
    code, payload = run_builder(tmp_path, builder_input(explicit_query="inspect Z:/synthetic/repo"))
    assert code == 2
    assert payload["status"] == "rejected"
    serialized = json.dumps(payload)
    assert "Z:/synthetic" not in serialized


def test_builder_rejects_unknown_fields_and_wrong_schema_version(tmp_path):
    code, payload = run_builder(tmp_path, builder_input(raw_log="Traceback"))
    assert code == 2
    assert payload["reason"] == "input_rejected"
    assert "Traceback" not in json.dumps(payload)

    code, payload = run_builder(tmp_path, builder_input(schema_version="task_profile.v0"))
    assert code == 2
    assert payload["reason"] == "input_rejected"
