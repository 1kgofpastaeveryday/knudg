#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "operator-ui"
CONSENT_GATE_FIXTURE = ROOT / "fixtures" / "consent-revocation-gate.draft.json"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8765"
MAX_JSON_BYTES = 64 * 1024
ALLOWED_API_HOSTS = {"api.knudg.com", "localhost", "127.0.0.1", "::1"}
TAILSCALE_IPV4_NETWORK = ipaddress.ip_network("100.64.0.0/10")
TAILSCALE_IPV6_NETWORK = ipaddress.ip_network("fd7a:115c:a1e0::/48")


def json_bytes(payload):
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def consent_review_surface():
    gate = json.loads(CONSENT_GATE_FIXTURE.read_text(encoding="utf-8"))
    enabled_flags = sorted(name for name, value in gate["enablement"].items() if value)
    private_retention_completion_ready = any(
        surface["surface_type"] == "private_retention_consent"
        and surface["status"] == "trusted_completion_ready"
        and surface["completion_transport"] == "trusted_browser_or_os_surface"
        for surface in gate["surfaces"]
    )
    return {
        "schema_version": "consent-review-surface-v0",
        "source_gate_id": gate["gate_id"],
        "source_schema_version": gate["schema_version"],
        "status": gate["status"],
        "review_only": not private_retention_completion_ready,
        "completion_actions_enabled": private_retention_completion_ready,
        "private_retention_completion_ready": private_retention_completion_ready,
        "trusted_completion_enabled": gate["enablement"]["trusted_completion_enabled"],
        "public_publication_enabled": gate["enablement"]["public_publication_enabled"],
        "enabled_flags": enabled_flags,
        "blocked_until": gate["blocked_until"],
        "surfaces": [
            {
                "surface_type": surface["surface_type"],
                "canonical_scope": surface["canonical_scope"],
                "status": surface["status"],
                "completion_transport": surface["completion_transport"],
                "requires_step_up": surface["requires_step_up"],
                "requires_comprehension_gate": surface["requires_comprehension_gate"],
                "completion_action": (
                    "complete_private_retention"
                    if surface["surface_type"] == "private_retention_consent"
                    and private_retention_completion_ready
                    else "disabled"
                ),
            }
            for surface in gate["surfaces"]
        ],
        "experience_domain_boundaries": [
            {
                "domain": domain,
                "real_ingest_enabled": boundary["real_ingest_enabled"],
                "private_retention_completion_enabled": boundary["private_retention_completion_enabled"],
                "public_candidate_conversion_enabled": boundary["public_candidate_conversion_enabled"],
                "public_publication_completion_enabled": boundary["public_publication_completion_enabled"],
                "raw_source_retention_enabled": boundary["raw_source_retention_enabled"],
                "requires_domain_scoped_revocation": boundary["requires_domain_scoped_revocation"],
            }
            for domain, boundary in sorted(gate["experience_domain_boundaries"].items())
        ],
        "challenge_controls": gate["challenge_controls"],
        "agent_boundaries": gate["agent_boundaries"],
    }


def normalize_api_base_url(value):
    if not isinstance(value, str) or not value:
        raise ValueError("backend URL is required")
    split = urlsplit(value)
    if split.scheme != "http" or not split.hostname:
        raise ValueError("backend URL must be http")
    if split.username or split.password or split.query or split.fragment or split.path not in ("", "/"):
        raise ValueError("backend URL must be an origin")
    host = split.hostname.lower()
    try:
        parsed_ip = ipaddress.ip_address(host)
    except ValueError:
        parsed_ip = None
    if host not in ALLOWED_API_HOSTS and not (
        parsed_ip is not None and (parsed_ip in TAILSCALE_IPV4_NETWORK or parsed_ip in TAILSCALE_IPV6_NETWORK)
    ):
        raise ValueError("backend URL host is not allowed")
    if host == "api.knudg.com" and split.port not in {None, 80}:
        raise ValueError("api.knudg.com must use default HTTP port")
    display_host = f"[{host}]" if ":" in host else host
    return f"http://{display_host}{':' + str(split.port) if split.port else ''}"


def read_token():
    token = os.environ.get("KNUDG_OPERATOR_TOKEN") or ""
    if not token:
        raise RuntimeError("KNUDG_OPERATOR_TOKEN is required")
    return token


