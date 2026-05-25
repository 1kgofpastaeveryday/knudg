import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from tests.test_knudg_synthetic_retrieval import corpus_payload, request_payload
from tests.test_task_profile_schema import rich_profile
from tests.test_knudg_writer import draft_payload


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "knudg-role-verdict-v0.schema.json"


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_valid(payload):
    errors = sorted(validator().iter_errors(payload), key=lambda error: error.path)
    assert errors == []


def assert_invalid(payload):
    assert list(validator().iter_errors(payload))


def run_role(*args):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudg_roles.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def write_json(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_schema_accepts_minimal_abstain_and_rejects_extra_body_fields():
    payload = {
        "schema_version": "knudg_role_verdict.v0",
        "role": "nudger",
        "status": "abstain",
        "confidence": "none",
        "risk": "none",
        "reason_summary": "No useful low-noise suggestion.",
        "recommended_action": "do_nothing",
    }
    assert_valid(payload)

    payload["raw_card_body"] = "must not be present"
    assert_invalid(payload)


def test_schema_rejects_executable_or_private_summary_and_refs():
    payload = {
        "schema_version": "knudg_role_verdict.v0",
        "role": "searcher",
        "status": "suggestion_available",
        "confidence": "medium",
        "risk": "low",
        "reason_summary": "Run npm install package",
        "recommended_action": "offer_retrieval_panel",
        "refs": {"card_refs": ["card_001:version_001"]},
    }
    assert_invalid(payload)

    payload["reason_summary"] = "Displayable retrieval-panel metadata is available."
    payload["refs"]["card_refs"] = ["C:\\Users\\4\\private"]
    assert_invalid(payload)


def test_searcher_wrapper_returns_compact_valid_verdict(tmp_path):
    request_path = write_json(tmp_path, "request.json", request_payload())
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload())
    code, payload = run_role("searcher-synthetic", "--input", str(request_path), "--corpus", str(corpus_path))
    assert code == 0
    assert_valid(payload)
    assert payload["role"] == "searcher"
    assert payload["status"] == "suggestion_available"
    assert payload["recommended_action"] == "offer_retrieval_panel"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "set local profile" not in serialized


def test_searcher_wrapper_abstains_when_no_match(tmp_path):
    request_path = write_json(tmp_path, "request.json", request_payload())
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload(tenant_id="tenant_other"))
    code, payload = run_role("searcher-synthetic", "--input", str(request_path), "--corpus", str(corpus_path))
    assert code == 0
    assert_valid(payload)
    assert payload["status"] == "abstain"
    assert payload["recommended_action"] == "do_nothing"


def test_writer_wrapper_returns_compact_valid_draft_verdict(tmp_path):
    draft_path = write_json(tmp_path, "draft.json", draft_payload())
    code, payload = run_role("writer-local", "--input", str(draft_path))
    assert code == 0
    assert_valid(payload)
    assert payload["role"] == "writer"
    assert payload["status"] == "draft_candidate_possible"
    assert payload["recommended_action"] == "offer_writer_draft"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "pin server capabilities" not in serialized


def test_writer_wrapper_degrades_without_echoing_raw_input(tmp_path):
    draft = draft_payload(goal="fix C:\\Users\\4\\private\\repo")
    draft_path = write_json(tmp_path, "draft.json", draft)
    code, payload = run_role("writer-local", "--input", str(draft_path))
    assert code == 2
    assert_valid(payload)
    assert payload["status"] == "degraded"
    assert "C:\\Users" not in json.dumps(payload)


def test_nudger_passes_only_low_noise_offers(tmp_path):
    request_path = write_json(tmp_path, "request.json", request_payload())
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload())
    code, searcher = run_role("searcher-synthetic", "--input", str(request_path), "--corpus", str(corpus_path))
    assert code == 0
    searcher_path = write_json(tmp_path, "searcher.json", searcher)

    code, nudge = run_role("nudger-from-verdict", "--input", str(searcher_path))
    assert code == 0
    assert_valid(nudge)
    assert nudge["role"] == "nudger"
    assert nudge["recommended_action"] == "offer_retrieval_panel"

    searcher["risk"] = "high"
    searcher["suppressed_detail"] = "high_risk"
    risky_path = write_json(tmp_path, "risky.json", searcher)
    code, nudge = run_role("nudger-from-verdict", "--input", str(risky_path))
    assert code == 0
    assert_valid(nudge)
    assert nudge["status"] == "abstain"
    assert nudge["recommended_action"] == "do_nothing"


def test_composed_searcher_nudge_returns_final_nudger_verdict(tmp_path):
    request_path = write_json(tmp_path, "request.json", request_payload())
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload())
    code, payload = run_role("searcher-nudge-synthetic", "--input", str(request_path), "--corpus", str(corpus_path))
    assert code == 0
    assert_valid(payload)
    assert payload["role"] == "nudger"
    assert payload["recommended_action"] == "offer_retrieval_panel"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "set local profile" not in serialized


