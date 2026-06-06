#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
import math
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
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
from knudgctl import local_search_terms, require_local_search_task_profile
from jsonschema import Draft202012Validator
from validate_experience_storage_record import SCHEMA_PATH as EXPERIENCE_STORAGE_SCHEMA_PATH
from validate_experience_storage_record import gate_failures as experience_storage_gate_failures


API_VERSION = "v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
DEFAULT_DEPLOYMENT_TYPE = "greencloud_closed_launch"
DEFAULT_NVIDIA_FINAL_FILTER_MODEL = "z-ai/glm-5.1"
DEFAULT_NVIDIA_CHAT_COMPLETIONS_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_NVIDIA_FINAL_FILTER_TIMEOUT_SECONDS = 600.0
DEFAULT_FINAL_FILTER_NVIDIA_RPM = 40.0
DEFAULT_FINAL_FILTER_QUEUE_MAX_CONCURRENCY = 480
DEFAULT_FINAL_FILTER_QUEUE_POLL_SECONDS = 1.0
DEFAULT_FINAL_FILTER_QUEUE_MAX_ATTEMPTS = 5
MAX_JSON_BYTES = 64 * 1024
EXPECTED_MIGRATIONS = (
    "0001_m0_schema",
    "0002_local_private_dogfood",
    "0003_local_private_payload_contract",
    "0004_closed_api_health_grants",
    "0005_closed_private_publish_function",
    "0006_closed_private_search_revoke_purge",
    "0007_closed_api_runtime_role",
    "0008_closed_private_publication_candidate",
    "0009_closed_api_bound_runtime_wrappers",
    "0010_closed_api_card_view",
    "0011_domain_policy_lookup",
    "0012_redacted_experience_storage",
    "0013_local_private_human_summary_contract",
    "0014_final_filter_queue",
    "0015_local_private_merge_update",
    "0016_closed_private_purge_all_versions",
)
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
LOCAL_PRIVATE_WORKSPACE_REJECT = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"(^|\s)/(Users|home|var|etc|tmp|working)/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.IGNORECASE),
)
FINAL_FILTER_ALLOWED_VERDICTS = {"pass", "hold", "reject"}
FINAL_FILTER_ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
FINAL_FILTER_HOLD_REPAIR_POLICY = {
    "enabled_on_verdict": "hold",
    "parallel_reviewer_count": 3,
    "reviewer_required_outputs": ["ok_points", "ng_points", "repair_worthiness"],
    "repair_worthiness_values": ["worth_repair_attempt", "not_worth_repair"],
    "writer_input": "ng_points_only",
    "max_writer_attempts": 3,
    "pass_condition": "all_three_reviewers_pass",
    "reject_condition": "not_worth_repair_or_three_writer_attempts_without_pass",
}
FINAL_FILTER_BLOCK_PATTERNS = (
    ("secret", re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PRIVATE) KEY-----", re.IGNORECASE)),
    ("secret", re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b")),
    ("secret", re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{20,}")),
    ("local_path", re.compile(r"\b[A-Z]:\\(?:Users|working|tmp|Windows)\\", re.IGNORECASE)),
    ("raw_transcript", re.compile(r"\b(raw transcript|raw log|chat log|full transcript)\b", re.IGNORECASE)),
)
_EXPERIENCE_STORAGE_VALIDATOR = None
_NVIDIA_START_RATE_LIMITER = None
_NVIDIA_START_RATE_LIMITER_LOCK = threading.Lock()
_FINAL_FILTER_QUEUE_STARTED = False
_FINAL_FILTER_QUEUE_START_LOCK = threading.Lock()
_FINAL_FILTER_QUEUE_EXECUTOR = None
_FINAL_FILTER_QUEUE_SEMAPHORE = None


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_bytes(payload):
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def origin_from_headers(handler):
    host = (handler.headers.get("x-forwarded-host") or handler.headers.get("host") or "").strip()
    if not host:
        return None
    proto_header = handler.headers.get("x-forwarded-proto")
    proto = (proto_header or "").split(",")[0].strip().lower()
    if not proto:
        proto = "http"
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


def digest_label(value):
    if not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _split_configured_tokens(value):
    if not value:
        return []
    return [token.strip() for token in re.split(r"[\s,;]+", value) if token.strip()]


def operator_token_entries():
    seen = set()
    entries = []
    for label, value in (
        ("primary", os.environ.get("KNUDG_OPERATOR_TOKEN")),
        ("distribution", os.environ.get("KNUDG_DISTRIBUTION_TOKEN")),
        ("additional", os.environ.get("KNUDG_ADDITIONAL_OPERATOR_TOKENS")),
    ):
        for token in _split_configured_tokens(value):
            if token not in seen:
                seen.add(token)
                entries.append((label, token))
    return entries


def operator_tokens():
    return [token for label, token in operator_token_entries()]


def operator_auth_configured():
    return bool(operator_tokens())


def deployment_type():
    return os.environ.get("KNUDG_DEPLOYMENT_TYPE") or DEFAULT_DEPLOYMENT_TYPE


def nvidia_api_key():
    return os.environ.get("KNUDG_NVIDIA_API_KEY") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("NGC_API_KEY") or ""


def nvidia_final_filter_model():
    return os.environ.get("KNUDG_FINAL_FILTER_NVIDIA_MODEL") or DEFAULT_NVIDIA_FINAL_FILTER_MODEL


def nvidia_chat_completions_url():
    return os.environ.get("KNUDG_NVIDIA_CHAT_COMPLETIONS_URL") or DEFAULT_NVIDIA_CHAT_COMPLETIONS_URL


def nvidia_status_base_url():
    configured = os.environ.get("KNUDG_NVIDIA_STATUS_BASE_URL")
    if configured:
        return configured.rstrip("/")
    split = urlsplit(nvidia_chat_completions_url())
    return f"{split.scheme}://{split.netloc}/v1/status"


def nvidia_final_filter_timeout_seconds():
    try:
        value = float(os.environ.get("KNUDG_FINAL_FILTER_TIMEOUT_SECONDS", str(DEFAULT_NVIDIA_FINAL_FILTER_TIMEOUT_SECONDS)))
    except ValueError:
        value = DEFAULT_NVIDIA_FINAL_FILTER_TIMEOUT_SECONDS
    return min(max(value, 1.0), 600.0)


def final_filter_nvidia_rpm():
    try:
        value = float(os.environ.get("KNUDG_FINAL_FILTER_NVIDIA_RPM", str(DEFAULT_FINAL_FILTER_NVIDIA_RPM)))
    except ValueError:
        value = DEFAULT_FINAL_FILTER_NVIDIA_RPM
    return min(max(value, 1.0), DEFAULT_FINAL_FILTER_NVIDIA_RPM)


def final_filter_queue_enabled():
    return os.environ.get("KNUDG_FINAL_FILTER_QUEUE_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def final_filter_queue_workers_enabled():
    return os.environ.get("KNUDG_FINAL_FILTER_QUEUE_WORKERS_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def final_filter_queue_poll_seconds():
    try:
        value = float(os.environ.get("KNUDG_FINAL_FILTER_QUEUE_POLL_SECONDS", str(DEFAULT_FINAL_FILTER_QUEUE_POLL_SECONDS)))
    except ValueError:
        value = DEFAULT_FINAL_FILTER_QUEUE_POLL_SECONDS
    return min(max(value, 0.1), 30.0)


def final_filter_queue_max_attempts():
    try:
        value = int(os.environ.get("KNUDG_FINAL_FILTER_QUEUE_MAX_ATTEMPTS", str(DEFAULT_FINAL_FILTER_QUEUE_MAX_ATTEMPTS)))
    except ValueError:
        value = DEFAULT_FINAL_FILTER_QUEUE_MAX_ATTEMPTS
    return min(max(value, 1), 20)


def final_filter_queue_worker_concurrency():
    configured = os.environ.get("KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY")
    if configured:
        try:
            value = int(configured)
        except ValueError:
            value = 1
        return min(max(value, 1), DEFAULT_FINAL_FILTER_QUEUE_MAX_CONCURRENCY)
    interval = 60.0 / final_filter_nvidia_rpm()
    needed = math.ceil(nvidia_final_filter_timeout_seconds() / interval)
    return min(max(needed, int(final_filter_nvidia_rpm())), DEFAULT_FINAL_FILTER_QUEUE_MAX_CONCURRENCY)


def final_filter_queue_lease_seconds():
    interval = 60.0 / final_filter_nvidia_rpm()
    return int(nvidia_final_filter_timeout_seconds() + final_filter_queue_worker_concurrency() * interval + 60)


class StartRateLimiter:
    def __init__(self, rpm):
        self.interval_seconds = 60.0 / rpm
        self.next_start_at = 0.0
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self.next_start_at - now)
            scheduled = max(now, self.next_start_at)
            self.next_start_at = scheduled + self.interval_seconds
        if wait_seconds > 0:
            time.sleep(wait_seconds)


def nvidia_start_rate_limiter():
    global _NVIDIA_START_RATE_LIMITER
    with _NVIDIA_START_RATE_LIMITER_LOCK:
        if _NVIDIA_START_RATE_LIMITER is None:
            _NVIDIA_START_RATE_LIMITER = StartRateLimiter(final_filter_nvidia_rpm())
        return _NVIDIA_START_RATE_LIMITER


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
            "source": "closed launch private projection",
            "source_class": "local_private_dogfood",
        },
    }


def verify_operator_auth(handler):
    expected_entries = operator_token_entries()
    if not expected_entries:
        handler.auth_token_class = "not_configured"
        return False, 503, "operator token is not configured"
    header = handler.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        handler.auth_token_class = "missing"
        return False, 401, "bearer token is required"
    supplied = header.removeprefix("Bearer ").strip()
    for label, expected in expected_entries:
        if supplied and hmac.compare_digest(supplied, expected):
            handler.auth_token_class = label
            return True, 200, None
    handler.auth_token_class = "invalid"
    if not supplied:
        handler.auth_token_class = "missing"
        return False, 403, "bearer token is invalid"
    return False, 403, "bearer token is invalid"


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
        "operator_private_publish": "ready" if operator_auth_configured() and all(private_workspace_env()[key] for key in ("tenant_id", "namespace_id", "principal_id")) else "not_configured",
        "publication_candidate": "ready" if operator_auth_configured() and all(private_workspace_env()[key] for key in ("tenant_id", "namespace_id", "principal_id")) else "not_configured",
        "redacted_experience_storage": "ready" if operator_auth_configured() and all(private_workspace_env()[key] for key in ("tenant_id", "namespace_id", "principal_id")) else "not_configured",
        "final_filter": "ready" if operator_auth_configured() else "not_configured",
        "final_filter_queue": "ready" if final_filter_queue_enabled() and database_url() else "disabled",
        "final_filter_queue_workers": "ready" if final_filter_queue_enabled() and final_filter_queue_workers_enabled() and nvidia_api_key() and database_url() else "not_configured",
        "nvidia_glm_5_1": "ready" if nvidia_api_key() else "not_configured",
    }


