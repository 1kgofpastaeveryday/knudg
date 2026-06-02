import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalKnudgHandler(BaseHTTPRequestHandler):
    server_id = "local-dev"
    deployment_type = "local"
    search_route = "disabled"

    def log_message(self, format, *args):
        return

    def _write_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in {"/health/startup", "/health/ready"}:
            self._write_json(
                {
                    "status": "ready",
                    "deployment_type": self.deployment_type,
                    "components": {
                        "postgres": "not_configured",
                        "migration": "not_configured",
                        "auth_policy": "disabled",
                        "revocation_epoch": "not_configured",
                        "synthetic_retrieval": "ready",
                        "active_index_manifest": "disabled",
                        "publication": "disabled",
                    },
                    "route_classes": {
                        "search": self.search_route,
                        "synthetic-retrieval": "synthetic_only",
                        "card-read": "disabled",
                        "submit/write": "disabled",
                        "trusted-consent-revocation": "disabled",
                        "reviewer-admin": "disabled",
                        "worker-lane": "disabled",
                        "landing": "disabled",
                    },
                }
            )
            return
        if self.path == "/capabilities":
            origin = f"http://localhost:{self.server.server_port}"
            self._write_json(
                {
                    "schema_version": 1,
                    "server_id": self.server_id,
                    "deployment_type": self.deployment_type,
                    "api_version": "v1",
                    "capability_resource_origin": origin,
                    "features": {
                        "search": False,
                        "synthetic_retrieval": True,
                        "protected_retrieval": False,
                        "publication": False,
                    },
                    "policy_versions": {
                        "privacy": "local-dev-v1",
                        "consent": "disabled-local-dev-v1",
                    },
                    "auth": {
                        "profile": "local",
                        "protected_resource_metadata_url": None,
                    },
                }
            )
            return
        self._write_json({"status": "not_found"}, status=404)


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


def test_config_commands_do_not_import_db_driver(tmp_path):
    config = tmp_path / "client-config.json"
    blocker = tmp_path / "block_psycopg"
    blocker.mkdir()
    (blocker / "sitecustomize.py").write_text(
        """
import importlib.abc
import sys


class BlockPsycopg(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "psycopg" or fullname.startswith("psycopg."):
            raise ModuleNotFoundError("blocked psycopg for non-db command test")
        return None


sys.meta_path.insert(0, BlockPsycopg())
""",
        encoding="utf-8",
    )
    code, payload = run_knudgctl(
        "config",
        "show",
        "--profile",
        "local",
        "--config",
        str(config),
        env={"PYTHONPATH": str(blocker)},
    )
    assert code == 0
    assert payload["status"] == "ok"


