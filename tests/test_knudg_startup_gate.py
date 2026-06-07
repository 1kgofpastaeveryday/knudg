import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "plugins" / "knudg" / "hooks" / "knudg_startup_gate.py"
WORKER = ROOT / "plugins" / "knudg" / "hooks" / "knudg_startup_worker.py"


class StartupNudgeHandler(BaseHTTPRequestHandler):
    seen_payloads = []

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
        payload = self._read_json()
        StartupNudgeHandler.seen_payloads.append(payload)
        if self.path == "/v1/private/search":
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
                                "coarse_match_reason": ["startup-gate"],
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
        self._write_json({"status": "not_found"}, status=404)


def serve_startup_nudge():
    StartupNudgeHandler.seen_payloads = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), StartupNudgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


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
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_hook(payload, log_path, env=None):
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={**os.environ, "KNUDG_STARTUP_GATE_LOG": str(log_path), **(env or {})},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def read_log(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def user_prompt(prompt, *, cwd=None):
    return {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "sess_test",
        "turn_id": "turn_test",
        "cwd": str(cwd or ROOT),
        "prompt": prompt,
    }


def test_gate_runs_for_technical_work_in_knudg_workspace(tmp_path):
    log = tmp_path / "gate.jsonl"
    server = serve_startup_nudge()
    config = write_pinned_config(tmp_path / "client-config.json", f"http://127.0.0.1:{server.server_port}")
    try:
        output = run_hook(
            user_prompt("pytestが落ちているので原因調査して"),
            log,
            env={"KNUDG_CONFIG": str(config), "KNUDG_OPERATOR_TOKEN": "test-token"},
        )
    finally:
        server.shutdown()

    hook_output = output["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "UserPromptSubmit"
    assert "Knudg decision check: use Knudg for this turn." in hook_output["additionalContext"]
    assert "Startup preflight worker completed sanitized live nudge" in hook_output["additionalContext"]
    assert "must not be reused as the native sub-agent verdict" in hook_output["additionalContext"]
    assert "References exist, but this is not task progress unless validated and used." in hook_output["additionalContext"]
    assert "Recommended action: offer_retrieval_panel." not in hook_output["additionalContext"]
    assert "Worker spawn: recorded." in hook_output["additionalContext"]
    assert "MANDATORY NATIVE SUB-AGENT" in hook_output["additionalContext"]
    assert "spawn_agent/collaboration tool exactly once now" in hook_output["additionalContext"]
    assert "Use a default spawn with only the delegated prompt/message" in hook_output["additionalContext"]
    assert "omit agent_type, model, reasoning_effort" in hook_output["additionalContext"]
    assert "Do not skip this because the user's task is small" not in hook_output["additionalContext"]
    assert "selected high-retrieval-value class" in hook_output["additionalContext"]
    assert "Sanitized task_profile.v0 for the delegated Knudg sub-agent" in hook_output["additionalContext"]
    assert "KNUDG_SUBAGENT_DELEGATED_V0" in hook_output["additionalContext"]
    assert '"schema_version":"task_profile.v0"' in hook_output["additionalContext"]
    assert '"explicit_query":"investigate technical test or failure context"' in hook_output["additionalContext"]
    assert "pytestが落ちているので原因調査して" not in hook_output["additionalContext"]
    assert "query the configured Knudg live backend itself" in hook_output["additionalContext"]
    assert "must not reuse or copy the startup preflight worker result" in hook_output["additionalContext"]
    assert "knudg_startup_worker.py" in hook_output["additionalContext"]
    assert "return only compact fields" in hook_output["additionalContext"]
    assert "`backend_query` should be `live_nudge`" in hook_output["additionalContext"]
    assert "`crawl_status` should be `searched` only when the delegated" in hook_output["additionalContext"]
    assert "pending_init" in hook_output["additionalContext"]
    assert "Do not close a delegated sub-agent while its status is still running" in hook_output["additionalContext"]
    assert "reaches a terminal status, record its compact verdict and close" in hook_output["additionalContext"]
    assert "does not consume the thread limit" in hook_output["additionalContext"]
    assert "Close only this bounded Knudg live-nudge sub-agent" in hook_output["additionalContext"]
    assert "do not claim a native sub-agent ran" in hook_output["additionalContext"]

    records = read_log(log)
    assert records[-1]["decision"] == "run"
    assert records[-1]["reason"] == "technical_work_in_knudg_workspace"
    assert records[-1]["worker_spawned"] is True
    assert records[-1]["worker_role"] == "knudg_startup_subagent"
    assert isinstance(records[-1]["worker_pid"], int)
    assert records[-1]["backend_query"] == "live_nudge"
    assert records[-1]["crawl_status"] == "searched"
    assert records[-1]["nudge_status"] == "suggestion_available"
    assert records[-1]["nudge_recommended_action"] == "offer_retrieval_panel"
    assert records[-1]["prompt_chars"] > 0
    assert "pytest" not in json.dumps(records[-1], ensure_ascii=False)
    assert len(StartupNudgeHandler.seen_payloads) == 1
    task_profile = StartupNudgeHandler.seen_payloads[0]["task_profile"]
    assert task_profile["explicit_query"] == "investigate technical test or failure context"
    assert "pytestが落ちているので原因調査して" not in json.dumps(task_profile, ensure_ascii=False)
    assert "retrieval_domains" not in task_profile


def test_gate_reports_active_nudge_unavailable_without_blocking(tmp_path):
    log = tmp_path / "gate.jsonl"
    output = run_hook(user_prompt("hookの挙動を調査して"), log, env={"KNUDG_CONFIG": str(tmp_path / "missing.json")})

    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Summoned Knudg sub-agent worker could not complete sanitized live nudge" in context
    record = read_log(log)[-1]
    assert record["decision"] == "run"
    assert record["worker_spawned"] is True
    assert record["worker_role"] == "knudg_startup_subagent"
    assert record["nudge_status"] == "unavailable"


def test_worker_rejects_invalid_profile_without_echoing_input():
    result = subprocess.run(
        [sys.executable, str(WORKER)],
        cwd=ROOT,
        input=json.dumps({"schema_version": "bad", "raw": "pytest failed"}),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["role"] == "knudg_startup_subagent"
    assert payload["status"] == "unavailable"
    assert payload["error_class"] == "invalid_task_profile"
    assert "pytest failed" not in result.stdout


def test_gate_skips_trivial_prompt_without_context_noise(tmp_path):
    log = tmp_path / "gate.jsonl"
    output = run_hook(user_prompt("ありがとう"), log)

    hook_output = output["hookSpecificOutput"]
    assert hook_output == {"hookEventName": "UserPromptSubmit"}
    assert read_log(log)[-1]["decision"] == "skip"


def test_gate_skips_small_text_edit_without_context_noise(tmp_path):
    log = tmp_path / "gate.jsonl"
    output = run_hook(user_prompt("docs/operations/foo.md の文言を少し調整して"), log)

    hook_output = output["hookSpecificOutput"]
    assert hook_output == {"hookEventName": "UserPromptSubmit"}
    record = read_log(log)[-1]
    assert record["decision"] == "skip"
    assert record["reason"] == "small_text_edit_low_retrieval_value"
    assert "worker_spawned" not in record


def test_gate_still_runs_for_policy_docs_alignment(tmp_path):
    log = tmp_path / "gate.jsonl"
    output = run_hook(
        user_prompt("複数文書のポリシー整合を確認して docs を修正して"),
        log,
        env={"KNUDG_STARTUP_GATE_DISABLE_NUDGE": "1"},
    )

    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Knudg decision check: use Knudg for this turn." in context
    record = read_log(log)[-1]
    assert record["decision"] == "run"
    assert record["reason"] == "technical_work_in_knudg_workspace"


def test_gate_skips_delegated_subagent_marker_without_worker(tmp_path):
    log = tmp_path / "gate.jsonl"
    output = run_hook(user_prompt("KNUDG_SUBAGENT_DELEGATED_V0 inspect package metadata"), log)

    assert output["hookSpecificOutput"] == {"hookEventName": "UserPromptSubmit"}
    record = read_log(log)[-1]
    assert record["decision"] == "skip"
    assert record["reason"] == "delegated_knudg_subagent"
    assert "worker_spawned" not in record


def test_gate_asks_before_raw_or_sensitive_material(tmp_path):
    log = tmp_path / "gate.jsonl"
    output = run_hook(user_prompt("raw logsを使って原因調査して"), log)

    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Knudg decision check: ask before using Knudg for this turn." in context
    assert "Do not send raw or sensitive material" in context
    assert read_log(log)[-1]["decision"] == "ask"


def test_gate_skips_outside_knudg_scope(tmp_path):
    log = tmp_path / "gate.jsonl"
    outside_cwd = ROOT.parent / "outside-knudg-test-workspace"
    output = run_hook(user_prompt("pytestが落ちているので原因調査して", cwd=outside_cwd), log)

    assert output["hookSpecificOutput"] == {"hookEventName": "UserPromptSubmit"}
    record = read_log(log)[-1]
    assert record["decision"] == "skip"
    assert record["reason"] == "outside_knudg_scope"


def test_gate_suppresses_duplicate_context_for_same_prompt(tmp_path):
    log = tmp_path / "gate.jsonl"
    payload = user_prompt("pytestが落ちているので原因調査して")

    first = run_hook(payload, log)
    second = run_hook(payload, log)

    assert "additionalContext" in first["hookSpecificOutput"]
    assert second["hookSpecificOutput"] == {"hookEventName": "UserPromptSubmit"}
    assert len(read_log(log)) == 1


def test_hook_manifest_registers_only_decision_gate():
    hooks = json.loads((ROOT / "plugins" / "knudg" / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"UserPromptSubmit"}
    handler = hooks["UserPromptSubmit"][0]["hooks"][0]
    assert handler["type"] == "command"
    assert "knudg_startup_gate.py" in handler["command"]
    assert "knudgctl" not in handler["command"]
    assert handler["timeout"] <= 10


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_text(path, payload):
    path.write_text(payload, encoding="utf-8")
    return path


def run_diagnose(config, global_hooks, plugin_hooks):
    result = subprocess.run(
        [
            sys.executable,
            str(HOOK),
            "--diagnose-install",
            "--config",
            str(config),
            "--global-hooks",
            str(global_hooks),
            "--plugin-hooks",
            str(plugin_hooks),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def plugin_hooks_manifest():
    return {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python \"plugins/knudg/hooks/knudg_startup_gate.py\"",
                        }
                    ]
                }
            ]
        }
    }


def test_diagnose_install_detects_legacy_global_duplicate(tmp_path):
    config = write_text(
        tmp_path / "config.toml",
        '[plugins."knudg@knudg-local"]\nenabled = true\n',
    )
    global_hooks = write_json(
        tmp_path / "hooks.json",
        {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python \"repo/plugins/knudg/hooks/knudg_startup_gate.py\"",
                            }
                        ]
                    }
                ]
            }
        },
    )
    plugin_hooks = write_json(tmp_path / "plugin-hooks.json", plugin_hooks_manifest())

    code, payload = run_diagnose(config, global_hooks, plugin_hooks)

    assert code == 3
    assert payload["status"] == "duplicate_registration"
    assert payload["global_knudg_hook_present"] is True
    assert payload["plugin_knudg_hook_present"] is True
    assert payload["plugin_enabled"] is True
    assert "Remove the legacy global" in payload["remediation"]
    assert "repo/plugins" not in json.dumps(payload)


def test_diagnose_install_accepts_plugin_only_registration(tmp_path):
    config = write_text(
        tmp_path / "config.toml",
        '[plugins."knudg@knudg-local"]\nenabled = true\n',
    )
    global_hooks = write_json(tmp_path / "hooks.json", {"hooks": {}})
    plugin_hooks = write_json(tmp_path / "plugin-hooks.json", plugin_hooks_manifest())

    code, payload = run_diagnose(config, global_hooks, plugin_hooks)

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["global_knudg_hook_present"] is False
    assert payload["plugin_knudg_hook_present"] is True
    assert payload["plugin_enabled"] is True