def route_classes():
    auth_configured = operator_auth_configured()
    return {
        "search": "operator_private_exact_fts" if auth_configured else "disabled",
        "synthetic-retrieval": "disabled",
        "card-read": "metadata_only",
        "submit/write": "operator_private_sanitized_only" if auth_configured else "disabled",
        "trusted-consent-revocation": "operator_private_revoke_purge" if auth_configured else "disabled",
        "publication-candidate": "operator_private_candidate_only" if auth_configured else "disabled",
        "final-filter": "operator_private_llm_judge_fail_closed" if auth_configured else "disabled",
        "redacted-experience-storage": "operator_private_redacted_storage_only" if auth_configured else "disabled",
        "private-retention-completion": "operator_private_trusted_completion" if auth_configured else "disabled",
        "reviewer-admin": "disabled",
        "worker-lane": "disabled",
        "landing": "disabled",
    }


def header_host(value):
    if not value:
        return None
    try:
        split = urlsplit(value if "://" in value else f"http://{value}")
    except ValueError:
        return "invalid"
    return split.hostname or "invalid"


def client_ip_metadata(handler):
    remote_ip = handler.client_address[0] if handler.client_address else None
    forwarded = (handler.headers.get("x-forwarded-for") or "").split(",")
    forwarded_for = forwarded[0].strip() if forwarded and forwarded[0].strip() else None
    return {
        "remote_ip": remote_ip,
        "forwarded_for": forwarded_for,
        "forwarded_for_present": bool(forwarded_for),
        "forwarded_host": header_host(handler.headers.get("x-forwarded-host")),
        "forwarded_proto": (handler.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower() or None,
    }


def route_label(method, path):
    clean_path = path.split("?", 1)[0]
    if method == "OPTIONS":
        return "cors_preflight"
    if clean_path == "/":
        return "root"
    if clean_path in {"/health/live", "/health/startup", "/health/ready"}:
        return clean_path.removeprefix("/").replace("/", "_")
    if clean_path == "/capabilities":
        return "capabilities"
    if clean_path == "/v1/private/cards:publish":
        return "private_cards_publish"
    if clean_path == "/v1/private/search":
        return "private_search"
    if clean_path == "/v1/private/experience-records:store":
        return "private_experience_store"
    if re.fullmatch(r"/v1/private/experience-records/[0-9a-fA-F-]+:(revoke|purge)", clean_path):
        return "private_experience_mutate"
    if re.fullmatch(r"/v1/private/cards/[0-9a-fA-F-]+:(revoke|purge)", clean_path):
        return "private_cards_mutate"
    if re.fullmatch(r"/v1/private/cards/[0-9a-fA-F-]+:publication-candidate", clean_path):
        return "private_cards_publication_candidate"
    if clean_path == "/v1/private/final-filter:evaluate":
        return "private_final_filter_evaluate"
    if clean_path == "/v1/private/final-filter/jobs:stats":
        return "private_final_filter_queue_stats"
    if re.fullmatch(r"/v1/private/final-filter/jobs/[0-9a-fA-F-]+:view", clean_path):
        return "private_final_filter_job_view"
    if re.fullmatch(r"/v1/private/approval-handoffs/[0-9a-fA-F-]+:complete-private-retention", clean_path):
        return "private_retention_complete"
    if re.fullmatch(r"/v1/private/cards/[0-9a-fA-F-]+:view", clean_path):
        return "private_cards_view"
    if clean_path.startswith("/v1/private/"):
        return "private_unknown"
    return "unknown"


def local_private_card_merge_task_profile(card):
    explicit_parts = [
        card.get("title", ""),
        card.get("problem_summary", ""),
        card.get("solution_summary", ""),
    ]
    return {
        "schema_version": "task_profile.v0",
        "explicit_query": " ".join(part for part in explicit_parts if part).strip()[:900],
        "intent": "capture_or_update_local_private_card",
        "repo_shape_category": "local-private-knudg-card",
        "public_packages": list(card.get("public_packages") or [])[:8],
        "public_frameworks_tools": list(card.get("command_labels") or [])[:6],
        "subsystems": list(card.get("environment_tags") or [])[:8],
        "error_fingerprints": list(card.get("error_fingerprints") or [])[:6],
        "language_runtime": "unknown",
        "coarse_os": "unknown",
        "recent_event_kinds": ["write_candidate"],
    }


def local_private_merge_candidates(card, workspace_id, *, exclude_card_id=None):
    try:
        result = search_private_cards(
            local_private_card_merge_task_profile(card),
            workspace_id=workspace_id,
            limit=3,
            min_score=2,
            latency_budget_ms=250,
        )
    except Exception as exc:
        return {
            "schema_version": "local-private-merge-candidates-v0",
            "status": "unavailable",
            "recommended_action": "allow_create_new",
            "error_class": exc.__class__.__name__,
            "cards": [],
        }
    cards = list(result.get("cards") or [])
    if exclude_card_id:
        cards = [card for card in cards if card.get("card_id") != exclude_card_id]
    recommended_action = "update_existing" if cards else "allow_create_new"
    return {
        "schema_version": "local-private-merge-candidates-v0",
        "status": "ok",
        "recommended_action": recommended_action,
        "decision": result.get("decision", "no_suggestion"),
        "served_from": result.get("served_from"),
        "cards": cards,
    }


def validate_merge_reason(value):
    if value is None:
        return "same logical local private card"
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError("merge request rejected")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("merge request rejected")
    if any(pattern.search(value) for pattern in LOCAL_PRIVATE_WORKSPACE_REJECT):
        raise ValueError("merge request rejected")
    return value.strip()


def normalize_publish_merge_request(value):
    if value is None:
        return {
            "decision": None,
            "target_card_id": None,
            "reason": None,
        }
    if not isinstance(value, dict):
        raise ValueError("merge request rejected")
    if set(value) - {"decision", "target_card_id", "reason"}:
        raise ValueError("merge request rejected")
    decision = value.get("decision")
    target_card_id = value.get("target_card_id")
    if decision is None and target_card_id:
        decision = "update_existing"
    if decision not in {"update_existing", "create_new"}:
        raise ValueError("merge request rejected")
    if decision == "update_existing":
        if not isinstance(target_card_id, str) or not UUID_RE.fullmatch(target_card_id):
            raise ValueError("merge request rejected")
    elif target_card_id is not None:
        raise ValueError("merge request rejected")
    return {
        "decision": decision,
        "target_card_id": target_card_id,
        "reason": validate_merge_reason(value.get("reason")),
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
            from knudg_closed_api_publish(%s, %s::jsonb, %s::jsonb)
            """,
            (
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


def update_private_card_from_merge(card, workspace_id, merge_request):
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    body_digest = canonical_digest_hex(card)
    projection_payload = local_private_projection_payload(card, body_digest)
    merge_payload = {
        "schema_version": "local-private-merge-request-v0",
        "decision": "update_existing",
        "reason_digest": "sha256:" + hashlib.sha256(merge_request["reason"].encode("utf-8")).hexdigest(),
    }
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select *
            from knudg_closed_api_merge_update(%s, %s::uuid, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                workspace_id,
                merge_request["target_card_id"],
                json.dumps(card, sort_keys=True),
                json.dumps(projection_payload, sort_keys=True),
                json.dumps(merge_payload, sort_keys=True),
            ),
        ).fetchone()
    return {
        "tenant_id": str(row["tenant_id"]),
        "namespace_id": str(row["namespace_id"]),
        "principal_id": str(row["principal_id"]),
        "card_id": str(row["card_id"]),
        "previous_card_version_id": str(row["previous_card_version_id"]),
        "card_version_id": str(row["card_version_id"]),
        "version_number": int(row["version_number"]),
        "body_digest": row["body_digest"],
        "payload_digest": row["payload_digest"],
        "merge_update": {
            "schema_version": "local-private-merge-update-result-v0",
            "decision": "update_existing",
            "result": row["merge_result"],
            "same_logical_card": True,
            "created_new_card": False,
        },
    }


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
    request_body = json.loads(handler.rfile.read(length).decode("utf-8"))
    if not isinstance(request_body, dict):
        raise ValueError("request body must be an object")
    return request_body


def closed_private_no_suggestion(reason, latency_budget_ms):
    return {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": reason,
        "served_from": "closed_private_exact_fts",
        "latency_budget_ms": latency_budget_ms,
        "cards": [],
    }


def closed_private_panel_card(row):
    return {
        "card_id": str(row["card_id"]),
        "card_version_id": str(row["card_version_id"]),
        "namespace_id": str(row["namespace_id"]),
        "digest": row["payload_digest"],
        "local_only_status": "local_private",
        "outcome_type": row["outcome_type"],
        "quality_state": row["quality_state"],
        "evidence_strength": row["evidence_strength"],
        "withheld": False,
        "freshness_bucket": "local_private_current",
        "match_score": int(row["match_score"]),
        "coarse_match_reason": list(row["coarse_match_reason"] or [])[:8],
        "handoff_ref": f"local-card:{row['card_id']}:{row['card_version_id']}",
        "provenance": {
            "source": "closed private exact/FTS",
            "source_class": "local_private_dogfood",
        },
    }


def closed_private_workspace_args(workspace_id):
    env = private_workspace_env()
    if any(not env[key] for key in ("tenant_id", "namespace_id", "principal_id")):
        raise RuntimeError("private workspace identity is not configured")
    return env["tenant_id"], [env["namespace_id"]], env["principal_id"], local_private_check_workspace(workspace_id)


def search_private_cards(task_profile, *, workspace_id, limit=3, min_score=1, latency_budget_ms=250):
    task_profile = require_local_search_task_profile(task_profile)
    terms = local_search_terms(task_profile)
    if not terms:
        return closed_private_no_suggestion("low_confidence", latency_budget_ms)
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    limit = max(1, min(int(limit), 10))
    min_score = max(1, int(min_score))
    query_text = " ".join(terms)
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        rows = conn.execute(
            """
            select *
            from knudg_closed_api_search(%s, %s::text[], %s, %s)
            """,
            (workspace, terms, query_text, limit),
        ).fetchall()
    cards = [closed_private_panel_card(row) for row in rows if int(row["match_score"]) >= min_score]
    if not cards:
        return closed_private_no_suggestion("no_authorized_match", latency_budget_ms)
    return {
        "decision": "cards_found",
        "delivery_mode": "retrieval_panel",
        "served_from": "closed_private_exact_fts",
        "latency_budget_ms": latency_budget_ms,
        "cards": cards[:3],
    }


def mutate_private_card(action, card_id, reason, *, workspace_id):
    if not isinstance(card_id, str) or not UUID_RE.fullmatch(card_id):
        raise ValueError("card id rejected")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ValueError("reason rejected")
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    reason_digest = hashlib.sha256(reason.encode("utf-8")).hexdigest()
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    function_name = {
        "revoke": "knudg_closed_api_revoke",
        "purge": "knudg_closed_api_purge",
    }[action]
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            f"""
            select *
            from {function_name}(%s, %s::uuid, %s)
            """,
            (workspace, card_id, reason_digest),
        ).fetchone()
    affected_key = "revoked" if action == "revoke" else "purged"
    return {
        "card_id": card_id,
        "card_version_id": str(row["card_version_id"]) if row and row["card_version_id"] else None,
        affected_key: bool(row and row[affected_key]),
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
    }


def prepare_publication_candidate(card_id, *, workspace_id):
    if not isinstance(card_id, str) or not UUID_RE.fullmatch(card_id):
        raise ValueError("card id rejected")
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select *
            from knudg_closed_api_publication_candidate(%s, %s::uuid)
            """,
            (workspace, card_id),
        ).fetchone()
    surface_contracts = public_exposure_contract(row["candidate_digest"], row["payload_digest"])
    policy_context = {
        "check_stage": "publication_candidate_final_filter",
        "visibility_target": "public_candidate",
        "candidate_digest": row["candidate_digest"],
        "payload_digest": sha256_digest_ref(row["payload_digest"]),
        "surface_contracts": surface_contracts,
        "ad_or_spam_assessment_required": True,
        "commercial_incentive_disclosure_required": True,
        "spam_or_undisclosed_ad_blocks_publication": True,
        "public_publication_enabled": False,
    }
    final_filter = enqueue_or_evaluate_final_filter(row["candidate_json"], policy_context)
    return {
        "card_id": str(row["card_id"]),
        "card_version_id": str(row["card_version_id"]),
        "body_digest": row["body_digest"],
        "payload_digest": sha256_digest_ref(row["payload_digest"]),
        "candidate_digest": row["candidate_digest"],
        "candidate": row["candidate_json"],
        "surface_contracts": surface_contracts,
        "final_filter": final_filter,
        "stored_public_card": False,
        "public_publication_enabled": False,
        "external_publication_enabled": False,
        "requires_human_approval": True,
    }


def experience_storage_validator():
    global _EXPERIENCE_STORAGE_VALIDATOR
    if _EXPERIENCE_STORAGE_VALIDATOR is None:
        _EXPERIENCE_STORAGE_VALIDATOR = Draft202012Validator(
            json.loads(EXPERIENCE_STORAGE_SCHEMA_PATH.read_text(encoding="utf-8"))
        )
    return _EXPERIENCE_STORAGE_VALIDATOR


def validate_redacted_experience_record(record):
    if not isinstance(record, dict):
        raise ValueError("record rejected")
    errors = sorted(experience_storage_validator().iter_errors(record), key=lambda error: list(error.path))
    if errors or experience_storage_gate_failures(record):
        raise ValueError("record rejected")
    return record


def store_redacted_experience(record, *, workspace_id):
    record = validate_redacted_experience_record(record)
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select *
            from knudg_closed_api_store_redacted_experience(%s, %s::jsonb)
            """,
            (workspace, json.dumps(record, sort_keys=True)),
        ).fetchone()
    return {
        "tenant_id": str(row["tenant_id"]),
        "namespace_id": str(row["namespace_id"]),
        "principal_id": str(row["principal_id"]),
        "record_id": str(row["record_id"]),
        "private_retention_proof_bound": True,
        "domain": row["domain"],
        "subject_type": row["subject_type"],
        "subject_public_name": row["subject_public_name"],
        "payload_digest": row["payload_digest"],
        "stored": True,
        "publication_scope": "private",
        "record_visible_to_retrieval": bool(row["record_visible_to_retrieval"]),
        "public_candidate_conversion_enabled": bool(row["public_candidate_conversion_enabled"]),
        "public_serving_enabled": bool(row["public_serving_enabled"]),
        "b2b_delivery_enabled": bool(row["b2b_delivery_enabled"]),
        "identity_processing_enabled": bool(row["identity_processing_enabled"]),
        "raw_detail_escrow_enabled": bool(row["raw_detail_escrow_enabled"]),
        "dashboard_enabled": bool(row["dashboard_enabled"]),
        "protected_data_serving_enabled": False,
    }


def mutate_redacted_experience(action, record_id, reason, *, workspace_id):
    if not isinstance(record_id, str) or not UUID_RE.fullmatch(record_id):
        raise ValueError("record id rejected")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ValueError("reason rejected")
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    reason_digest = hashlib.sha256(reason.encode("utf-8")).hexdigest()
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    function_name = {
        "revoke": "knudg_closed_api_revoke_redacted_experience",
        "purge": "knudg_closed_api_purge_redacted_experience",
    }[action]
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            f"""
            select *
            from {function_name}(%s, %s::uuid, %s)
            """,
            (workspace, record_id, reason_digest),
        ).fetchone()
    affected_key = "revoked" if action == "revoke" else "purged"
    return {
        "record_id": str(row["record_id"]),
        "lifecycle_status": row["lifecycle_status"],
        affected_key: bool(row[affected_key]),
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
    }


def complete_private_retention(handoff_id, request_body, *, workspace_id):
    if not isinstance(handoff_id, str) or not UUID_RE.fullmatch(handoff_id):
        raise ValueError("handoff id rejected")
    if not isinstance(request_body, dict):
        raise ValueError("request rejected")
    required_confirmations = [
        "comprehension_confirmed",
        "private_retention_scope_confirmed",
        "no_publication_confirmed",
    ]
    if any(request_body.get(flag) is not True for flag in required_confirmations):
        raise ValueError("request rejected")
    idempotency_key = request_body.get("idempotency_key")
    if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,120}", idempotency_key):
        raise ValueError("request rejected")
    digest_fields = ["artifact_digest", "challenge_digest", "handoff_digest"]
    for field in digest_fields:
        value = request_body.get(field)
        pattern = r"(?:sha256:)?[a-f0-9]{64}" if field == "artifact_digest" else r"sha256:[a-f0-9]{64}"
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            raise ValueError("request rejected")
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    request_digest = "sha256:" + canonical_digest_hex(
        {
            "handoff_id": handoff_id.lower(),
            "idempotency_key": idempotency_key,
            "workspace": workspace,
            "confirmations": required_confirmations,
            "artifact_digest": request_body["artifact_digest"],
            "challenge_digest": request_body["challenge_digest"],
            "handoff_digest": request_body["handoff_digest"],
        }
    )
    correlation_id = request_body.get("correlation_id") or str(uuid_from_digest(request_digest))
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select *
            from knudg_closed_api_complete_private_retention(%s, %s::uuid, %s, %s, %s::uuid, %s, %s, %s, %s, %s, %s)
            """,
            (
                workspace,
                handoff_id,
                idempotency_key,
                request_digest,
                correlation_id,
                request_body["artifact_digest"],
                request_body["challenge_digest"],
                request_body["handoff_digest"],
                request_body["comprehension_confirmed"],
                request_body["private_retention_scope_confirmed"],
                request_body["no_publication_confirmed"],
            ),
        ).fetchone()
    return {
        "handoff_id": str(row["handoff_id"]),
        "challenge_id": str(row["challenge_id"]),
        "card_id": str(row["card_id"]),
        "card_version_id": str(row["current_version_id"]),
        "consent_id": str(row["consent_id"]),
        "event_id": str(row["event_id"]),
        "previous_status": row["previous_status"],
        "next_status": row["next_status"],
        "handoff_state": "consent_completed",
        "public_publication_enabled": False,
        "team_sharing_enabled": False,
        "protected_data_serving_enabled": False,
    }


