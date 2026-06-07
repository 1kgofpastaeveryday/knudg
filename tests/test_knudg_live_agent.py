import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ROLE_VERDICT_SCHEMA = ROOT / "schemas" / "knudg-role-verdict-v0.schema.json"


class LiveBackendHandler(BaseHTTPRequestHandler):
    saw_token = False
    seen_task_profiles = []

    def log_message(self, format, *args):
        return

    def _read_json(self):
        length = int(self.headers.get("content-length") or "0")
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def _write_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health/live":
            self._write_json({"status": "live"})
            return
        self._write_json({"status": "not_found"}, status=404)

    def do_POST(self):
        LiveBackendHandler.saw_token = self.headers.get("authorization") == "Bearer live-token"
        payload = self._read_json()
        if self.path == "/v1/private/search":
            assert payload["workspace"] == "agent-smoke"
            LiveBackendHandler.seen_task_profiles.append(payload["task_profile"])
            assert "retrieval_domains" not in payload["task_profile"]
            self._write_json(
                {
                    "status": "ok",
                    "result": {
                        "decision": "cards_found",
                        "delivery_mode": "retrieval_panel",
                        "cards": [
                            {
                                "card_id": "11111111-1111-4111-8111-111111111111",
                                "card_version_id": "22222222-2222-4222-8222-222222222222",
                                "handoff_ref": "local-card:11111111-1111-4111-8111-111111111111:22222222-2222-4222-8222-222222222222",
                                "coarse_match_reason": ["agent-facing"],
                                "match_score": 2,
                            }
                        ],
                    },
                    "publication_enabled": False,
                    "public_search_enabled": False,
                    "vector_search_enabled": False,
                }
            )
            return
        if self.path == "/v1/private/cards:publish":
            self._write_json(
                {
                    "status": "approval_required",
                    "artifact_digest": "sha256:" + "a" * 64,
                    "stored": False,
                    "public_publication_enabled": False,
                },
                status=409,
            )
            return
        if self.path == "/v1/private/final-filter/jobs:stats":
            assert payload == {}
            self._write_json(
                {
                    "status": "final_filter_queue_stats",
                    "stats": {
                        "schema_version": "final-filter-queue-stats-v0",
                        "total_jobs": 1500,
                        "active_depth": 37,
                        "status_counts": {"queued": 31, "leased": 6, "succeeded": 1463, "dead": 0},
                        "ready_queued_jobs": 31,
                        "delayed_queued_jobs": 0,
                        "expired_leases": 0,
                        "candidate_bodies_included": False,
                        "result_bodies_included": False,
                    },
                }
            )
            return
        self._write_json({"status": "not_found"}, status=404)