def test_task_profile_searcher_wrapper_returns_compact_verdict(tmp_path):
    task_profile = rich_profile()
    task_profile["explicit_query"] = "capture local server setup failure"
    task_profile["repo_shape_category"] = "python-node-local-plugin"
    task_profile["symbols"] = ["knudgctl"]
    task_profile["public_frameworks_tools"] = ["Codex"]
    task_profile_path = write_json(tmp_path, "task-profile.json", task_profile)
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload())

    code, payload = run_role(
        "searcher-profile-synthetic",
        "--input",
        str(task_profile_path),
        "--corpus",
        str(corpus_path),
        "--min-score",
        "2",
    )
    assert code == 0
    assert_valid(payload)
    assert payload["role"] == "searcher"
    assert payload["recommended_action"] == "offer_retrieval_panel"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "set local profile" not in serialized


def test_task_profile_searcher_wrapper_degrades_without_echoing_raw_input(tmp_path):
    task_profile = rich_profile()
    task_profile["explicit_query"] = "inspect C:\\Users\\4\\private\\repo"
    task_profile_path = write_json(tmp_path, "task-profile.json", task_profile)
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload())

    code, payload = run_role("searcher-profile-synthetic", "--input", str(task_profile_path), "--corpus", str(corpus_path))
    assert code == 2
    assert_valid(payload)
    serialized = json.dumps(payload)
    assert "C:\\Users" not in serialized
    assert "private\\repo" not in serialized


def test_composed_task_profile_searcher_nudge_returns_final_nudger_verdict(tmp_path):
    task_profile = rich_profile()
    task_profile["explicit_query"] = "capture local server setup failure"
    task_profile["repo_shape_category"] = "python-node-local-plugin"
    task_profile_path = write_json(tmp_path, "task-profile.json", task_profile)
    corpus_path = write_json(tmp_path, "corpus.json", corpus_payload())

    code, payload = run_role("searcher-profile-nudge-synthetic", "--input", str(task_profile_path), "--corpus", str(corpus_path))
    assert code == 0
    assert_valid(payload)
    assert payload["role"] == "nudger"
    assert payload["recommended_action"] == "offer_retrieval_panel"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "set local profile" not in serialized


def test_composed_writer_nudge_returns_final_nudger_verdict(tmp_path):
    draft_path = write_json(tmp_path, "draft.json", draft_payload())
    code, payload = run_role("writer-nudge-local", "--input", str(draft_path))
    assert code == 0
    assert_valid(payload)
    assert payload["role"] == "nudger"
    assert payload["recommended_action"] == "offer_writer_draft"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "pin server capabilities" not in serialized


def test_local_dogfood_command_returns_compact_nudger_verdict_and_refs(tmp_path):
    draft_path = write_json(tmp_path, "draft.json", draft_payload())
    task_profile = rich_profile()
    task_profile["explicit_query"] = "capture local server setup failure"
    task_profile["repo_shape_category"] = "python-node-local-plugin"
    task_profile["symbols"] = ["knudgctl"]
    task_profile["public_frameworks_tools"] = ["Codex"]
    task_profile_path = write_json(tmp_path, "task-profile.json", task_profile)

    code, payload = run_role(
        "local-dogfood",
        "--draft-input",
        str(draft_path),
        "--task-profile-input",
        str(task_profile_path),
    )
    assert code == 0
    assert payload["schema_version"] == "local-dogfood-result-v0"
    assert payload["stored"] is False
    assert payload["protected_data_serving_enabled"] is False
    assert payload["publication_enabled"] is False
    assert payload["refs"]["card_ref"] == "card_001:version_001"
    assert payload["refs"]["corpus_ref"].startswith("synthetic-corpus:")
    assert_valid(payload["role_verdict"])
    assert payload["role_verdict"]["role"] == "nudger"
    assert payload["role_verdict"]["recommended_action"] == "offer_retrieval_panel"
    serialized = json.dumps(payload)
    assert "successful_path" not in serialized
    assert "pin server capabilities" not in serialized


def test_local_dogfood_degrades_without_echoing_raw_input(tmp_path):
    draft_path = write_json(tmp_path, "draft.json", draft_payload(goal="fix C:\\Users\\4\\private\\repo"))
    task_profile_path = write_json(tmp_path, "task-profile.json", rich_profile())

    code, payload = run_role(
        "local-dogfood",
        "--draft-input",
        str(draft_path),
        "--task-profile-input",
        str(task_profile_path),
    )
    assert code == 2
    assert_valid(payload)
    assert payload["role"] == "nudger"
    assert payload["status"] == "degraded"
    assert "C:\\Users" not in json.dumps(payload)
