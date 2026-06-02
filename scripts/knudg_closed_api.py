#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.error
import urllib.request
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
DEFAULT_NVIDIA_FINAL_FILTER_TIMEOUT_SECONDS = 180.0
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
)
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
LOCAL_PRIVATE_WORKSPACE_REJECT = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"(^|\s)/(Users|home|var|etc|tmp|working)/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.IGNORECASE),
)
FINAL_FILTER_ALLOWED_VERDICTS = {"allow", "quarantine", "reject", "needs_human_review"}
FINAL_FILTER_ALLOWED_RISK_LEVELS = {"low", "medium", "high", "critical"}
FINAL_FILTER_BLOCK_PATTERNS = (
    ("secret", re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PRIVATE) KEY-----", re.IGNORECASE)),
    ("secret", re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b")),
    ("secret", re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{20,}")),
    ("local_path", re.compile(r"\b[A-Z]:\\(?:Users|working|tmp|Windows)\\", re.IGNORECASE)),
    ("raw_transcript", re.compile(r"\b(raw transcript|raw log|chat log|full transcript)\b", re.IGNORECASE)),
)
_EXPERIENCE_STORAGE_VALIDATOR = None


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


def deployment_type():
    return os.environ.get("KNUDG_DEPLOYMENT_TYPE") or DEFAULT_DEPLOYMENT_TYPE


def nvidia_api_key():
    return os.environ.get("KNUDG_NVIDIA_API_KEY") or os.environ.get("NVIDIA_API_KEY") or os.environ.get("NGC_API_KEY") or ""


def nvidia_final_filter_model():
    return os.environ.get("KNUDG_FINAL_FILTER_NVIDIA_MODEL") or DEFAULT_NVIDIA_FINAL_FILTER_MODEL


def nvidia_chat_completions_url():
    return os.environ.get("KNUDG_NVIDIA_CHAT_COMPLETIONS_URL") or DEFAULT_NVIDIA_CHAT_COMPLETIONS_URL


def nvidia_final_filter_timeout_seconds():
    try:
        value = float(os.environ.get("KNUDG_FINAL_FILTER_TIMEOUT_SECONDS", str(DEFAULT_NVIDIA_FINAL_FILTER_TIMEOUT_SECONDS)))
    except ValueError:
        value = DEFAULT_NVIDIA_FINAL_FILTER_TIMEOUT_SECONDS
    return min(max(value, 1.0), 240.0)


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
        "publication_candidate": "ready" if operator_token() and all(private_workspace_env()[key] for key in ("tenant_id", "namespace_id", "principal_id")) else "not_configured",
        "redacted_experience_storage": "ready" if operator_token() and all(private_workspace_env()[key] for key in ("tenant_id", "namespace_id", "principal_id")) else "not_configured",
        "final_filter": "ready" if operator_token() else "not_configured",
        "nvidia_glm_5_1": "ready" if nvidia_api_key() else "not_configured",
    }


def route_classes():
    return {
        "search": "operator_private_exact_fts" if operator_token() else "disabled",
        "synthetic-retrieval": "disabled",
        "card-read": "metadata_only",
        "submit/write": "operator_private_sanitized_only" if operator_token() else "disabled",
        "trusted-consent-revocation": "operator_private_revoke_purge" if operator_token() else "disabled",
        "publication-candidate": "operator_private_candidate_only" if operator_token() else "disabled",
        "final-filter": "operator_private_llm_judge_fail_closed" if operator_token() else "disabled",
        "redacted-experience-storage": "operator_private_redacted_storage_only" if operator_token() else "disabled",
        "private-retention-completion": "operator_private_trusted_completion" if operator_token() else "disabled",
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
    return {
        "card_id": str(row["card_id"]),
        "card_version_id": str(row["card_version_id"]),
        "body_digest": row["body_digest"],
        "payload_digest": sha256_digest_ref(row["payload_digest"]),
        "candidate_digest": row["candidate_digest"],
        "candidate": row["candidate_json"],
        "surface_contracts": surface_contracts,
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
        "fail_closed": verdict != "allow",
        "human_review_required": verdict in {"quarantine", "needs_human_review"},
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


def normalize_final_filter_model_output(payload, *, provider, model, request_digest):
    if not isinstance(payload, dict):
        raise ValueError("final filter model output must be an object")
    return final_filter_response(
        verdict=payload.get("verdict"),
        risk_level=payload.get("risk_level"),
        risk_reasons=payload.get("risk_reasons") or [],
        required_redactions=payload.get("required_redactions") or [],
        public_safe_summary=payload.get("public_safe_summary"),
        operator_note=payload.get("operator_note") or "",
        provider=provider,
        model=model,
        request_digest=request_digest,
        llm_called=True,
    )


def nvidia_glm_final_filter(candidate, policy_context, request_digest):
    key = nvidia_api_key()
    if not key:
        raise RuntimeError("NVIDIA API key is not configured")
    model = nvidia_final_filter_model()
    prompt = {
        "task": "Evaluate a Knudg candidate for final safety filtering. Return only JSON.",
        "allowed_verdicts": sorted(FINAL_FILTER_ALLOWED_VERDICTS),
        "allowed_risk_levels": sorted(FINAL_FILTER_ALLOWED_RISK_LEVELS),
        "policy": {
            "fail_closed": True,
            "allow_only_when_low_risk_and_public_safe": True,
            "company_store_career_or_complaint_content_requires_human_review": True,
            "raw_transcripts_secrets_private_paths_or_identity_leaks_must_not_be_allowed": True,
            "public_publication_is_not_enabled_by_this_filter": True,
        },
        "required_output": {
            "verdict": "allow | quarantine | reject | needs_human_review",
            "risk_level": "low | medium | high | critical",
            "risk_reasons": ["short_machine_reason"],
            "required_redactions": [{"field": "json.path", "reason": "short reason"}],
            "public_safe_summary": "string or null",
            "operator_note": "short internal explanation without quoting sensitive text",
        },
        "candidate": candidate,
        "policy_context": policy_context,
    }
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict final safety filter for agent knowledge cards. "
                    "Return one compact JSON object only. Do not quote secrets, personal data, "
                    "raw source text, or private operational details."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, sort_keys=True)},
        ],
        "temperature": 0,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
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
    with urllib.request.urlopen(request, timeout=nvidia_final_filter_timeout_seconds()) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    content = response_payload["choices"][0]["message"]["content"]
    return normalize_final_filter_model_output(
        parse_json_object_text(content),
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
            verdict="needs_human_review",
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
            verdict="needs_human_review",
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

    def log_message(self, format, *args):
        if not self.server.quiet:
            sys.stderr.write("closed-api request\n")

    def write_json(self, payload, status=200):
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.write_cors_headers()
        self.end_headers()
        self.wfile.write(body)

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
        self.end_headers()

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
        return {
            "schema_version": 1,
            "server_id": self.server.server_id,
            "deployment_type": deployment_type(),
            "api_version": API_VERSION,
            "capability_resource_origin": origin,
            "launch_state": "closed",
            "features": {
                "search": bool(operator_token()),
                "synthetic_retrieval": False,
                "protected_retrieval": False,
                "publication": False,
                "write": bool(operator_token()),
                "operator_private_publish": bool(operator_token()),
                "operator_private_publication_candidate": bool(operator_token()),
                "operator_private_redacted_experience_storage": bool(operator_token()),
                "operator_private_trusted_completion": bool(operator_token()),
                "operator_private_final_filter": bool(operator_token()),
                "nvidia_glm_5_1_final_filter": bool(nvidia_api_key()),
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