def serve(handler=LocalKnudgHandler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_local_config_set_show_and_rejects_non_loopback(tmp_path):
    config = tmp_path / "client-config.json"
    code, payload = run_knudgctl("config", "show", "--profile", "local", "--config", str(config))
    assert code == 0
    assert payload["server_url"] is None
    assert payload["pin_state"] == "unpinned"
    assert payload["exploration_depth"] == "off"

    code, payload = run_knudgctl(
        "config",
        "set-server",
        "--profile",
        "local",
        "--server-url",
        "http://localhost:8787/",
        "--config",
        str(config),
    )
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["server_url"] == "http://localhost:8787"
    assert payload["pin_state"] == "unpinned"
    assert "token" not in config.read_text(encoding="utf-8").lower()

    code, payload = run_knudgctl("config", "show", "--profile", "local", "--config", str(config))
    assert code == 0
    assert payload["server_url"] == "http://localhost:8787"
    assert payload["tenant"] == {"present": False}
    assert payload["exploration_depth"] == "off"

    code, payload = run_knudgctl(
        "config",
        "set-server",
        "--profile",
        "local",
        "--server-url",
        "http://example.com:8787",
        "--config",
        str(config),
    )
    assert code == 3
    assert payload["status"] == "usage_error"

    code, payload = run_knudgctl(
        "config",
        "set-server",
        "--profile",
        "local",
        "--server-url",
        "http://localhost:8787",
        "--auth-profile",
        "cloud",
        "--config",
        str(config),
    )
    assert code == 3
    assert payload["status"] == "usage_error"


def test_exploration_depth_config_is_explicit_and_preserved(tmp_path):
    config = tmp_path / "client-config.json"

    code, payload = run_knudgctl("config", "set-exploration-depth", "hard", "--config", str(config))
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["exploration_depth"] == "hard"
    assert payload["guidance_mode"] == "root_cause_hint"

    code, payload = run_knudgctl("config", "show", "--profile", "cloud", "--config", str(config))
    assert code == 0
    assert payload["exploration_depth"] == "hard"

    code, payload = run_knudgctl(
        "config",
        "set-server",
        "--profile",
        "local",
        "--server-url",
        "http://localhost:8787",
        "--config",
        str(config),
    )
    assert code == 0
    code, payload = run_knudgctl("config", "show", "--profile", "local", "--config", str(config))
    assert code == 0
    assert payload["exploration_depth"] == "hard"

    code, payload = run_knudgctl("config", "set-exploration-depth", "harder", "--config", str(config))
    assert code == 0
    assert payload["exploration_depth"] == "harder"
    assert payload["guidance_mode"] == "publication_candidate"


def test_cloud_and_enterprise_custom_servers_are_parseable_not_configured(tmp_path):
    config = tmp_path / "client-config.json"
    for profile in ("cloud", "enterprise"):
        code, payload = run_knudgctl(
            "config",
            "set-server",
            "--profile",
            profile,
            "--server-url",
            "https://customer.example",
            "--config",
            str(config),
        )
        assert code == 2
        assert payload["status"] == "not_configured"
        assert payload["profile"] == profile


def test_server_status_capabilities_pin_and_mismatch(tmp_path):
    config = tmp_path / "client-config.json"
    server = serve()
    try:
        origin = f"http://localhost:{server.server_port}"
        run_knudgctl("config", "set-server", "--profile", "local", "--server-url", origin, "--config", str(config))

        code, payload = run_knudgctl("server", "status", "--config", str(config), env={"HTTP_PROXY": "http://127.0.0.1:1"})
        assert code == 0
        assert payload["status"] == "ok"
        assert payload["pin_state"] == "unpinned"
        assert payload["health"]["ready"]["route_classes"]["search"] == "disabled"

        code, payload = run_knudgctl("server", "capabilities", "--config", str(config))
        assert code == 0
        assert payload["pin_state"] == "unpinned"
        assert payload["capabilities_digest"].startswith("sha256:")

        code, payload = run_knudgctl("server", "capabilities", "--pin", "--config", str(config))
        assert code == 3
        assert payload["status"] == "usage_error"

        code, payload = run_knudgctl(
            "server",
            "capabilities",
            "--pin",
            "--allow-insecure-loopback",
            "--config",
            str(config),
        )
        assert code == 0
        assert payload["pin_state"] == "pinned"

        LocalKnudgHandler.server_id = "local-dev-changed"
        code, payload = run_knudgctl("server", "capabilities", "--config", str(config))
        assert code == 4
        assert payload["status"] == "server_pin_mismatch"
        assert payload["pin_state"] == "mismatch"
    finally:
        LocalKnudgHandler.server_id = "local-dev"
        server.shutdown()


def test_invalid_local_health_and_capabilities_are_runtime_failures(tmp_path):
    config = tmp_path / "client-config.json"
    server = serve()
    try:
        origin = f"http://localhost:{server.server_port}"
        run_knudgctl("config", "set-server", "--profile", "local", "--server-url", origin, "--config", str(config))

        LocalKnudgHandler.search_route = "enabled"
        code, payload = run_knudgctl("server", "status", "--config", str(config))
        assert code == 4
        assert payload["status"] == "unavailable"

        LocalKnudgHandler.search_route = "disabled"
        LocalKnudgHandler.deployment_type = "cloud"
        code, payload = run_knudgctl("server", "capabilities", "--config", str(config))
        assert code == 4
        assert payload["status"] == "capabilities_invalid"
    finally:
        LocalKnudgHandler.search_route = "disabled"
        LocalKnudgHandler.deployment_type = "local"
        server.shutdown()


def test_closed_launch_loopback_status_capabilities_and_pin(tmp_path):
    config = tmp_path / "client-config.json"

    class ClosedLaunchHandler(LocalKnudgHandler):
        server_id = "greencloud-closed-launch"
        deployment_type = "greencloud_closed_launch"
        search_route = "operator_private_exact_fts"

        def do_GET(self):
            if self.path in {"/health/startup", "/health/ready"}:
                self._write_json(
                    {
                        "status": "ready",
                        "deployment_type": self.deployment_type,
                        "components": {
                            "postgres": "ready",
                            "migration": "applied",
                            "auth_policy": "closed",
                            "revocation_epoch": "read_disabled",
                            "local_private_schema": "ready",
                            "publication": "disabled",
                            "publication_candidate": "ready",
                        },
                        "route_classes": {
                            "search": "operator_private_exact_fts",
                            "synthetic-retrieval": "disabled",
                            "card-read": "metadata_only",
                            "submit/write": "operator_private_sanitized_only",
                            "trusted-consent-revocation": "operator_private_revoke_purge",
                            "publication-candidate": "operator_private_candidate_only",
                            "reviewer-admin": "disabled",
                            "worker-lane": "disabled",
                            "landing": "disabled",
                        },
                    }
                )
                return
            if self.path == "/capabilities":
                origin = f"http://localhost:{self.server.server_port}"
                self._write_json(
                    {
                        "schema_version": 1,
                        "server_id": self.server_id,
                        "deployment_type": self.deployment_type,
                        "api_version": "v1",
                        "capability_resource_origin": origin,
                        "features": {
                            "search": True,
                            "write": True,
                            "operator_private_publish": True,
                            "operator_private_publication_candidate": True,
                            "synthetic_retrieval": False,
                            "protected_retrieval": False,
                            "publication": False,
                        },
                        "policy_versions": {
                            "privacy": "closed-launch-v1",
                            "consent": "closed-launch-disabled-v1",
                            "capabilities": "closed-launch-v1",
                        },
                        "auth": {
                            "profile": "closed_launch_no_user_routes",
                            "protected_resource_metadata_url": None,
                        },
                    }
                )
                return
            self._write_json({"status": "not_found"}, status=404)

    server = serve(ClosedLaunchHandler)
    try:
        origin = f"http://localhost:{server.server_port}"
        run_knudgctl("config", "set-server", "--profile", "local", "--server-url", origin, "--config", str(config))

        code, payload = run_knudgctl("server", "status", "--config", str(config))
        assert code == 0
        assert payload["health"]["ready"]["deployment_type"] == "greencloud_closed_launch"
        assert payload["health"]["ready"]["route_classes"]["search"] == "operator_private_exact_fts"

        code, payload = run_knudgctl(
            "server",
            "capabilities",
            "--pin",
            "--allow-insecure-loopback",
            "--config",
            str(config),
        )
        assert code == 0
        assert payload["server_id"] == "greencloud-closed-launch"
        saved = json.loads(config.read_text(encoding="utf-8"))
        assert saved["pins"]["local"]["pin_class"] == "closed_launch_loopback_operator_only"
        assert saved["capabilities_cache"]["local"]["capabilities"]["features"]["publication"] is False
    finally:
        server.shutdown()


def test_closed_launch_loopback_allows_https_capability_origin_from_tunnel(tmp_path):
    config = tmp_path / "client-config.json"

    class TunnelClosedLaunchHandler(LocalKnudgHandler):
        server_id = "greencloud-closed-launch"
        deployment_type = "greencloud_closed_launch"
        search_route = "operator_private_exact_fts"

        def do_GET(self):
            if self.path in {"/health/startup", "/health/ready"}:
                self._write_json(
                    {
                        "status": "ready",
                        "deployment_type": self.deployment_type,
                        "components": {"publication": "disabled"},
                        "route_classes": {
                            "search": "operator_private_exact_fts",
                            "trusted-consent-revocation": "operator_private_revoke_purge",
                            "reviewer-admin": "disabled",
                            "landing": "disabled",
                        },
                    }
                )
                return
            if self.path == "/capabilities":
                origin = f"https://localhost:{self.server.server_port}"
                self._write_json(
                    {
                        "schema_version": 1,
                        "server_id": self.server_id,
                        "deployment_type": self.deployment_type,
                        "api_version": "v1",
                        "capability_resource_origin": origin,
                        "features": {
                            "search": True,
                            "write": True,
                            "synthetic_retrieval": False,
                            "protected_retrieval": False,
                            "publication": False,
                        },
                        "policy_versions": {
                            "privacy": "closed-launch-v1",
                            "consent": "closed-launch-disabled-v1",
                        },
                        "auth": {
                            "profile": "closed_launch_no_user_routes",
                            "protected_resource_metadata_url": None,
                        },
                    }
                )
                return
            self._write_json({"status": "not_found"}, status=404)

    server = serve(TunnelClosedLaunchHandler)
    try:
        origin = f"http://localhost:{server.server_port}"
        run_knudgctl("config", "set-server", "--profile", "local", "--server-url", origin, "--config", str(config))
        code, payload = run_knudgctl("server", "capabilities", "--config", str(config))
        assert code == 0
        assert payload["server_id"] == "greencloud-closed-launch"
    finally:
        server.shutdown()


def test_closed_launch_allows_api_knudg_com_when_dns_resolves_to_tailscale(tmp_path, monkeypatch):
    import scripts.knudg_client_config as client_config

    original_http_connection = client_config.http.client.HTTPConnection
    original_getaddrinfo = client_config.socket.getaddrinfo

    class FakeConnection:
        def __init__(self, host, port, timeout):
            self.connection = original_http_connection("127.0.0.1", server.server_port, timeout=timeout)

        def request(self, method, path, headers=None):
            self.connection.request(method, path, headers=headers)

        def getresponse(self):
            return self.connection.getresponse()

        def close(self):
            self.connection.close()

    class ClosedTailnetHandler(LocalKnudgHandler):
        server_id = "greencloud-closed-launch"
        deployment_type = "greencloud_closed_launch"
        search_route = "operator_private_exact_fts"

        def do_GET(self):
            if self.path in {"/health/startup", "/health/ready"}:
                self._write_json(
                    {
                        "status": "ready",
                        "deployment_type": self.deployment_type,
                        "components": {"publication": "disabled"},
                        "route_classes": {
                            "search": "operator_private_exact_fts",
                            "trusted-consent-revocation": "operator_private_revoke_purge",
                            "reviewer-admin": "disabled",
                            "landing": "disabled",
                        },
                    }
                )
                return
            if self.path == "/capabilities":
                self._write_json(
                    {
                        "schema_version": 1,
                        "server_id": self.server_id,
                        "deployment_type": self.deployment_type,
                        "api_version": "v1",
                        "capability_resource_origin": "http://api.knudg.com",
                        "features": {
                            "search": True,
                            "write": True,
                            "synthetic_retrieval": False,
                            "protected_retrieval": False,
                            "publication": False,
                        },
                        "policy_versions": {
                            "privacy": "closed-launch-v1",
                            "consent": "closed-launch-disabled-v1",
                        },
                        "auth": {
                            "profile": "closed_launch_no_user_routes",
                            "protected_resource_metadata_url": None,
                        },
                    }
                )
                return
            self._write_json({"status": "not_found"}, status=404)

    server = serve(ClosedTailnetHandler)
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "api.knudg.com":
            return [(client_config.socket.AF_INET, client_config.socket.SOCK_STREAM, 0, "", ("100.78.239.26", port))]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(client_config.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(client_config.http.client, "HTTPConnection", FakeConnection)
    try:
        origin = client_config.normalize_server_url("http://api.knudg.com", "local")
        assert origin == "http://api.knudg.com"
        ready = client_config.validate_ready_health(client_config.probe_json(origin, "/health/ready"))
        assert ready["deployment_type"] == "greencloud_closed_launch"
        capabilities = client_config.validate_capabilities(
            client_config.probe_json(origin, "/capabilities"),
            origin,
        )
        assert capabilities["server_id"] == "greencloud-closed-launch"
    finally:
        server.shutdown()


def test_closed_launch_api_knudg_com_rejects_custom_port(tmp_path):
    config = tmp_path / "client-config.json"
    code, payload = run_knudgctl(
        "config",
        "set-server",
        "--profile",
        "local",
        "--server-url",
        "http://api.knudg.com:8788",
        "--config",
        str(config),
    )
    assert code == 3
    assert payload["status"] == "usage_error"


def test_server_url_override_is_unpinned_and_must_be_loopback(tmp_path):
    config = tmp_path / "client-config.json"
    first = serve()
    second = serve()
    try:
        run_knudgctl(
            "config",
            "set-server",
            "--profile",
            "local",
            "--server-url",
            f"http://localhost:{first.server_port}",
            "--config",
            str(config),
        )
        run_knudgctl(
            "server",
            "capabilities",
            "--pin",
            "--allow-insecure-loopback",
            "--config",
            str(config),
        )
        code, payload = run_knudgctl(
            "server",
            "status",
            "--server-url",
            f"http://localhost:{second.server_port}",
            "--config",
            str(config),
        )
        assert code == 0
        assert payload["pin_state"] == "override_unpinned"

        code, payload = run_knudgctl(
            "server",
            "status",
            "--server-url",
            "http://example.com",
            "--config",
            str(config),
        )
        assert code == 3
        assert payload["status"] == "usage_error"
    finally:
        first.shutdown()
        second.shutdown()


def test_server_status_server_url_implies_local_profile_without_config(tmp_path):
    config = tmp_path / "missing-client-config.json"
    server = serve()
    try:
        code, payload = run_knudgctl(
            "server",
            "status",
            "--server-url",
            f"http://localhost:{server.server_port}",
            "--config",
            str(config),
        )
        assert code == 0
        assert payload["profile"] == "local"
        assert payload["pin_state"] == "override_unpinned"
    finally:
        server.shutdown()