def read_json_request(handler):
    length_value = handler.headers.get("content-length")
    if length_value is None:
        raise ValueError("content-length is required")
    length = int(length_value)
    if length < 1 or length > MAX_JSON_BYTES:
        raise ValueError("json body length is outside limit")
    content_type = (handler.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/json":
        raise ValueError("content-type must be application/json")
    payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("request body must be an object")
    return payload


class LocalFrontendHandler(BaseHTTPRequestHandler):
    server_version = "KnudgLocalFrontend/0"

    def log_message(self, format, *args):
        if not self.server.quiet:
            sys.stderr.write("local-frontend request\n")

    def write_json(self, payload, status=200):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def write_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def upstream_json(self, method, path, payload=None, extra_headers=None):
        body = None if payload is None else json_bytes(payload)
        headers = {"accept": "application/json"}
        if payload is not None:
            headers["content-type"] = "application/json"
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(
            f"{self.server.api_base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response_body = response.read(MAX_JSON_BYTES + 1)
                if len(response_body) > MAX_JSON_BYTES:
                    raise RuntimeError("upstream response exceeded JSON limit")
                return response.status, json.loads(response_body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            response_body = exc.read(MAX_JSON_BYTES + 1)
            try:
                return exc.code, json.loads(response_body.decode("utf-8"))
            except json.JSONDecodeError:
                return exc.code, {"status": "upstream_error"}

    def do_GET(self):
        if self.path == "/":
            self.write_file(UI_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/app.js":
            self.write_file(UI_ROOT / "app.js", "text/javascript; charset=utf-8")
            return
        if self.path == "/styles.css":
            self.write_file(UI_ROOT / "styles.css", "text/css; charset=utf-8")
            return
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        if self.path == "/api/status":
            status, payload = self.upstream_json("GET", "/health/ready")
            self.write_json(
                {
                    "status": "ready" if status == 200 and payload.get("status") == "ready" else "unavailable",
                    "backend_url": self.server.api_base_url,
                    "backend": payload,
                },
                status=200,
            )
            return
        if self.path == "/api/consent-review":
            self.write_json(consent_review_surface())
            return
        self.write_json({"status": "not_found"}, status=404)

    def do_POST(self):
        try:
            payload = read_json_request(self)
        except (ValueError, json.JSONDecodeError):
            self.write_json({"status": "rejected"}, status=400)
            return
        headers = {"authorization": f"Bearer {self.server.operator_token}"}
        try:
            if self.path == "/api/cards:publish":
                digest = (payload.pop("approved_digest", None) or "").strip()
                if digest:
                    self.write_json(
                        {
                            "status": "completion_disabled",
                            "detail": "Browser digest completion is disabled; this surface can only stage review artifacts.",
                        },
                        status=409,
                    )
                    return
                status, upstream = self.upstream_json("POST", "/v1/private/cards:publish", payload, headers)
                if status != 409 or upstream.get("status") != "approval_required" or upstream.get("stored") is True:
                    self.write_json(
                        {
                            "status": "rejected",
                            "detail": "Upstream write path did not return a review-only approval challenge.",
                            "upstream_status": status,
                        },
                        status=502,
                    )
                    return
                self.write_json(upstream, status=status)
                return
            if self.path == "/api/search":
                status, upstream = self.upstream_json("POST", "/v1/private/search", payload, headers)
                self.write_json(upstream, status=status)
                return
            if self.path == "/api/experience-records:store":
                status, upstream = self.upstream_json("POST", "/v1/private/experience-records:store", payload, headers)
                self.write_json(upstream, status=status)
                return
            experience_action_match = re.fullmatch(r"/api/experience-records/([0-9a-fA-F-]+):(revoke|purge)", self.path)
            if experience_action_match:
                record_id, action = experience_action_match.groups()
                status, upstream = self.upstream_json(
                    "POST",
                    f"/v1/private/experience-records/{record_id}:{action}",
                    payload,
                    headers,
                )
                self.write_json(upstream, status=status)
                return
            handoff_match = re.fullmatch(r"/api/approval-handoffs/([0-9a-fA-F-]+):complete-private-retention", self.path)
            if handoff_match:
                status, upstream = self.upstream_json(
                    "POST",
                    f"/v1/private/approval-handoffs/{handoff_match.group(1)}:complete-private-retention",
                    payload,
                    headers,
                )
                self.write_json(upstream, status=status)
                return
            view_match = re.fullmatch(r"/api/cards/([0-9a-fA-F-]+):view", self.path)
            if view_match:
                status, upstream = self.upstream_json("POST", f"/v1/private/cards/{view_match.group(1)}:view", payload, headers)
                self.write_json(upstream, status=status)
                return
        except Exception as exc:
            self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        self.write_json({"status": "not_found"}, status=404)


class LocalFrontendServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, request_handler_class, *, api_base_url, operator_token, quiet):
        self.api_base_url = api_base_url
        self.operator_token = operator_token
        self.quiet = quiet
        super().__init__(server_address, request_handler_class)


def build_parser():
    parser = argparse.ArgumentParser(description="Local Knudg operator frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--api-base-url", default=os.environ.get("KNUDG_FRONTEND_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    api_base_url = normalize_api_base_url(args.api_base_url)
    token = read_token()
    server = LocalFrontendServer(
        (args.host, args.port),
        LocalFrontendHandler,
        api_base_url=api_base_url,
        operator_token=token,
        quiet=args.quiet,
    )
    print(
        json.dumps(
            {
                "status": "listening",
                "url": f"http://{args.host}:{server.server_port}",
                "backend_url": api_base_url,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