def uuid_from_digest(digest):
    raw = hashlib.sha256(digest.encode("utf-8")).hexdigest()
    return f"{raw[:8]}-{raw[8:12]}-4{raw[13:16]}-8{raw[17:20]}-{raw[20:32]}"


def sha256_digest_ref(digest):
    if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest):
        return "sha256:" + digest
    return digest


def public_exposure_contract(candidate_digest, payload_digest):
    return {
        "schema_version": "public-exposure-contract-v0",
        "contract_digest_binding": {
            "candidate_digest": candidate_digest,
            "payload_digest": sha256_digest_ref(payload_digest),
        },
        "public_candidate_conversion": {
            "objective_item": 9,
            "enabled": False,
            "serving_enabled": False,
            "stored_public_card": False,
            "required_gates": ["PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"],
        },
        "b2b_respondent_portal": {
            "objective_item": 10,
            "enabled": False,
            "b2b_delivery_enabled": False,
            "response_available": False,
            "required_gates": ["ED-005", "MODERATION_WORKFLOW", "NO_DISCLOSURE_NEGATIVE_TESTS", "RESPONDENT_POLICY"],
        },
        "company_store_dashboard": {
            "objective_item": 13,
            "enabled": False,
            "dashboard_enabled": False,
            "aggregate_signal_available": False,
            "required_gates": [
                "AGGREGATE_PRIVACY_THRESHOLD_POLICY",
                "AGGREGATE_SIGNAL_POLICY",
                "CORRECTION_TAKEDOWN_POLICY",
                "DASHBOARD_DISPLAY_POLICY",
                "DASHBOARD_EXPORT_DOWNLOAD_POLICY",
                "FAIR_REVIEW_PRESENTATION_POLICY",
                "MANIPULATION_RESISTANCE_POLICY",
                "MIN_SOURCE_COUNT_POLICY",
                "MODERATION_WORKFLOW",
                "NO_ESCROW_ARTIFACT_DISPLAY_TESTS",
                "NO_IDENTITY_LEAKAGE_TESTS",
                "NO_SINGLE_OBSERVATION_DISPLAY_TESTS",
                "NO_SUPPRESSION_SURFACE_TESTS",
                "PUBLIC_B2B_DISCLOSURE_POLICY",
            ],
        },
        "forbidden_outputs": {
            "public_candidate_conversion": [
                "submitter_identity",
                "raw_source_material",
                "private_selection_status",
                "staff_identity",
                "raw_review_body",
                "non_public_operational_detail",
            ],
            "b2b_respondent_portal": [
                "submitter_identity",
                "raw_source_material",
                "device_or_network_signal",
                "reidentification_hint",
                "protected_fingerprint",
                "raw_review_body",
                "source_metadata",
                "raw_moderation_evidence",
                "escrow_ciphertext",
                "escrow_handle",
                "escrow_key_material",
                "reviewer_private_note",
                "non_public_operational_detail",
                "respondent_visible_user_attribution",
            ],
            "company_store_dashboard": [
                "submitter_identity",
                "raw_source_material",
                "device_or_network_signal",
                "reidentification_hint",
                "protected_fingerprint",
                "raw_review_body",
                "source_metadata",
                "raw_moderation_evidence",
                "escrow_ciphertext",
                "escrow_handle",
                "escrow_key_material",
                "account_identifier",
                "match_status",
                "individual_claim",
                "single_observation_detail",
                "reviewer_private_note",
                "non_public_operational_detail",
            ],
        },
    }


