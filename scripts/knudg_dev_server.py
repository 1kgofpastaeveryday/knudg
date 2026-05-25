#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from knudg_synthetic_retrieval import RetrievalError, SyntheticRetrievalError, search_synthetic


API_VERSION = "v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
MAX_JSON_BYTES = 256 * 1024


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_bytes(payload):
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def loopback_host(value):
    if value not in {"127.0.0.1", "localhost", "::1"}:
        raise argparse.ArgumentTypeError("dev server only binds localhost, 127.0.0.1, or ::1")
    return value


def host_header_origin(handler):
    host = (handler.headers.get("host") or "").strip().lower()
    if not host:
        host = f"127.0.0.1:{handler.server.server_port}"
    parsed = urlsplit(f"http://{host}")
    if parsed.username or parsed.password or parsed.scheme != "http" or not parsed.hostname:
        return None
    hostname = parsed.hostname.lower()
    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        return None
    port = parsed.port
    display_host = f"[{hostname}]" if hostname == "::1" else hostname
    return f"http://{display_host}{':' + str(port) if port else ''}"


class KnudgDevHandler(BaseHTTPRequestHandler):
    server_version = "KnudgDevServer/0"

    def log_message(self, format, *args):
        if not self.server.quiet:
            super().log_message(format, *args)

    def write_json(self, payload, status=200):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def health_payload(self):
        return {
            "status": "ready",
            "server_id": self.server.server_id,
            "deployment_type": "local",
            "api_version": API_VERSION,
            "checked_at": utc_now_iso(),
            "components": {
                "postgres": "not_configured",
                "migration": "not_configured",
                "auth_policy": "disabled",
                "revocation_epoch": "not_configured",
                "active_index_manifest": "disabled",
                "synthetic_retrieval": "ready",
            },
            "route_classes": {
                "search": "disabled",
                "synthetic-retrieval": "synthetic_only",
                "card-read": "disabled",
                "submit/write": "disabled",
                "trusted-consent-revocation": "disabled",
                "reviewer-admin": "disabled",
                "worker-lane": "disabled",
                "landing": "disabled",
            },
        }

    def capabilities_payload(self):
        origin = host_header_origin(self)
        if origin is None:
            return None
        return {
            "schema_version": 1,
            "server_id": self.server.server_id,
            "deployment_type": "local",
            "api_version": API_VERSION,
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
                "capabilities": "local-dev-v1",
            },
            "auth": {
                "profile": "local",
                "protected_resource_metadata_url": None,
            },
        }

    def do_GET(self):
        if self.path == "/":
            self.write_json(
                {
                    "status": "ok",
                    "service": "knudg-dev-server",
                    "detail": "temporary local loopback server for knudgctl custom-server dogfood",
                }
            )
            return
        if self.path in {"/health/live", "/health/startup", "/health/ready"}:
            self.write_json(self.health_payload())
            return
        if self.path == "/capabilities":
            payload = self.capabilities_payload()
            if payload is None:
                self.write_json({"status": "bad_request", "detail": "Host must be loopback"}, status=400)
                return
            self.write_json(payload)
            return
        self.write_json({"status": "not_found", "path": self.path}, status=404)

    def read_json_body(self):
        length_value = self.headers.get("content-length")
        if length_value is None:
            raise ValueError("content-length is required")
        try:
            length = int(length_value)
        except ValueError as exc:
            raise ValueError("content-length must be an integer") from exc
        if length < 1 or length > MAX_JSON_BYTES:
            raise ValueError("json body length is outside local limit")
        content_type = (self.headers.get("content-type") or "").split(";")[0].strip().lower()
        if content_type and content_type != "application/json":
            raise ValueError("content-type must be application/json")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_POST(self):
        if self.path != "/v1/synthetic-retrieval/search":
            self.write_json({"status": "not_found", "path": self.path}, status=404)
            return
        try:
            body = self.read_json_body()
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            request = body.get("request")
            corpus = body.get("corpus")
            min_score = body.get("min_score", 2)
            if not isinstance(min_score, int) or min_score < 1:
                raise ValueError("min_score must be a positive integer")
            self.write_json(search_synthetic(request, corpus, min_score))
        except json.JSONDecodeError:
            self.write_json(
                {
                    "decision": "no_suggestion",
                    "delivery_mode": "no_suggestion",
                    "abstention_reason": "payload_rejected",
                    "served_from": "synthetic_corpus",
                    "latency_budget_ms": None,
                    "cards": [],
                },
                status=400,
            )
        except (ValueError, SyntheticRetrievalError, RetrievalError) as exc:
            self.write_json(
                {
                    "decision": "no_suggestion",
                    "delivery_mode": "no_suggestion",
                    "abstention_reason": "payload_rejected",
                    "served_from": "synthetic_corpus",
                    "latency_budget_ms": None,
                    "error": str(exc),
                    "cards": [],
                },
                status=400,
            )


class KnudgDevServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, request_handler_class, *, server_id, quiet):
        self.server_id = server_id
        self.quiet = quiet
        super().__init__(server_address, request_handler_class)


def build_parser():
    parser = argparse.ArgumentParser(description="Temporary Knudg local loopback development server.")
    parser.add_argument("--host", type=loopback_host, default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--server-id", default="local-dev")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.port < 0 or args.port > 65535:
        parser.error("--port must be between 0 and 65535")
    server = KnudgDevServer((args.host, args.port), KnudgDevHandler, server_id=args.server_id, quiet=args.quiet)
    host = args.host
    display_host = f"[{host}]" if host == "::1" else host
    server_url = f"http://{display_host}:{server.server_port}"
    print(json.dumps({"status": "listening", "server_url": server_url, "server_id": args.server_id}, sort_keys=True), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