def serve():
    LiveBackendHandler.saw_token = False
    LiveBackendHandler.seen_task_profiles = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), LiveBackendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def run_knudgctl(*args, env=None):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudgctl.py"), *args],
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def load_knudgctl_module():
    spec = importlib.util.spec_from_file_location("knudgctl_under_test", ROOT / "scripts" / "knudgctl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def role_verdict_validator():
    schema = json.loads(ROLE_VERDICT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def write_pinned_config(path, server_url):
    payload = {
        "schema_version": 1,
        "active_profile": "cloud",
        "profiles": {
            "local": {
                "server_url": server_url,
                "auth_profile": "local",
                "tenant_id": None,
            }
        },
        "pins": {
            "local": {
                "server_url": server_url,
                "server_id": "greencloud-test",
                "deployment_type": "greencloud_closed_launch",
                "api_version": "v1",
                "capabilities_digest": "sha256:" + "b" * 64,
                "capability_resource_origin": server_url,
                "auth_profile": "local",
                "tenant_id": None,
                "pinned_at": "2026-05-30T00:00:00Z",
                "pin_class": "closed_launch_loopback_operator_only",
            }
        },
        "capabilities_cache": {},
        "exploration_depth": "off",
    }
    return write_json(path, payload)


def test_live_search_verdict_marks_empty_search_as_no_actionable_signal():
    knudgctl = load_knudgctl_module()
    verdict = knudgctl.live_search_verdict({"result": {"decision": "no_suggestion", "cards": []}})

    assert verdict["status"] == "no_actionable_signal"
    assert verdict["recommended_action"] == "do_nothing"
    assert "refs" not in verdict
    role_verdict_validator().validate(verdict)


def test_live_profile_build_search_nudge_and_write_candidate(tmp_path):
    builder_input = write_json(
        tmp_path / "builder.json",
        {
            "schema_version": "task-profile-builder-input-v0",
            "intent": "debug",
            "explicit_query": "agent facing orchestration",
            "repo_shape_category": "python-cli",
            "public_packages": ["pypi:pytest"],
            "recent_event_kinds": ["task_start"],
        },
    )
    code, built = run_knudgctl("live", "profile", "build", "--input", str(builder_input), "--with-query-views")
    assert code == 0
    assert built["status"] == "ok"
    assert built["task_profile"]["schema_version"] == "task_profile.v0"
    assert built["profile_digest"].startswith("sha256:")
    assert built["query_views"]

    task_profile = write_json(tmp_path / "task-profile.json", built["task_profile"])
    card = write_json(
        tmp_path / "card.json",
        {
            "source_class": "local_private_dogfood",
            "title": "Agent facing orchestration path",
            "human_summary": {
                "content": "Agent-facing orchestration should use the live backend nudge path.",
                "redaction_summary": "Removed private paths, hostnames, usernames, env values, and raw logs.",
            },
            "problem_summary": "The agent workflow needed a live backend nudge path instead of a fixture-only path.",
            "solution_summary": "Use live profile build, live search, live nudge, and write candidate commands against the pinned backend.",
            "public_packages": ["pytest"],
            "environment_tags": ["windows"],
            "public_reference_urls": ["https://docs.python.org/3/library/json.html"],
            "command_labels": ["live nudge"],
            "error_fingerprints": ["agent-facing-live-nudge"],
            "lessons": ["Keep retrieved cards advisory until independently validated."],
        },
    )

    server = serve()
    env = {"KNUDG_OPERATOR_TOKEN": "live-token"}
    url = f"http://127.0.0.1:{server.server_port}"
    config = write_pinned_config(tmp_path / "client-config.json", url)
    try:
        code, searched = run_knudgctl(
            "live",
            "search",
            "--config",
            str(config),
            "--workspace",
            "agent-smoke",
            "--task-profile",
            str(task_profile),
            env=env,
        )
        assert code == 0
        assert searched["result"]["decision"] == "cards_found"
        assert "live-token" not in json.dumps(searched)

        code, nudged = run_knudgctl(
            "live",
            "nudge",
            "--config",
            str(config),
            "--workspace",
            "agent-smoke",
            "--task-profile",
            str(task_profile),
            env=env,
        )
        assert code == 0
        assert nudged["verdict"]["role"] == "nudger"
        assert nudged["verdict"]["recommended_action"] == "offer_retrieval_panel"
        assert "live-token" not in json.dumps(nudged)
        assert len(LiveBackendHandler.seen_task_profiles) == 2

        code, candidate = run_knudgctl(
            "live",
            "write-candidate",
            "--config",
            str(config),
            "--workspace",
            "agent-smoke",
            "--card",
            str(card),
            env=env,
        )
        assert code == 0
        assert candidate["verdict"]["recommended_action"] == "offer_writer_draft"
        assert candidate["stored"] is False
        assert candidate["public_publication_enabled"] is False
        assert "live-token" not in json.dumps(candidate)

        code, stats = run_knudgctl(
            "live",
            "final-filter",
            "stats",
            "--config",
            str(config),
            env=env,
        )
        assert code == 0
        assert stats["queue_status"] == "final_filter_queue_stats"
        assert stats["stats"]["total_jobs"] == 1500
        assert stats["stats"]["candidate_bodies_included"] is False
        assert stats["stats"]["result_bodies_included"] is False
        assert "live-token" not in json.dumps(stats)
        assert LiveBackendHandler.saw_token is True
    finally:
        server.shutdown()


def test_live_profile_build_accepts_inline_json_input():
    builder_input = {
        "schema_version": "task-profile-builder-input-v0",
        "intent": "debug",
        "explicit_query": "pytest failure investigation",
        "repo_shape_category": "python-cli",
        "public_packages": ["pypi:pytest"],
        "recent_event_kinds": ["task_start", "test_failure"],
    }
    code, built = run_knudgctl("live", "profile", "build", "--input", json.dumps(builder_input))
    assert code == 0
    assert built["status"] == "ok"
    assert built["task_profile"]["explicit_query"] == "pytest failure investigation"


def test_live_search_rejects_non_technical_retrieval_domains_before_backend(tmp_path):
    task_profile = write_json(
        tmp_path / "task-profile.json",
        {
            "schema_version": "task_profile.v0",
            "intent": "debug",
            "explicit_query": "agent facing orchestration",
            "repo_shape_category": "python-cli",
            "retrieval_domains": ["career_private"],
            "recent_event_kinds": ["task_start"],
        },
    )
    server = serve()
    config = write_pinned_config(tmp_path / "client-config.json", f"http://127.0.0.1:{server.server_port}")
    try:
        code, payload = run_knudgctl(
            "live",
            "search",
            "--config",
            str(config),
            "--task-profile",
            str(task_profile),
            env={"KNUDG_OPERATOR_TOKEN": "live-token"},
        )
    finally:
        server.shutdown()
    assert code == 3
    assert payload["status"] == "usage_error"
    assert LiveBackendHandler.seen_task_profiles == []


def test_live_commands_require_pinned_closed_launch_config(tmp_path):
    task_profile = write_json(
        tmp_path / "task-profile.json",
        {
            "schema_version": "task_profile.v0",
            "intent": "debug",
            "explicit_query": "agent facing orchestration",
            "repo_shape_category": "python-cli",
            "recent_event_kinds": ["task_start"],
        },
    )
    config = write_json(
        tmp_path / "client-config.json",
        {
            "schema_version": 1,
            "active_profile": "cloud",
            "profiles": {
                "local": {
                    "server_url": "http://127.0.0.1:65530",
                    "auth_profile": "local",
                    "tenant_id": None,
                }
            },
            "pins": {},
            "capabilities_cache": {},
            "exploration_depth": "off",
        },
    )

    code, payload = run_knudgctl(
        "live",
        "nudge",
        "--config",
        str(config),
        "--task-profile",
        str(task_profile),
        env={"KNUDG_OPERATOR_TOKEN": "live-token"},
    )
    assert code == 3
    assert payload["status"] == "usage_error"
    assert "pinned" in payload["detail"]


def test_live_commands_reject_server_url_override(tmp_path):
    task_profile = write_json(
        tmp_path / "task-profile.json",
        {
            "schema_version": "task_profile.v0",
            "intent": "debug",
            "explicit_query": "agent facing orchestration",
            "repo_shape_category": "python-cli",
            "recent_event_kinds": ["task_start"],
        },
    )
    code, payload = run_knudgctl(
        "live",
        "nudge",
        "--server-url",
        "http://127.0.0.1:8787",
        "--task-profile",
        str(task_profile),
        env={"KNUDG_OPERATOR_TOKEN": "live-token"},
    )
    assert code == 3
    assert payload["status"] == "usage_error"
