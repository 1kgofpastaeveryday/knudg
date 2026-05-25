import json
import ast
import shutil
import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_retrieval(tmp_path, command, payload):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudg_retrieval.py"), command, "--input", str(input_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def private_profile():
    return {
        "schema_version": "search-profile-v0",
        "request_id": "req_20260514_000001",
        "tenant_scope": "team",
        "namespace_ids": ["ns_opaque_000001"],
        "delivery_mode_requested": "retrieval_panel",
        "goal_category": "debug_build_failure",
        "sanitized_error_signature": "npm-econnreset",
        "public_packages_claimed": ["npm:example-pkg"],
        "public_frameworks_tools_claimed": ["pytest"],
        "language_runtime": "python-3.12",
        "coarse_os": "windows",
        "dependency_major_versions": ["pytest:9"],
        "repo_shape_category": "python-postgres",
        "risk_flags_claimed": [],
        "latency_budget_ms": 250,
        "privacy_budget_class_claimed": "private_team",
    }


def public_request():
    return {
        "schema_version": "public-search-v0",
        "request_id": "req_public_000001",
        "goal_category": "debug_build_failure",
        "public_package_family": "npm",
        "coarse_os": "windows",
        "language_runtime": "node-20",
        "bounded_public_error_category": "network-install-failure",
        "delivery_mode_requested": "retrieval_panel",
    }


def test_private_search_abstains_without_candidate_generation(tmp_path):
    code, payload = run_retrieval(tmp_path, "search-similar", private_profile())
    assert code == 0
    assert payload == {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": "service_degraded",
        "consent_state": "withheld",
        "served_from": "none",
        "latency_budget_ms": 250,
        "cards": [],
    }


def test_private_search_rejects_raw_fields_and_unknown_fields(tmp_path):
    profile = private_profile()
    profile["raw_log"] = "Traceback with private data"
    code, payload = run_retrieval(tmp_path, "search-similar", profile)
    assert code == 2
    assert payload["abstention_reason"] == "payload_rejected"
    assert payload["cards"] == []

    profile = private_profile()
    profile["private_repo_name"] = "customer-repo"
    code, payload = run_retrieval(tmp_path, "search-similar", profile)
    assert code == 2
    assert "customer-repo" not in json.dumps(payload)

    profile = private_profile()
    profile["https://github.com/private/repo"] = "x"
    code, payload = run_retrieval(tmp_path, "search-similar", profile)
    assert code == 2
    assert "github.com" not in json.dumps(payload)
    assert "private/repo" not in json.dumps(payload)


def test_public_search_rejects_authenticated_scope_and_keeps_public_abstention_generic(tmp_path):
    request = public_request()
    code, payload = run_retrieval(tmp_path, "public-search", request)
    assert code == 0
    assert payload == {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": "generic_abstention",
        "threshold_version": "public-threshold-unconfigured",
        "served_from": "none",
        "latency_budget_ms": None,
        "cards": [],
    }

    request["namespace_ids"] = ["ns_opaque_000001"]
    code, payload = run_retrieval(tmp_path, "public-search", request)
    assert code == 0
    assert payload == {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": "generic_abstention",
        "threshold_version": "public-threshold-unconfigured",
        "served_from": "none",
        "latency_budget_ms": None,
        "cards": [],
    }


def test_public_search_forbidden_selectors_are_indistinguishable(tmp_path):
    expected = {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": "generic_abstention",
        "threshold_version": "public-threshold-unconfigured",
        "served_from": "none",
        "latency_budget_ms": None,
        "cards": [],
    }
    for selector, value in {
        "tenant_scope": "team",
        "namespace_ids": ["ns_opaque_000001"],
        "card_id": "card_opaque_000001",
        "card_version_id": "version_opaque_000001",
        "internal_card_id": "internal_opaque_000001",
        "fingerprint": "fp_opaque_000001",
    }.items():
        request = public_request()
        request[selector] = value
        code, payload = run_retrieval(tmp_path, "public-search", request)
        assert code == 0
        assert payload == expected
        assert selector not in json.dumps(payload)


def test_public_search_raw_values_are_generic_abstention(tmp_path):
    request = public_request()
    request["bounded_public_error_category"] = "https://github.com/private/repo/issues/1"
    code, payload = run_retrieval(tmp_path, "public-search", request)
    assert code == 0
    assert payload["abstention_reason"] == "generic_abstention"
    assert "github.com" not in json.dumps(payload)
    assert "private/repo" not in json.dumps(payload)


def test_mcp_tools_list_and_search_call_abstain(tmp_path):
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    code, payload = run_retrieval(tmp_path, "mcp-once", request)
    assert code == 0
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == 1
    assert payload["result"]["tools"][0]["name"] == "search_similar"
    schema = payload["result"]["tools"][0]["inputSchema"]
    assert schema["additionalProperties"] is False
    assert "tenant_scope" in schema["required"]
    assert "server_url" not in schema["properties"]

    request = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {"name": "search_similar", "arguments": private_profile()},
    }
    code, payload = run_retrieval(tmp_path, "mcp-once", request)
    assert code == 0
    result = json.loads(payload["result"]["content"][0]["text"])
    assert result["decision"] == "no_suggestion"
    assert result["cards"] == []
    assert "server_url" not in json.dumps(payload)


def test_mcp_notification_has_no_response_and_ignores_server_env(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"jsonrpc": "2.0", "method": "tools/list"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudg_retrieval.py"), "mcp-once", "--input", str(input_path)],
        cwd=ROOT,
        env={**os.environ, "KNUDG_SERVER_URL": "http://evil.example"},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_mcp_invalid_method_uses_json_rpc_error(tmp_path):
    code, payload = run_retrieval(tmp_path, "mcp-once", {"jsonrpc": "2.0", "id": "x", "method": "unknown"})
    assert code == 0
    assert payload == {
        "jsonrpc": "2.0",
        "id": "x",
        "error": {"code": -32601, "message": "Method not found"},
    }


def test_retrieval_skeleton_has_no_db_or_sql_access():
    path = ROOT / "scripts" / "knudg_retrieval.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
    assert imported_modules <= {"argparse", "json", "re", "sys", "pathlib"}

    forbidden = ["psycopg", "sqlite", "sqlalchemy", "select ", "insert ", "update ", "delete ", "from jobs", "from experience_cards"]
    lowered = source.lower()
    for term in forbidden:
        assert term not in lowered


def test_retrieval_skeleton_npm_wrapper_help():
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    assert npm is not None
    result = subprocess.run(
        [npm, "run", "retrieval:skeleton", "--", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "Knudg retrieval/API/MCP abstention skeleton" in result.stdout
