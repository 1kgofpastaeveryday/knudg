#!/usr/bin/env python3
import argparse
import hmac
import json
import os
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
for candidate in (str(ROOT), str(SCRIPT_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from card_payload import canonical_digest_hex
from knudg_local_private import LocalPrivateCardError, validate_local_private_card_v0


API_VERSION = "v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
MAX_JSON_BYTES = 64 * 1024
EXPECTED_MIGRATIONS = (
    "0001_m0_schema",
    "0002_local_private_dogfood",
    "0003_local_private_payload_contract",
    "0004_closed_api_health_grants",
    "0005_closed_private_publish_function",
)
LOCAL_PRIVATE_WORKSPACE_REJECT = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"(^|\s)/(Users|home|var|etc|tmp|working)/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.IGNORECASE),
)


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_bytes(payload):
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def origin_from_headers(handler):
    host = (handler.headers.get("x-forwarded-host") or handler.headers.get("host") or "").strip()
    if not host:
        return None
    proto = (handler.headers.get("x-forwarded-proto") or "https").split(",")[0].strip().lower()
    if proto not in {"https", "http"}:
        return None
    try:
        split = urlsplit(f"{proto}://{host}")
    except ValueError:
        return None
    if split.username or split.password or not split.hostname:
        return None
    if split.query or split.fragment or split.path not in ("", "/"):
        return None
    display_host = f"[{split.hostname}]" if ":" in split.hostname else split.hostname
    return f"{split.scheme}://{display_host}{':' + str(split.port) if split.port else ''}"


def database_url():
    return os.environ.get("DATABASE_URL") or ""


def operator_token():
    return os.environ.get("KNUDG_OPERATOR_TOKEN") or ""


def private_workspace_env():
    return {
        "tenant_id": os.environ.get("KNUDG_PRIVATE_TENANT_ID") or "",
        "namespace_id": os.environ.get("KNUDG_PRIVATE_NAMESPACE_ID") or "",
        "principal_id": os.environ.get("KNUDG_PRIVATE_PRINCIPAL_ID") or "",
        "tenant_slug": os.environ.get("KNUDG_PRIVATE_TENANT_SLUG") or "knudg-closed-private",
        "namespace_key": os.environ.get("KNUDG_PRIVATE_NAMESPACE_KEY") or "closed-private",
    }


def local_private_check_workspace(workspace_id):
    if not isinstance(workspace_id, str) or not workspace_id.strip() or len(workspace_id) > 200:
        raise ValueError("workspace binding rejected")
    if any(token in workspace_id for token in ("\\", "/", ":", "..", "~")):
        raise ValueError("workspace binding rejected")
    if any(pattern.search(workspace_id) for pattern in LOCAL_PRIVATE_WORKSPACE_REJECT):
        raise ValueError("workspace binding rejected")
    if any(ord(char) < 32 or ord(char) == 127 for char in workspace_id):
        raise ValueError("workspace binding rejected")
    return workspace_id


def local_private_projection_payload(card, body_digest):
    return {
        "source_class": "local_private_dogfood",
        "visibility": "local_private",
        "sharing_state": "not_shared",
        "publication_state": "never_publishable",
        "outcome_type": "solved",
        "goal": "local private dogfood card",
        "symptom": "structured local private card captured for local search",
        "environment": {
            "tags": card["environment_tags"],
        },
        "context_fingerprint": {
            "public_packages": card["public_packages"],
            "public_frameworks_tools": [],
            "error_fingerprints": card["error_fingerprints"],
            "command_labels": card["command_labels"],
        },
        "successful_path": ["local private body retained in local_private_card_bodies"],
        "failed_paths": [],
        "known_unknowns": [],
        "scope_limits": [
            "local_private_dogfood side table only",
            "not eligible for public publication from this command path",
            "body text is purgeable and excluded from append-only payload_json",
        ],
        "evidence_strength": "operator_judgment",
        "quality_state": "unreviewed",
        "safety": {
            "safety_class": "low",
            "review_state": "cleared",
            "executable_advice": False,
            "mentions_urls": bool(card["public_reference_urls"]),
            "mentions_packages": bool(card["public_packages"]),
            "mentions_repositories": False,
            "credential_risk": False,
            "billing_risk": False,
            "deletion_risk": False,
            "network_call_risk": False,
            "verification_state": "unverified",
            "withheld_reason": None,
        },
        "privacy": {
            "contains_personal_data": False,
            "source_class": "local_private_dogfood",
            "local_private_body_table": "local_private_card_bodies",
            "body_digest": body_digest,
            "visibility": "local_private",
            "sharing_state": "not_shared",
            "publication_state": "never_publishable",
        },
        "provenance": {
            "source": "local private dogfood projection",
            "source_class": "local_private_dogfood",
        },
    }


def verify_operator_auth(handler):
    expected = operator_token()
    if not expected:
        return False, 503, "operator token is not configured"
    header = handler.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        return False, 401, "bearer token is required"
    supplied = header.removeprefix("Bearer ").strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        return False, 403, "bearer token is invalid"
    return True, 200, None


def db_snapshot():
    url = database_url()
    if not url:
        return {
            "postgres": "not_configured",
            "migration": "not_configured",
            "local_private_schema": "not_configured",
            "detail": "DATABASE_URL is not configured",
        }
    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
            server = conn.execute(
                """
                select current_database() as database,
                  current_user as user_name,
                  current_setting('server_version') as server_version,
                  current_setting('server_version_num')::int as server_version_num
                """
            ).fetchone()
            migrations = conn.execute(
                "select version, state from schema_migrations order by version"
            ).fetchall()
            migration_states = {row["version"]: row["state"] for row in migrations}
            extension_row = conn.execute(
                """
                select n.nspname as schema_name
                from pg_extension e
                join pg_namespace n on n.oid = e.extnamespace
                where e.extname = 'pgcrypto'
                """
            ).fetchone()
            rls_rows = conn.execute(
                """
                select c.relname, c.relrowsecurity, c.relforcerowsecurity
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public'
                  and c.relname in (
                    'local_private_card_bodies',
                    'local_private_search_documents',
                    'local_private_value_events'
                  )
                order by c.relname
                """
            ).fetchall()
            expected_applied = all(migration_states.get(version) == "applied" for version in EXPECTED_MIGRATIONS)
            pgcrypto_ready = extension_row and extension_row["schema_name"] == "knudg_crypto"
            rls_ready = len(rls_rows) == 3 and all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls_rows)
            schema_ready = expected_applied and bool(pgcrypto_ready) and rls_ready
            return {
                "postgres": "ready",
                "migration": "applied" if expected_applied else "incomplete",
                "local_private_schema": "ready" if schema_ready else "incomplete",
                "database": server["database"],
                "server_version": server["server_version"],
                "server_version_num": server["server_version_num"],
                "expected_migrations": {version: migration_states.get(version) for version in EXPECTED_MIGRATIONS},
                "pgcrypto_schema": extension_row["schema_name"] if extension_row else None,
                "rls_force_tables": sorted(row["relname"] for row in rls_rows if row["relrowsecurity"] and row["relforcerowsecurity"]),
            }
    except Exception as exc:
        return {
            "postgres": "unavailable",
            "migration": "unknown",
            "local_private_schema": "unknown",
            "error_class": exc.__class__.__name__,
        }


