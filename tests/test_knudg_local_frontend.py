import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]


class UpstreamHandler(BaseHTTPRequestHandler):
    token_seen = False
    expected_token = "test-token"
    approved_digest_seen = None
    publish_requests = 0
    force_store_on_stage = False

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
        if self.path == "/health/ready":
            self._write_json({"status": "ready"})
            return
        self._write_json({"status": "not_found"}, status=404)

    def do_POST(self):
        UpstreamHandler.token_seen = self.headers.get("authorization") == f"Bearer {UpstreamHandler.expected_token}"
        payload = self._read_json()
        if self.path == "/v1/private/cards:publish":
            UpstreamHandler.publish_requests += 1
            digest = self.headers.get("x-knudg-artifact-digest")
            UpstreamHandler.approved_digest_seen = digest
            if UpstreamHandler.force_store_on_stage and not digest:
                self._write_json({"status": "private_published", "stored": True}, status=201)
                return
            if not digest:
                self._write_json({"status": "approval_required", "artifact_digest": "sha256:test"}, status=409)
                return
            self._write_json({"status": "private_published", "card_id": "11111111-1111-4111-8111-111111111111"}, status=201)
            return
        if self.path == "/v1/private/search":
            self._write_json(
                {
                    "status": "ok",
                    "result": {
                        "decision": "cards_found",
                        "cards": [
                            {
                                "card_id": "11111111-1111-4111-8111-111111111111",
                                "coarse_match_reason": ["operator-frontend-smoke"],
                            }
                        ],
                    },
                    "echo_workspace": payload.get("workspace"),
                }
            )
            return
        if self.path == "/v1/private/cards/11111111-1111-4111-8111-111111111111:view":
            self._write_json({"status": "private_card", "card": {"title": "Viewed card"}})
            return
        self._write_json({"status": "not_found"}, status=404)


def serve_upstream():
    UpstreamHandler.token_seen = False
    UpstreamHandler.expected_token = "test-token"
    UpstreamHandler.approved_digest_seen = None
    UpstreamHandler.publish_requests = 0
    UpstreamHandler.force_store_on_stage = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def read_startup_line(process, timeout_seconds=5):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            return json.loads(line)
    raise AssertionError("local frontend did not print a startup line")


def post_json(url, payload, headers=None):
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def get_json(url, headers=None):
    req = request.Request(url, headers=headers or {}, method="GET")
    with request.urlopen(req, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def get_json_or_error(url, headers=None):
    req = request.Request(url, headers=headers or {}, method="GET")
    try:
        with request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_local_frontend_stages_write_search_and_view_without_browser_token():
    upstream = serve_upstream()
    env = {
        **os.environ,
        "KNUDG_OPERATOR_TOKEN": "test-token",
        "KNUDG_FRONTEND_API_BASE_URL": f"http://127.0.0.1:{upstream.server_port}",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_local_frontend.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = startup["url"]

        with request.urlopen(f"{base_url}/api/status", timeout=5) as response:
            status = json.loads(response.read().decode("utf-8"))
        assert status["status"] == "ready"

        code, approval = post_json(f"{base_url}/api/cards:publish", {"workspace": "closed-beta-test", "card": {}})
        assert code == 409
        assert approval["artifact_digest"] == "sha256:test"

        code, completion = post_json(
            f"{base_url}/api/cards:publish",
            {"workspace": "closed-beta-test", "card": {}, "approved_digest": "sha256:test"},
        )
        assert code == 409
        assert completion["status"] == "completion_disabled"
        assert UpstreamHandler.token_seen is True
        assert UpstreamHandler.approved_digest_seen is None
        assert UpstreamHandler.publish_requests == 1

        code, searched = post_json(f"{base_url}/api/search", {"workspace": "closed-beta-test", "task_profile": {}})
        assert code == 200
        assert searched["result"]["cards"][0]["coarse_match_reason"] == ["operator-frontend-smoke"]

        code, viewed = post_json(f"{base_url}/api/cards/11111111-1111-4111-8111-111111111111:view", {"workspace": "closed-beta-test"})
        assert code == 200
        assert viewed["card"]["title"] == "Viewed card"
    finally:
        stop_process(process)
        upstream.shutdown()


def test_local_frontend_requires_explicit_token_for_private_proxy_when_env_token_absent():
    upstream = serve_upstream()
    env = {**os.environ}
    env.pop("KNUDG_OPERATOR_TOKEN", None)
    env.pop("KNUDG_FRONTEND_TOKEN", None)
    env["KNUDG_FRONTEND_API_BASE_URL"] = f"http://127.0.0.1:{upstream.server_port}"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_local_frontend.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        code, searched = post_json(f"{startup['url']}/api/search", {"workspace": "closed-beta-test", "task_profile": {}})

        assert code == 503
        assert searched["status"] == "operator_token_required"
        assert UpstreamHandler.token_seen is False
    finally:
        stop_process(process)
        upstream.shutdown()


def test_local_frontend_can_require_tailscale_identity_headers():
    upstream = serve_upstream()
    env = {
        **os.environ,
        "KNUDG_OPERATOR_TOKEN": "test-token",
        "KNUDG_OPERATOR_REQUIRE_TAILSCALE": "1",
        "KNUDG_OPERATOR_TAILSCALE_ALLOWED_USERS": "operator@example.com",
        "KNUDG_FRONTEND_API_BASE_URL": f"http://127.0.0.1:{upstream.server_port}",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_local_frontend.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        assert startup["tailscale_required"] is True
        assert startup["tailscale_allowed_user_count"] == 1

        code, rejected = get_json_or_error(f"{startup['url']}/api/status")
        assert code == 403
        assert rejected["reject_class"] == "tailscale_required"

        code, rejected_user = get_json_or_error(
            f"{startup['url']}/api/status",
            headers={"Tailscale-User-Login": "other@example.com"},
        )
        assert code == 403
        assert rejected_user["reject_class"] == "tailscale_user_not_allowed"

        code, status = get_json_or_error(
            f"{startup['url']}/api/status",
            headers={"Tailscale-User-Login": "operator@example.com"},
        )
        assert code == 200
        assert status["status"] == "ready"
    finally:
        stop_process(process)
        upstream.shutdown()


def test_local_frontend_fails_closed_when_stage_writes_upstream():
    upstream = serve_upstream()
    UpstreamHandler.force_store_on_stage = True
    env = {
        **os.environ,
        "KNUDG_OPERATOR_TOKEN": "test-token",
        "KNUDG_FRONTEND_API_BASE_URL": f"http://127.0.0.1:{upstream.server_port}",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_local_frontend.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        code, rejected = post_json(f"{startup['url']}/api/cards:publish", {"workspace": "closed-beta-test", "card": {}})

        assert code == 502
        assert rejected["status"] == "rejected"
        assert rejected["upstream_status"] == 201
    finally:
        stop_process(process)
        upstream.shutdown()