def final_filter_digest(candidate, policy_context):
    return "sha256:" + canonical_digest_hex(
        {
            "candidate": candidate,
            "policy_context": policy_context,
            "schema_version": "final-filter-request-v0",
        }
    )


def iter_final_filter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from iter_final_filter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_final_filter_strings(item)


def deterministic_final_filter_findings(candidate, policy_context):
    findings = []
    for text in iter_final_filter_strings({"candidate": candidate, "policy_context": policy_context}):
        for reason, pattern in FINAL_FILTER_BLOCK_PATTERNS:
            if pattern.search(text):
                findings.append(reason)
    return sorted(set(findings))


def final_filter_response(
    *,
    verdict,
    risk_level,
    risk_reasons,
    required_redactions=None,
    public_safe_summary=None,
    operator_note="",
    provider,
    model=None,
    request_digest,
    llm_called=False,
):
    if verdict not in FINAL_FILTER_ALLOWED_VERDICTS:
        raise ValueError("invalid final filter verdict")
    if risk_level not in FINAL_FILTER_ALLOWED_RISK_LEVELS:
        raise ValueError("invalid final filter risk level")
    normalized_reasons = []
    for reason in risk_reasons:
        if not isinstance(reason, str) or not reason or len(reason) > 80:
            raise ValueError("invalid final filter risk reason")
        normalized_reasons.append(reason)
    normalized_redactions = []
    for redaction in required_redactions or []:
        if not isinstance(redaction, dict):
            raise ValueError("invalid final filter redaction")
        field = redaction.get("field")
        reason = redaction.get("reason")
        if not isinstance(field, str) or not field or len(field) > 120:
            raise ValueError("invalid final filter redaction field")
        if not isinstance(reason, str) or not reason or len(reason) > 200:
            raise ValueError("invalid final filter redaction reason")
        normalized_redactions.append({"field": field, "reason": reason})
    if public_safe_summary is not None and not isinstance(public_safe_summary, str):
        raise ValueError("invalid final filter public summary")
    if not isinstance(operator_note, str) or len(operator_note) > 300:
        raise ValueError("invalid final filter operator note")
    return {
        "schema_version": "final-filter-result-v0",
        "verdict": verdict,
        "risk_level": risk_level,
        "risk_reasons": normalized_reasons,
        "required_redactions": normalized_redactions,
        "public_safe_summary": public_safe_summary,
        "operator_note": operator_note,
        "provider": provider,
        "model": model,
        "request_digest": request_digest,
        "llm_called": llm_called,
        "decision_label": {
            "pass": "clear_ok",
            "hold": "hold",
            "reject": "clear_ng",
        }[verdict],
        "fail_closed": verdict != "pass",
        "human_review_required": False,
        "automated_repair_required": verdict == "hold",
        "hold_repair_policy": FINAL_FILTER_HOLD_REPAIR_POLICY if verdict == "hold" else None,
        "public_publication_enabled": False,
        "final_publication_completion_enabled": False,
    }


def parse_json_object_text(text):
    if not isinstance(text, str):
        raise ValueError("model content is not text")
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


FINAL_FILTER_OUTPUT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": sorted(FINAL_FILTER_ALLOWED_VERDICTS)},
        "risk_level": {"type": "string", "enum": sorted(FINAL_FILTER_ALLOWED_RISK_LEVELS)},
        "risk_reasons": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "required_redactions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["field", "reason"],
            },
            "maxItems": 8,
        },
        "public_safe_summary": {"type": ["string", "null"]},
        "operator_note": {"type": "string"},
    },
    "required": [
        "verdict",
        "risk_level",
        "risk_reasons",
        "required_redactions",
        "public_safe_summary",
        "operator_note",
    ],
}

FINAL_FILTER_LABEL_ALIASES = {
    "pass": ("pass", "allow", "accept", "accepted", "safe", "approved", "approve", "clear_ok", "ok"),
    "hold": (
        "review",
        "needs_review",
        "needs_human_review",
        "human_review",
        "manual_review",
        "uncertain",
        "suspicious",
        "suspect",
        "quarantine",
        "quarantined",
        "hold",
    ),
    "reject": ("reject", "rejected", "block", "blocked", "fail", "failed", "unsafe"),
}


def final_filter_payload_from_label(label, source_payload=None):
    normalized = re.sub(r"[^a-z0-9_]+", "_", str(label).strip().lower()).strip("_")
    matched = None
    for verdict, aliases in FINAL_FILTER_LABEL_ALIASES.items():
        if normalized in aliases:
            matched = verdict
            break
    if not matched:
        raise ValueError("unrecognized final filter label")
    source_payload = source_payload if isinstance(source_payload, dict) else {}
    if matched == "pass":
        risk_level = "low"
        risk_reasons = []
    elif matched == "hold":
        risk_level = "medium"
        risk_reasons = ["model_requested_hold"]
    else:
        risk_level = "high"
        risk_reasons = ["model_rejected"]
    return {
        "verdict": matched,
        "risk_level": source_payload.get("risk_level") if source_payload.get("risk_level") in FINAL_FILTER_ALLOWED_RISK_LEVELS else risk_level,
        "risk_reasons": source_payload.get("risk_reasons") or risk_reasons,
        "required_redactions": source_payload.get("required_redactions") or [],
        "public_safe_summary": source_payload.get("public_safe_summary"),
        "operator_note": source_payload.get("operator_note") or f"Model returned compact label: {normalized}.",
    }