def components_from_snapshot(snapshot):
    return {
        "postgres": snapshot["postgres"],
        "migration": snapshot["migration"],
        "local_private_schema": snapshot["local_private_schema"],
        "auth_policy": "closed",
        "revocation_epoch": "read_disabled",
        "active_index_manifest": "disabled",
        "protected_retrieval": "disabled",
        "publication": "disabled",
        "operator_private_publish": "ready" if operator_token() and all(private_workspace_env()[key] for key in ("tenant_id", "namespace_id", "principal_id")) else "not_configured",
    }


def route_classes():
    return {
        "search": "disabled",
        "synthetic-retrieval": "disabled",
        "card-read": "disabled",
        "submit/write": "operator_private_sanitized_only" if operator_token() else "disabled",
        "trusted-consent-revocation": "disabled",
        "reviewer-admin": "disabled",
        "worker-lane": "disabled",
        "landing": "disabled",
    }


def insert_private_published_card(card, workspace_id):
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg

    body_digest = canonical_digest_hex(card)
    projection_payload = local_private_projection_payload(card, body_digest)
    env = private_workspace_env()
    if any(not env[key] for key in ("tenant_id", "namespace_id", "principal_id")):
        raise RuntimeError("private workspace identity is not configured")
    with psycopg.connect(url, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select *
            from knudg_closed_private_publish(
              %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb
            )
            """,
            (
                env["tenant_id"],
                env["namespace_id"],
                env["principal_id"],
                env["tenant_slug"],
                env["namespace_key"],
                workspace_id,
                json.dumps(card, sort_keys=True),
                json.dumps(projection_payload, sort_keys=True),
            ),
        ).fetchone()
    return {
        "tenant_id": str(row[0]),
        "namespace_id": str(row[1]),
        "principal_id": str(row[2]),
        "card_id": str(row[3]),
        "card_version_id": str(row[4]),
        "body_digest": row[5],
        "payload_digest": row[6],
    }


class KnudgClosedApiHandler(BaseHTTPRequestHandler):
    server_version = "KnudgClosedAPI/0"

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

    def health_payload(self, path):
        snapshot = db_snapshot()
        ready = (
            snapshot["postgres"] == "ready"
            and snapshot["migration"] == "applied"
            and snapshot["local_private_schema"] == "ready"
        )
        if path == "/health/live":
            status = "ok"
        elif path == "/health/startup":
            status = "ok"
        else:
            status = "ready" if ready else "degraded"
        return {
            "status": status,
            "server_id": self.server.server_id,
            "deployment_type": "azure_closed_launch",
            "api_version": API_VERSION,
            "launch_state": "closed",
            "checked_at": utc_now_iso(),
            "components": components_from_snapshot(snapshot),
            "database": {
                "configured": bool(database_url()),
                "name": snapshot.get("database"),
                "server_version": snapshot.get("server_version"),
                "expected_migrations": snapshot.get("expected_migrations", {}),
                "error_class": snapshot.get("error_class"),
            },
            "route_classes": route_classes(),
        }

    def capabilities_payload(self):
        origin = origin_from_headers(self)
        if origin is None:
            return None
        return {
            "schema_version": 1,
            "server_id": self.server.server_id,
            "deployment_type": "azure_closed_launch",
            "api_version": API_VERSION,
            "capability_resource_origin": origin,
            "launch_state": "closed",
            "features": {
                "search": False,
                "synthetic_retrieval": False,
                "protected_retrieval": False,
                "publication": False,
                "write": False,
                "operator_private_publish": bool(operator_token()),
                "mcp_streamable_http": False,
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
            "route_classes": route_classes(),
        }

    def do_GET(self):
        if self.path == "/":
            self.write_json(
                {
                    "status": "ok",
                    "service": "knudg-closed-api",
                    "launch_state": "closed",
                    "detail": "closed-launch Knudg API substrate; user-facing routes are disabled",
                }
            )
            return
        if self.path in {"/health/live", "/health/startup", "/health/ready"}:
            payload = self.health_payload(self.path)
            status = 200 if payload["status"] in {"ok", "ready"} else 503
            self.write_json(payload, status=status)
            return
        if self.path == "/capabilities":
            payload = self.capabilities_payload()
            if payload is None:
                self.write_json({"status": "bad_request", "detail": "invalid host/proto headers"}, status=400)
                return
            self.write_json(payload)
            return
        self.write_json({"status": "not_found", "path": self.path}, status=404)

    def do_POST(self):
        if self.path == "/v1/private/cards:publish":
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                length_value = self.headers.get("content-length")
                if length_value is None:
                    raise ValueError("content-length is required")
                length = int(length_value)
                if length < 1 or length > MAX_JSON_BYTES:
                    raise ValueError("json body length is outside limit")
                content_type = (self.headers.get("content-type") or "").split(";")[0].strip().lower()
                if content_type and content_type != "application/json":
                    raise ValueError("content-type must be application/json")
                request_body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(request_body, dict):
                    raise ValueError("request body must be an object")
                workspace_id = local_private_check_workspace(request_body.get("workspace", "closed-launch-manual"))
                card = validate_local_private_card_v0(request_body.get("card", request_body))
                body_digest = canonical_digest_hex(card)
                approved_digest = (self.headers.get("x-knudg-artifact-digest") or "").strip().lower()
                if approved_digest != body_digest:
                    self.write_json(
                        {
                            "status": "approval_required",
                            "artifact_digest": body_digest,
                            "detail": "resubmit with X-Knudg-Artifact-Digest after reviewing the exact local artifact",
                            "stored": False,
                            "public_publication_enabled": False,
                        },
                        status=409,
                    )
                    return
                result = insert_private_published_card(card, workspace_id)
                self.write_json(
                    {
                        "status": "private_published",
                        "stored": True,
                        "publication_scope": "private",
                        "public_publication_enabled": False,
                        "team_publication_enabled": False,
                        "searchable_in_private_namespace": True,
                        **result,
                    },
                    status=201,
                )
            except (ValueError, json.JSONDecodeError, LocalPrivateCardError):
                self.write_json({"status": "rejected", "stored": False, "reject_class": "local_private_card"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "stored": False, "error_class": exc.__class__.__name__}, status=503)
            return
        self.write_json(
            {
                "status": "closed",
                "launch_state": "closed",
                "detail": "write/search routes are disabled for this closed-launch deployment",
            },
            status=404,
        )


class KnudgClosedApiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, request_handler_class, *, server_id, quiet):
        self.server_id = server_id
        self.quiet = quiet
        super().__init__(server_address, request_handler_class)


def build_parser():
    parser = argparse.ArgumentParser(description="Knudg closed-launch API server.")
    parser.add_argument("--host", default=os.environ.get("HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    parser.add_argument("--server-id", default=os.environ.get("KNUDG_SERVER_ID", "azure-closed-launch"))
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.port < 0 or args.port > 65535:
        parser.error("--port must be between 0 and 65535")
    server = KnudgClosedApiServer((args.host, args.port), KnudgClosedApiHandler, server_id=args.server_id, quiet=args.quiet)
    print(
        json.dumps(
            {
                "status": "listening",
                "server_id": args.server_id,
                "host": args.host,
                "port": server.server_port,
                "launch_state": "closed",
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