def coerce_final_filter_model_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("final filter model output must be an object")
    raw_verdict = payload.get("verdict")
    if raw_verdict in FINAL_FILTER_ALLOWED_VERDICTS:
        return payload
    if raw_verdict is not None:
        return final_filter_payload_from_label(raw_verdict, payload)
    for key in ("filter_result", "result", "decision", "label", "status"):
        if key in payload:
            return final_filter_payload_from_label(payload[key], payload)
    raise ValueError("final filter model output has no verdict")


def parse_final_filter_model_content(text):
    try:
        return parse_json_object_text(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        stripped = text.strip() if isinstance(text, str) else ""
        cleaned = re.sub(r"[^A-Za-z0-9_]+", " ", stripped).lower()
        matched = set()
        for verdict, aliases in FINAL_FILTER_LABEL_ALIASES.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", cleaned):
                    matched.add(verdict)
        if len(matched) == 1:
            return final_filter_payload_from_label(next(iter(matched)))
        if matched:
            return final_filter_payload_from_label(
                "hold",
                {
                    "risk_reasons": ["ambiguous_model_label"],
                    "operator_note": "Model returned multiple compact labels; fail-closed to hold repair.",
                },
            )
        raise


def default_risk_level_for_verdict(verdict):
    if verdict == "pass":
        return "low"
    if verdict == "hold":
        return "medium"
    return "high"


def normalize_model_risk_reasons(value):
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    normalized = []
    for item in raw_items[:8]:
        text = str(item).strip()
        if not text:
            continue
        reason = re.sub(r"[^A-Za-z0-9_]+", "_", text.lower()).strip("_")
        if not reason:
            reason = "model_reason"
        normalized.append(reason[:80].rstrip("_"))
    return normalized


def normalize_model_redactions(value):
    if not isinstance(value, list):
        return []
    redactions = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()[:120]
        reason = str(item.get("reason") or "").strip()[:200]
        if field and reason:
            redactions.append({"field": field, "reason": reason})
    return redactions


def truncate_model_text(value, limit):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def normalize_final_filter_model_output(payload, *, provider, model, request_digest):
    payload = coerce_final_filter_model_payload(payload)
    verdict = payload.get("verdict")
    risk_level = payload.get("risk_level") if payload.get("risk_level") in FINAL_FILTER_ALLOWED_RISK_LEVELS else default_risk_level_for_verdict(verdict)
    return final_filter_response(
        verdict=verdict,
        risk_level=risk_level,
        risk_reasons=normalize_model_risk_reasons(payload.get("risk_reasons")),
        required_redactions=normalize_model_redactions(payload.get("required_redactions")),
        public_safe_summary=truncate_model_text(payload.get("public_safe_summary"), 1000),
        operator_note=truncate_model_text(payload.get("operator_note") or payload.get("reason") or "", 300) or "",
        provider=provider,
        model=model,
        request_digest=request_digest,
        llm_called=True,
    )


def compact_final_filter_text(value, limit=1600):
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "...[truncated]"


def compact_final_filter_candidate(candidate):
    summary = candidate.get("human_summary") if isinstance(candidate.get("human_summary"), dict) else {}
    source_policy = candidate.get("source_policy") if isinstance(candidate.get("source_policy"), dict) else {}
    artifact = candidate.get("artifact") if isinstance(candidate.get("artifact"), dict) else {}
    redaction = candidate.get("redaction") if isinstance(candidate.get("redaction"), dict) else {}
    compact = {
        "schema_version": candidate.get("schema_version"),
        "candidate_state": candidate.get("candidate_state"),
        "card_type": candidate.get("card_type"),
        "human_summary": {
            "content": compact_final_filter_text(summary.get("content"), 2400),
            "redaction_summary": compact_final_filter_text(summary.get("redaction_summary"), 1000),
        },
        "source_policy": {
            "domain": source_policy.get("domain"),
            "visibility": source_policy.get("visibility"),
        },
        "artifact": {
            "title": compact_final_filter_text(artifact.get("title"), 400),
            "summary": compact_final_filter_text(artifact.get("summary"), 1200),
        },
        "redaction": {
            "state": redaction.get("state"),
            "raw_body_excluded": redaction.get("raw_body_excluded"),
            "private_identifiers_excluded": redaction.get("private_identifiers_excluded"),
        },
    }
    return {key: value for key, value in compact.items() if value not in (None, {}, [])}


def compact_final_filter_policy_context(policy_context):
    return {
        "check_stage": policy_context.get("check_stage"),
        "visibility_target": policy_context.get("visibility_target"),
        "candidate_digest": policy_context.get("candidate_digest"),
        "payload_digest": policy_context.get("payload_digest"),
        "surface_contracts_present": isinstance(policy_context.get("surface_contracts"), dict),
        "ad_or_spam_assessment_required": bool(policy_context.get("ad_or_spam_assessment_required")),
        "commercial_incentive_disclosure_required": bool(policy_context.get("commercial_incentive_disclosure_required")),
        "spam_or_undisclosed_ad_blocks_publication": bool(policy_context.get("spam_or_undisclosed_ad_blocks_publication")),
        "public_publication_enabled": bool(policy_context.get("public_publication_enabled")),
    }


def read_nvidia_json_response(response):
    data = response.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise RuntimeError("NVIDIA response exceeded JSON limit")
    return json.loads(data.decode("utf-8"))


def http_response_status(response):
    status = getattr(response, "status", None)
    if status is not None:
        return status
    return response.getcode()


def poll_nvidia_status(request_id, key, deadline):
    if not isinstance(request_id, str) or not request_id or len(request_id) > 80:
        raise RuntimeError("invalid NVIDIA pending request id")
    status_url = f"{nvidia_status_base_url()}/{request_id}"
    while time.monotonic() < deadline:
        time.sleep(min(5.0, max(0.1, deadline - time.monotonic())))
        remaining = max(1.0, min(60.0, deadline - time.monotonic()))
        request = urllib.request.Request(
            status_url,
            headers={
                "authorization": f"Bearer {key}",
                "accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=remaining) as response:
            response_payload = read_nvidia_json_response(response)
            status = http_response_status(response)
            if status == 200:
                return response_payload
            if status != 202:
                raise RuntimeError("unexpected NVIDIA status response")
    raise TimeoutError("NVIDIA pending request timed out")


def resolve_nvidia_chat_completion_response(response, key, deadline):
    response_payload = read_nvidia_json_response(response)
    status = http_response_status(response)
    if status == 200:
        return response_payload
    if status == 202:
        request_id = response_payload.get("requestId") or response_payload.get("request_id") or response_payload.get("id")
        return poll_nvidia_status(request_id, key, deadline)
    raise RuntimeError("unexpected NVIDIA chat completion response")


class FinalFilterRetryableProviderError(RuntimeError):
    pass


def final_filter_provider_hold_response(candidate, policy_context, request_digest, *, provider, model, reason, note, llm_called):
    return final_filter_response(
        verdict="hold",
        risk_level="medium",
        risk_reasons=[reason],
        required_redactions=[],
        public_safe_summary=None,
        operator_note=note,
        provider=provider,
        model=model,
        request_digest=request_digest,
        llm_called=llm_called,
    )


def evaluate_final_filter_for_queue_worker(candidate, policy_context, request_digest):
    deterministic_findings = deterministic_final_filter_findings(candidate, policy_context)
    if deterministic_findings:
        return final_filter_response(
            verdict="reject",
            risk_level="critical",
            risk_reasons=deterministic_findings,
            required_redactions=[{"field": "candidate", "reason": "blocked by deterministic preflight"}],
            public_safe_summary=None,
            operator_note="Deterministic preflight blocked this candidate before LLM review.",
            provider="rules",
            model=None,
            request_digest=request_digest,
            llm_called=False,
        )
    if not nvidia_api_key():
        return final_filter_provider_hold_response(
            candidate,
            policy_context,
            request_digest,
            provider="none",
            model=nvidia_final_filter_model(),
            reason="llm_provider_unconfigured",
            note="NVIDIA GLM-5.1 final filter is not configured.",
            llm_called=False,
        )
    try:
        return nvidia_glm_final_filter(candidate, policy_context, request_digest)
    except urllib.error.HTTPError as exc:
        if exc.code in {429, 500, 502, 503, 504}:
            raise FinalFilterRetryableProviderError(f"nvidia_http_{exc.code}") from exc
        return final_filter_provider_hold_response(
            candidate,
            policy_context,
            request_digest,
            provider="nvidia",
            model=nvidia_final_filter_model(),
            reason="llm_provider_error",
            note="NVIDIA GLM-5.1 final filter failed or returned invalid JSON.",
            llm_called=True,
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        raise FinalFilterRetryableProviderError(exc.__class__.__name__) from exc
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, RuntimeError):
        return final_filter_provider_hold_response(
            candidate,
            policy_context,
            request_digest,
            provider="nvidia",
            model=nvidia_final_filter_model(),
            reason="llm_provider_error",
            note="NVIDIA GLM-5.1 final filter failed or returned invalid JSON.",
            llm_called=True,
        )


def final_filter_retry_delay_seconds(attempts):
    return min(60 * (2 ** max(0, attempts - 1)), 900)


def final_filter_queue_unavailable(exc):
    return exc.__class__.__name__ in {"UndefinedTable", "UndefinedColumn", "InsufficientPrivilege"}


def enqueue_final_filter_job(candidate, policy_context, *, priority=0):
    request_digest = final_filter_digest(candidate, policy_context)
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    job_id = str(uuid.uuid4())
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            insert into final_filter_jobs(
              id, request_digest, candidate_json, policy_context_json,
              priority, max_attempts
            )
            values (%s, %s, %s::jsonb, %s::jsonb, %s, %s)
            on conflict (request_digest) do update
            set updated_at = now()
            returning *
            """,
            (
                job_id,
                request_digest,
                json.dumps(candidate, sort_keys=True),
                json.dumps(policy_context, sort_keys=True),
                int(priority),
                final_filter_queue_max_attempts(),
            ),
        ).fetchone()
    return row


def final_filter_queue_result_response(row):
    if row and row.get("status") == "succeeded" and isinstance(row.get("result_json"), dict):
        result = dict(row["result_json"])
        result.update(
            {
                "queued": False,
                "queue_status": "succeeded",
                "final_filter_job_id": str(row["id"]),
                "max_queries_per_minute": final_filter_nvidia_rpm(),
            }
        )
        return result
    request_digest = row["request_digest"] if row else "sha256:unknown"
    response = final_filter_response(
        verdict="hold",
        risk_level="medium",
        risk_reasons=["queued_for_llm_final_filter"],
        required_redactions=[],
        public_safe_summary=None,
        operator_note="Final filter queued for NVIDIA GLM-5.1 evaluation.",
        provider="queue",
        model=nvidia_final_filter_model(),
        request_digest=request_digest,
        llm_called=False,
    )
    response.update(
        {
            "queued": True,
            "queue_status": row["status"] if row else "queued",
            "final_filter_job_id": str(row["id"]) if row else None,
            "max_queries_per_minute": final_filter_nvidia_rpm(),
            "queue_worker_concurrency": final_filter_queue_worker_concurrency(),
        }
    )
    return response


def read_final_filter_job(job_id):
    if not isinstance(job_id, str) or not UUID_RE.fullmatch(job_id):
        raise ValueError("job id rejected")
    if not database_url():
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute("select * from final_filter_jobs where id = %s", (job_id,)).fetchone()
    if not row:
        raise PermissionError("job not found")
    return final_filter_queue_result_response(row)


def final_filter_queue_stats():
    if not database_url():
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url(), row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select
              count(*)::bigint as total_jobs,
              count(*) filter (where status = 'queued')::bigint as queued_jobs,
              count(*) filter (where status = 'queued' and available_at <= now())::bigint as ready_queued_jobs,
              count(*) filter (where status = 'queued' and available_at > now())::bigint as delayed_queued_jobs,
              count(*) filter (where status = 'leased')::bigint as leased_jobs,
              count(*) filter (where status = 'leased' and leased_until < now())::bigint as expired_leases,
              count(*) filter (where status = 'succeeded')::bigint as succeeded_jobs,
              count(*) filter (where status = 'dead')::bigint as dead_jobs,
              count(*) filter (where attempts > 0)::bigint as attempted_jobs,
              coalesce(sum(attempts), 0)::bigint as attempts_total,
              coalesce(max(attempts), 0)::integer as max_attempts_seen,
              floor(extract(epoch from now() - min(created_at) filter (where status = 'queued')))::bigint
                as oldest_queued_age_seconds,
              floor(extract(epoch from now() - min(available_at) filter (where status = 'queued' and available_at <= now())))::bigint
                as oldest_ready_queued_age_seconds,
              floor(extract(epoch from now() - min(leased_until) filter (where status = 'leased' and leased_until < now())))::bigint
                as oldest_expired_lease_age_seconds,
              floor(extract(epoch from now() - max(completed_at) filter (where status = 'succeeded')))::bigint
                as newest_succeeded_age_seconds
            from final_filter_jobs
            """
        ).fetchone()

    def as_int(value):
        return 0 if value is None else int(value)

    def as_age(value):
        return None if value is None else max(0, int(value))

    status_counts = {
        "queued": as_int(row["queued_jobs"]),
        "leased": as_int(row["leased_jobs"]),
        "succeeded": as_int(row["succeeded_jobs"]),
        "dead": as_int(row["dead_jobs"]),
    }
    return {
        "schema_version": "final-filter-queue-stats-v0",
        "checked_at": utc_now_iso(),
        "total_jobs": as_int(row["total_jobs"]),
        "active_depth": status_counts["queued"] + status_counts["leased"],
        "status_counts": status_counts,
        "ready_queued_jobs": as_int(row["ready_queued_jobs"]),
        "delayed_queued_jobs": as_int(row["delayed_queued_jobs"]),
        "expired_leases": as_int(row["expired_leases"]),
        "attempted_jobs": as_int(row["attempted_jobs"]),
        "attempts_total": as_int(row["attempts_total"]),
        "max_attempts_seen": as_int(row["max_attempts_seen"]),
        "age_seconds": {
            "oldest_queued": as_age(row["oldest_queued_age_seconds"]),
            "oldest_ready_queued": as_age(row["oldest_ready_queued_age_seconds"]),
            "oldest_expired_lease": as_age(row["oldest_expired_lease_age_seconds"]),
            "newest_succeeded": as_age(row["newest_succeeded_age_seconds"]),
        },
        "configuration": {
            "queue_enabled": final_filter_queue_enabled(),
            "workers_enabled": final_filter_queue_workers_enabled(),
            "max_queries_per_minute": final_filter_nvidia_rpm(),
            "worker_concurrency": final_filter_queue_worker_concurrency(),
            "timeout_seconds": nvidia_final_filter_timeout_seconds(),
            "max_attempts": final_filter_queue_max_attempts(),
        },
        "candidate_bodies_included": False,
        "result_bodies_included": False,
    }


def enqueue_or_evaluate_final_filter(candidate, policy_context):
    deterministic_findings = deterministic_final_filter_findings(candidate, policy_context)
    if deterministic_findings or not final_filter_queue_enabled() or not nvidia_api_key() or not database_url():
        return evaluate_final_filter({"candidate": candidate, "policy_context": policy_context})
    try:
        return final_filter_queue_result_response(enqueue_final_filter_job(candidate, policy_context))
    except Exception as exc:
        if final_filter_queue_unavailable(exc):
            return evaluate_final_filter({"candidate": candidate, "policy_context": policy_context})
        raise


def claim_final_filter_job():
    url = database_url()
    if not url:
        return None
    import psycopg
    from psycopg.rows import dict_row

    lease_seconds = final_filter_queue_lease_seconds()
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            update final_filter_jobs
            set status = 'leased',
                attempts = attempts + 1,
                leased_until = now() + (%s::text || ' seconds')::interval,
                started_at = coalesce(started_at, now()),
                updated_at = now()
            where id = (
              select id
              from final_filter_jobs
              where (
                status = 'queued'
                and available_at <= now()
              ) or (
                status = 'leased'
                and leased_until < now()
              )
              order by priority desc, available_at, created_at
              for update skip locked
              limit 1
            )
            returning *
            """,
            (lease_seconds,),
        ).fetchone()
    return row


def complete_final_filter_job(job_id, result):
    import psycopg

    with psycopg.connect(database_url(), connect_timeout=3) as conn:
        conn.execute(
            """
            update final_filter_jobs
            set status = 'succeeded',
                result_json = %s::jsonb,
                leased_until = null,
                completed_at = now(),
                updated_at = now(),
                last_error_class = null,
                last_error_detail = null
            where id = %s
            """,
            (json.dumps(result, sort_keys=True), job_id),
        )


def retry_or_hold_final_filter_job(row, exc):
    import psycopg

    attempts = int(row["attempts"])
    max_attempts = int(row["max_attempts"])
    if attempts >= max_attempts:
        result = final_filter_provider_hold_response(
            row["candidate_json"],
            row["policy_context_json"],
            row["request_digest"],
            provider="nvidia",
            model=nvidia_final_filter_model(),
            reason="llm_provider_error_after_retries",
            note="NVIDIA GLM-5.1 final filter failed after queued retries.",
            llm_called=True,
        )
        complete_final_filter_job(row["id"], result)
        return
    delay = final_filter_retry_delay_seconds(attempts)
    detail = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(exc))[:200] or exc.__class__.__name__
    with psycopg.connect(database_url(), connect_timeout=3) as conn:
        conn.execute(
            """
            update final_filter_jobs
            set status = 'queued',
                available_at = now() + (%s::text || ' seconds')::interval,
                leased_until = null,
                updated_at = now(),
                last_error_class = %s,
                last_error_detail = %s
            where id = %s
            """,
            (delay, exc.__class__.__name__, detail, row["id"]),
        )


def process_final_filter_job(row):
    try:
        result = evaluate_final_filter_for_queue_worker(row["candidate_json"], row["policy_context_json"], row["request_digest"])
        complete_final_filter_job(row["id"], result)
    except FinalFilterRetryableProviderError as exc:
        retry_or_hold_final_filter_job(row, exc)
    except Exception as exc:
        retry_or_hold_final_filter_job(row, exc)


def final_filter_queue_scheduler(server):
    while True:
        _FINAL_FILTER_QUEUE_SEMAPHORE.acquire()
        row = None
        try:
            row = claim_final_filter_job()
        except Exception as exc:
            _FINAL_FILTER_QUEUE_SEMAPHORE.release()
            if not getattr(server, "quiet", False):
                sys.stderr.write(json.dumps({"event": "final_filter_queue_error", "error_class": exc.__class__.__name__}, sort_keys=True) + "\n")
            time.sleep(final_filter_queue_poll_seconds())
            continue
        if not row:
            _FINAL_FILTER_QUEUE_SEMAPHORE.release()
            time.sleep(final_filter_queue_poll_seconds())
            continue

        def run_and_release(job_row):
            try:
                process_final_filter_job(job_row)
            finally:
                _FINAL_FILTER_QUEUE_SEMAPHORE.release()

        _FINAL_FILTER_QUEUE_EXECUTOR.submit(run_and_release, row)


def start_final_filter_queue_workers(server):
    global _FINAL_FILTER_QUEUE_STARTED, _FINAL_FILTER_QUEUE_EXECUTOR, _FINAL_FILTER_QUEUE_SEMAPHORE
    if not final_filter_queue_enabled() or not final_filter_queue_workers_enabled() or not database_url() or not nvidia_api_key():
        return False
    with _FINAL_FILTER_QUEUE_START_LOCK:
        if _FINAL_FILTER_QUEUE_STARTED:
            return True
        concurrency = final_filter_queue_worker_concurrency()
        _FINAL_FILTER_QUEUE_EXECUTOR = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="final-filter")
        _FINAL_FILTER_QUEUE_SEMAPHORE = threading.BoundedSemaphore(concurrency)
        thread = threading.Thread(target=final_filter_queue_scheduler, args=(server,), name="final-filter-queue-scheduler", daemon=True)
        thread.start()
        _FINAL_FILTER_QUEUE_STARTED = True
        return True


def nvidia_glm_final_filter(candidate, policy_context, request_digest):
    key = nvidia_api_key()
    if not key:
        raise RuntimeError("NVIDIA API key is not configured")
    model = nvidia_final_filter_model()
    prompt = {
        "task": "Evaluate a Knudg candidate for final safety filtering.",
        "decision_policy": [
            "Return pass only for Clear OK: the candidate is low-risk, non-promotional, non-spam, and safe to retain as reusable technical knowledge after LLM review.",
            "Return hold for Suspicious: company-store, career, complaint, reputation, public-candidate, ambiguous, or uncertain content that needs automated repair review.",
            "Hold is not human review; hold triggers a three-reviewer repair-worthiness check, writer repair using NG points only, and up to three writer attempts before reject.",
            "Return reject only for Clear NG: undisclosed sponsorship, affiliate incentives, lead capture, keyword stuffing, fake or unverifiable experience claims, coordinated low-signal submissions, secrets, private paths, raw transcripts, or identity leaks.",
            "Do not quote or repeat sensitive source text.",
            "This filter never enables public publication by itself.",
        ],
        "required_output_json_schema": FINAL_FILTER_OUTPUT_JSON_SCHEMA,
        "candidate": compact_final_filter_candidate(candidate),
        "policy_context": compact_final_filter_policy_context(policy_context),
    }
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict final safety filter for agent knowledge cards. "
                    "Think carefully, then return one compact JSON object only. Do not use markdown. "
                    "Do not quote secrets, personal data, raw source text, or private operational details."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, separators=(",", ":"), sort_keys=True)},
        ],
        "temperature": 0,
        "top_p": 1,
        "seed": 0,
        "max_tokens": 500,
        "stream": False,
        "guided_json": FINAL_FILTER_OUTPUT_JSON_SCHEMA,
    }
    request = urllib.request.Request(
        nvidia_chat_completions_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )
    nvidia_start_rate_limiter().acquire()
    deadline = time.monotonic() + nvidia_final_filter_timeout_seconds()
    with urllib.request.urlopen(request, timeout=nvidia_final_filter_timeout_seconds()) as response:
        response_payload = resolve_nvidia_chat_completion_response(response, key, deadline)
    content = response_payload["choices"][0]["message"]["content"]
    return normalize_final_filter_model_output(
        parse_final_filter_model_content(content),
        provider="nvidia",
        model=model,
        request_digest=request_digest,
    )


def evaluate_final_filter(request_body):
    if not isinstance(request_body, dict):
        raise ValueError("request rejected")
    candidate = request_body.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("candidate rejected")
    policy_context = request_body.get("policy_context") or {}
    if not isinstance(policy_context, dict):
        raise ValueError("policy context rejected")
    request_digest = final_filter_digest(candidate, policy_context)
    deterministic_findings = deterministic_final_filter_findings(candidate, policy_context)
    if deterministic_findings:
        return final_filter_response(
            verdict="reject",
            risk_level="critical",
            risk_reasons=deterministic_findings,
            required_redactions=[{"field": "candidate", "reason": "blocked by deterministic preflight"}],
            public_safe_summary=None,
            operator_note="Deterministic preflight blocked this candidate before LLM review.",
            provider="rules",
            model=None,
            request_digest=request_digest,
            llm_called=False,
        )
    if not nvidia_api_key():
        return final_filter_response(
            verdict="hold",
            risk_level="medium",
            risk_reasons=["llm_provider_unconfigured"],
            required_redactions=[],
            public_safe_summary=None,
            operator_note="NVIDIA GLM-5.1 final filter is not configured.",
            provider="none",
            model=nvidia_final_filter_model(),
            request_digest=request_digest,
            llm_called=False,
        )
    try:
        return nvidia_glm_final_filter(candidate, policy_context, request_digest)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError, urllib.error.URLError, TimeoutError, RuntimeError):
        return final_filter_response(
            verdict="hold",
            risk_level="medium",
            risk_reasons=["llm_provider_error"],
            required_redactions=[],
            public_safe_summary=None,
            operator_note="NVIDIA GLM-5.1 final filter failed or returned invalid JSON.",
            provider="nvidia",
            model=nvidia_final_filter_model(),
            request_digest=request_digest,
            llm_called=True,
        )


def read_private_card(card_id, *, workspace_id):
    if not isinstance(card_id, str) or not UUID_RE.fullmatch(card_id):
        raise ValueError("card id rejected")
    tenant_id, namespace_ids, principal_id, workspace = closed_private_workspace_args(workspace_id)
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(url, row_factory=dict_row, connect_timeout=3) as conn:
        row = conn.execute(
            """
            select *
            from knudg_closed_api_card_view(%s, %s::uuid)
            """,
            (workspace, card_id),
        ).fetchone()
    if row is None:
        raise PermissionError("private card not found")
    return {
        "card_id": str(row["card_id"]),
        "card_version_id": str(row["card_version_id"]),
        "namespace_id": str(row["namespace_id"]),
        "body_digest": row["body_digest"],
        "payload_digest": row["payload_digest"],
        "card": row["body_json"],
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
    }


class KnudgClosedApiHandler(BaseHTTPRequestHandler):
    server_version = "KnudgClosedAPI/0"

    def handle_one_request(self):
        self.request_started_at = time.monotonic()
        self.request_id = str(uuid.uuid4())
        self.auth_token_class = "not_checked"
        return super().handle_one_request()

    def log_message(self, format, *args):
        return

    def write_access_log(self, status):
        if self.server.quiet:
            return
        elapsed_ms = int((time.monotonic() - getattr(self, "request_started_at", time.monotonic())) * 1000)
        content_length = self.headers.get("content-length")
        try:
            request_bytes = int(content_length) if content_length is not None else None
        except ValueError:
            request_bytes = None
        event = {
            "event": "http_access",
            "service": "knudg-closed-api",
            "request_id": getattr(self, "request_id", None),
            "method": self.command,
            "route": route_label(self.command, self.path),
            "status": status,
            "elapsed_ms": elapsed_ms,
            "request_bytes": request_bytes,
            "auth_token_class": getattr(self, "auth_token_class", "not_checked"),
            "authorization_present": bool(self.headers.get("authorization")),
            "origin_host": header_host(self.headers.get("origin")),
            "host": header_host(self.headers.get("host")),
            "user_agent_digest": digest_label(self.headers.get("user-agent") or ""),
            **client_ip_metadata(self),
        }
        sys.stderr.write(json.dumps(event, sort_keys=True) + "\n")

    def write_json(self, payload, status=200):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.send_header("x-knudg-request-id", getattr(self, "request_id", ""))
        self.write_cors_headers()
        self.end_headers()
        self.wfile.write(body)
        self.write_access_log(status)

    def write_cors_headers(self):
        origin = (self.headers.get("origin") or "").strip()
        if not origin:
            return
        try:
            split = urlsplit(origin)
        except ValueError:
            return
        host = (split.hostname or "").lower()
        port = split.port
        if split.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"} and (port is None or 1 <= port <= 65535):
            self.send_header("access-control-allow-origin", origin)
            self.send_header("vary", "Origin")
            self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
            self.send_header("access-control-allow-headers", "Authorization, Content-Type, X-Knudg-Artifact-Digest")
            self.send_header("access-control-max-age", "600")

    def do_OPTIONS(self):
        self.send_response(204)
        self.write_cors_headers()
        self.send_header("content-length", "0")
        self.send_header("x-knudg-request-id", getattr(self, "request_id", ""))
        self.end_headers()
        self.write_access_log(204)

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
            "deployment_type": deployment_type(),
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
        auth_configured = operator_auth_configured()
        return {
            "schema_version": 1,
            "server_id": self.server.server_id,
            "deployment_type": deployment_type(),
            "api_version": API_VERSION,
            "capability_resource_origin": origin,
            "launch_state": "closed",
            "features": {
                "search": auth_configured,
                "synthetic_retrieval": False,
                "protected_retrieval": False,
                "publication": False,
                "write": auth_configured,
                "operator_private_publish": auth_configured,
                "operator_private_publication_candidate": auth_configured,
                "operator_private_redacted_experience_storage": auth_configured,
                "operator_private_trusted_completion": auth_configured,
                "operator_private_final_filter": auth_configured,
                "operator_private_final_filter_queue": auth_configured and final_filter_queue_enabled(),
                "nvidia_glm_5_1_final_filter": bool(nvidia_api_key()),
                "mcp_streamable_http": False,
            },
            "limits": {
                "final_filter_max_queries_per_minute": final_filter_nvidia_rpm(),
                "final_filter_queue_worker_concurrency": final_filter_queue_worker_concurrency(),
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
        self.write_json({"status": "not_found"}, status=404)

    def do_POST(self):
        if self.path == "/v1/private/cards:publish":
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                workspace_id = local_private_check_workspace(request_body.get("workspace", "closed-launch-manual"))
                card = validate_local_private_card_v0(request_body.get("card", request_body))
                merge_request = normalize_publish_merge_request(request_body.get("merge"))
                merge_candidates = local_private_merge_candidates(
                    card,
                    workspace_id,
                    exclude_card_id=merge_request["target_card_id"],
                )
                body_digest = canonical_digest_hex(card)
                approved_digest = (self.headers.get("x-knudg-artifact-digest") or "").strip().lower()
                if approved_digest != body_digest:
                    self.write_json(
                        {
                            "status": "approval_required",
                            "artifact_digest": body_digest,
                            "detail": "resubmit with X-Knudg-Artifact-Digest after reviewing the exact local artifact",
                            "merge_candidates": merge_candidates,
                            "merge_policy": {
                                "schema_version": "local-private-merge-policy-v0",
                                "default_when_similar": "update_existing",
                                "update_mechanism": "append_card_version_and_move_current_pointer",
                                "create_new_requires_explicit_decision": True,
                            },
                            "stored": False,
                            "public_publication_enabled": False,
                        },
                        status=409,
                    )
                    return
                if (
                    merge_candidates.get("recommended_action") == "update_existing"
                    and merge_request["decision"] is None
                ):
                    self.write_json(
                        {
                            "status": "merge_required",
                            "artifact_digest": body_digest,
                            "detail": "similar local private cards were found; resubmit with merge.target_card_id or merge.decision=create_new",
                            "merge_candidates": merge_candidates,
                            "stored": False,
                            "public_publication_enabled": False,
                        },
                        status=409,
                    )
                    return
                if merge_request["decision"] == "update_existing":
                    result = update_private_card_from_merge(card, workspace_id, merge_request)
                    response_status = "private_card_updated"
                    status_code = 200
                else:
                    result = insert_private_published_card(card, workspace_id)
                    response_status = "private_published"
                    status_code = 201
                self.write_json(
                    {
                        "status": response_status,
                        "stored": True,
                        "publication_scope": "private",
                        "public_publication_enabled": False,
                        "team_publication_enabled": False,
                        "searchable_in_private_namespace": True,
                        **result,
                    },
                    status=status_code,
                )
            except (ValueError, json.JSONDecodeError, LocalPrivateCardError):
                self.write_json({"status": "rejected", "stored": False, "reject_class": "local_private_card"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "stored": False, "error_class": exc.__class__.__name__}, status=503)
            return
        if self.path == "/v1/private/search":
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                result = search_private_cards(
                    request_body.get("task_profile"),
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                    limit=request_body.get("limit", 3),
                    min_score=request_body.get("min_score", 1),
                    latency_budget_ms=request_body.get("latency_budget_ms", 250),
                )
                self.write_json(
                    {
                        "status": "ok",
                        "result": result,
                        "protected_data_serving_enabled": False,
                        "publication_enabled": False,
                        "public_search_enabled": False,
                        "vector_search_enabled": False,
                    }
                )
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected", "reject_class": "task_profile"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        if self.path == "/v1/private/experience-records:store":
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                result = store_redacted_experience(
                    request_body.get("record"),
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                )
                self.write_json({"status": "redacted_experience_stored", **result}, status=201)
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected", "stored": False, "reject_class": "redacted_experience_record"}, status=400)
            except Exception as exc:
                if exc.__class__.__name__ in {"CheckViolation", "ForeignKeyViolation", "InvalidTextRepresentation"}:
                    self.write_json({"status": "rejected", "stored": False, "reject_class": "redacted_experience_consent_proof"}, status=400)
                    return
                self.write_json({"status": "unavailable", "stored": False, "error_class": exc.__class__.__name__}, status=503)
            return
        experience_action_match = re.fullmatch(r"/v1/private/experience-records/([0-9a-fA-F-]+):(revoke|purge)", self.path)
        if experience_action_match:
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            record_id, action = experience_action_match.groups()
            try:
                request_body = read_json_request(self)
                result = mutate_redacted_experience(
                    action,
                    record_id,
                    request_body.get("reason"),
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                )
                self.write_json({"status": "redacted_experience_revoked" if action == "revoke" else "redacted_experience_purged", **result})
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        action_match = re.fullmatch(r"/v1/private/cards/([0-9a-fA-F-]+):(revoke|purge)", self.path)
        if action_match:
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            card_id, action = action_match.groups()
            try:
                request_body = read_json_request(self)
                result = mutate_private_card(
                    action,
                    card_id,
                    request_body.get("reason"),
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                )
                self.write_json({"status": "revoked" if action == "revoke" else "purged", **result})
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        candidate_match = re.fullmatch(r"/v1/private/cards/([0-9a-fA-F-]+):publication-candidate", self.path)
        if candidate_match:
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                result = prepare_publication_candidate(
                    candidate_match.group(1),
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                )
                self.write_json({"status": "publication_candidate_ready", **result})
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        if self.path == "/v1/private/final-filter:evaluate":
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                result = evaluate_final_filter(request_body)
                self.write_json({"status": "final_filter_evaluated", **result})
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected", "reject_class": "final_filter_request"}, status=400)
            return
        if self.path == "/v1/private/final-filter/jobs:stats":
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                read_json_request(self)
                self.write_json({"status": "final_filter_queue_stats", "stats": final_filter_queue_stats()})
            except json.JSONDecodeError:
                self.write_json({"status": "rejected", "reject_class": "final_filter_queue_stats_request"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        final_filter_job_match = re.fullmatch(r"/v1/private/final-filter/jobs/([0-9a-fA-F-]+):view", self.path)
        if final_filter_job_match:
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                result = read_final_filter_job(final_filter_job_match.group(1))
                self.write_json({"status": "final_filter_job", **result})
            except ValueError:
                self.write_json({"status": "rejected", "reject_class": "final_filter_job_request"}, status=400)
            except PermissionError:
                self.write_json({"status": "not_found"}, status=404)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        handoff_completion_match = re.fullmatch(r"/v1/private/approval-handoffs/([0-9a-fA-F-]+):complete-private-retention", self.path)
        if handoff_completion_match:
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                result = complete_private_retention(
                    handoff_completion_match.group(1),
                    request_body,
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                )
                self.write_json({"status": "private_retention_consent_completed", **result})
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected", "reject_class": "private_retention_completion"}, status=400)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
            return
        view_match = re.fullmatch(r"/v1/private/cards/([0-9a-fA-F-]+):view", self.path)
        if view_match:
            ok, status, detail = verify_operator_auth(self)
            if not ok:
                self.write_json({"status": "unauthorized" if status == 401 else "forbidden", "detail": detail}, status=status)
                return
            try:
                request_body = read_json_request(self)
                result = read_private_card(
                    view_match.group(1),
                    workspace_id=request_body.get("workspace", "closed-launch-manual"),
                )
                self.write_json({"status": "private_card", **result})
            except (ValueError, json.JSONDecodeError):
                self.write_json({"status": "rejected"}, status=400)
            except PermissionError:
                self.write_json({"status": "not_found"}, status=404)
            except Exception as exc:
                self.write_json({"status": "unavailable", "error_class": exc.__class__.__name__}, status=503)
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
    parser.add_argument("--server-id", default=os.environ.get("KNUDG_SERVER_ID", "greencloud-closed-launch"))
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.port < 0 or args.port > 65535:
        parser.error("--port must be between 0 and 65535")
    server = KnudgClosedApiServer((args.host, args.port), KnudgClosedApiHandler, server_id=args.server_id, quiet=args.quiet)
    queue_workers_started = start_final_filter_queue_workers(server)
    print(
        json.dumps(
            {
                "status": "listening",
                "server_id": args.server_id,
                "host": args.host,
                "port": server.server_port,
                "launch_state": "closed",
                "final_filter_queue_workers_started": queue_workers_started,
                "final_filter_max_queries_per_minute": final_filter_nvidia_rpm(),
                "final_filter_queue_worker_concurrency": final_filter_queue_worker_concurrency() if queue_workers_started else 0,
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
