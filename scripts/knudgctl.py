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
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from knudg_client_config import (
    CapabilitiesInvalid,
    ConfigError,
    HealthInvalid,
    ProbeError,
    canonical_capabilities_digest,
    default_config,
    effective_profile,
    load_config,
    normalize_server_url,
    probe_json,
    save_config,
    utc_now_iso,
    validate_capabilities,
    validate_ready_health,
)
from card_payload import canonical_digest_hex
from knudg_domain_policy import DomainPolicyError, normalize_retrieval_domains
from knudg_task_profile import TaskProfileError, build_query_views, build_task_profile
from knudg_local_private import (
    LocalPrivateCardError,
    validate_local_private_card_v0,
)


DEFAULT_DATABASE_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"
EXIT_OK = 0
EXIT_NOT_CONFIGURED = 2
EXIT_USAGE = 3
EXIT_UNAVAILABLE = 4
EXIT_REJECTED = 2
EXIT_LOCAL_DB_FAILURE = 3
PROFILE_CHOICES = ("local", "cloud", "enterprise")
EXPLORATION_DEPTH_CHOICES = ("off", "hard", "harder")
WRITER_CARD_STATUSES = (
    "candidate_created",
    "pending_admission",
    "deferred",
    "pending_redaction",
    "pending_review",
    "awaiting_user_approval",
)
WRITER_JOB_LANES = ("public_candidate_ingest", "redaction", "review", "approval_publish", "consent", "event_projection")
WRITER_ENQUEUE_STATUSES = (
    "candidate_created",
    "deferred",
    "pending_admission",
    "pending_redaction",
    "pending_review",
)
WRITER_RUN_OPERATIONS = {
    "accept_admission": {
        "lane": "public_candidate_ingest",
        "worker_role": "ingestion_worker",
        "function": "knudg_accept_admission",
    },
    "request_redaction": {
        "lane": "redaction",
        "worker_role": "ingestion_worker",
        "function": "knudg_request_redaction",
    },
    "complete_redaction": {
        "lane": "redaction",
        "worker_role": "redaction_worker",
        "function": "knudg_complete_redaction",
    },
    "request_private_approval": {
        "lane": "review",
        "worker_role": "review_worker",
        "function": "knudg_request_private_approval",
    },
}
WRITER_RUN_LANES = tuple(dict.fromkeys(spec["lane"] for spec in WRITER_RUN_OPERATIONS.values()))
LOCAL_SEARCH_RAW_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"(^|\s)/(Users|home|var|etc|tmp)/", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.IGNORECASE),
]
LOCAL_SEARCH_ALLOWED_PROFILE_FIELDS = {
    "schema_version",
    "explicit_query",
    "intent",
    "repo_shape_category",
    "subsystems",
    "safe_file_refs",
    "symbols",
    "error_fingerprints",
    "public_packages",
    "public_frameworks_tools",
    "language_runtime",
    "coarse_os",
    "dependency_major_versions",
    "risk_tags",
    "recent_event_kinds",
    "retrieval_domains",
}
LOCAL_PRIVATE_FUTURE_BOUNDARY_TABLES = (
    "embedding_jobs",
    "embedding_vectors",
    "export_artifacts",
    "hosted_sync_state",
    "product_search_projections",
    "public_search_projections",
    "review_assignments",
    "review_cases",
)


def local_private_check_workspace(workspace_id):
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("workspace binding rejected")
    if len(workspace_id) > 200:
        raise ValueError("workspace binding rejected")
    reject_local_search_raw(workspace_id)
    if any(token in workspace_id for token in ("\\", "/", ":", "..", "~")):
        raise ValueError("workspace binding rejected")
    return workspace_id


def local_private_require_tenant_membership(conn, tenant_id, principal_id):
    row = conn.execute(
        """
        select exists (
          select 1
          from tenant_memberships tm
          where tm.tenant_id = %s::uuid
            and tm.principal_id = %s::uuid
            and tm.status = 'active'
            and tm.valid_from <= now()
            and tm.revoked_at is null
            and (tm.expires_at is null or tm.expires_at > now())
            and (tm.effective_until is null or tm.effective_until > now())
        ) as ok
        """,
        (tenant_id, principal_id),
    ).fetchone()
    if not row or not row["ok"]:
        raise PermissionError("local principal binding rejected")


def local_private_require_namespace_scope(conn, tenant_id, namespace_ids, principal_id, scopes):
    local_private_require_tenant_membership(conn, tenant_id, principal_id)
    rows = conn.execute(
        """
        select ns.namespace_id, exists (
          select 1
          from namespaces n
          join namespace_grants ng
            on ng.tenant_id = n.tenant_id
           and ng.namespace_id = n.id
          where n.tenant_id = %s::uuid
            and n.id = ns.namespace_id
            and n.archived_at is null
            and ng.principal_id = %s::uuid
            and ng.status = 'active'
            and ng.valid_from <= now()
            and (ng.expires_at is null or ng.expires_at > now())
            and (ng.revoked_at is null)
            and ng.grant_scope = any(%s::text[])
        ) as ok
        from unnest(%s::uuid[]) as ns(namespace_id)
        """,
        (tenant_id, principal_id, list(scopes), namespace_ids),
    ).fetchall()
    if not rows or any(not row["ok"] for row in rows):
        raise PermissionError("local namespace binding rejected")


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        emit("knudgctl", "usage_error", EXIT_USAGE, detail=message)
        raise SystemExit(EXIT_USAGE)


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def emit(command, status, exit_code, **fields):
    payload = {
        "command": command,
        "status": status,
        "ok": exit_code == EXIT_OK,
        "exit_code": exit_code,
    }
    payload.update(fields)
    print(json.dumps(payload, sort_keys=True, default=json_default))
    return exit_code


def emit_client(command, status, exit_code, **fields):
    fields.setdefault("request_id", f"knudgctl_{uuid.uuid4().hex}")
    fields.setdefault("correlation_id", f"knudgctl_{uuid.uuid4().hex}")
    return emit(command, status, exit_code, **fields)


def opaque_arg(value):
    if value is None:
        return {"present": False}
    return {
        "present": True,
        "sha256": hashlib.sha256(str(value).encode("utf-8")).hexdigest(),
    }


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def nonnegative_int(value):
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def retry_delay_seconds(value):
    parsed = nonnegative_int(value)
    if parsed > 86400:
        raise argparse.ArgumentTypeError("must be <= 86400")
    return parsed


def connect(args):
    import psycopg
    from psycopg.rows import dict_row

    url = args.database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=3)


def load_json_arg(value):
    stripped = value.strip() if isinstance(value, str) else value
    if isinstance(stripped, str) and stripped.startswith(("{", "[")):
        return json.loads(stripped)
    return json.loads(Path(value).read_text(encoding="utf-8"))


def post_json(origin, path, payload, *, timeout_seconds=5.0, max_bytes=262144):
    normalized = normalize_server_url(origin, "local")
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    if len(body) > max_bytes:
        raise ProbeError("request body exceeds local JSON limit")
    request = urllib.request.Request(
        f"{normalized}{path}",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read(max_bytes + 1)
            if len(response_body) > max_bytes:
                raise ProbeError("response body exceeds local JSON limit")
            return json.loads(response_body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_body = exc.read(max_bytes + 1)
        try:
            error_payload = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as decode_exc:
            raise ProbeError(f"server returned HTTP {exc.code}") from decode_exc
        raise ProbeError(json.dumps(error_payload, sort_keys=True)) from exc
    except urllib.error.URLError as exc:
        raise ProbeError(str(exc)) from exc


def live_operator_token(args):
    env_name = getattr(args, "token_env", "KNUDG_OPERATOR_TOKEN") or "KNUDG_OPERATOR_TOKEN"
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]{1,80}", env_name):
        raise ConfigError("token env name rejected")
    token = os.environ.get(env_name) or ""
    if not token:
        raise ConfigError(f"{env_name} is required")
    return token


def live_post_json(origin, path, payload, token, *, extra_headers=None, timeout_seconds=5.0, max_bytes=262144):
    normalized = normalize_server_url(origin, "local")
    probe_json(normalized, "/health/live", timeout_seconds=min(timeout_seconds, 2.0))
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    if len(body) > max_bytes:
        raise ProbeError("request body exceeds live JSON limit")
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
    }
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(
        f"{normalized}{path}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read(max_bytes + 1)
            if len(response_body) > max_bytes:
                raise ProbeError("response body exceeds live JSON limit")
            return response.status, json.loads(response_body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_body = exc.read(max_bytes + 1)
        try:
            return exc.code, json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as decode_exc:
            raise ProbeError(f"server returned HTTP {exc.code}") from decode_exc
    except urllib.error.URLError as exc:
        raise ProbeError(str(exc)) from exc


def live_verdict(role, status, confidence, risk, reason_summary, recommended_action, *, refs=None, suppressed_detail="none"):
    payload = {
        "schema_version": "knudg_role_verdict.v0",
        "role": role,
        "status": status,
        "confidence": confidence,
        "risk": risk,
        "reason_summary": reason_summary,
        "recommended_action": recommended_action,
        "suppressed_detail": suppressed_detail,
    }
    if refs:
        payload["refs"] = refs
    return payload


def live_search_verdict(search_payload):
    result = search_payload.get("result") or {}
    cards = result.get("cards") or []
    if result.get("decision") != "cards_found" or not cards:
        return live_verdict(
            "nudger",
            "no_actionable_signal",
            "none",
            "none",
            "No low-noise Knudg retrieval offer is available.",
            "do_nothing",
        )
    refs = {
        "panel_ref": f"live-search:{hashlib.sha256(json.dumps([card.get('handoff_ref') for card in cards], sort_keys=True).encode('utf-8')).hexdigest()[:24]}",
        "card_refs": [card.get("handoff_ref") for card in cards if card.get("handoff_ref")][:3],
    }
    return live_verdict(
        "nudger",
        "suggestion_available",
        "medium",
        "low",
        "A live Knudg retrieval panel can be offered.",
        "offer_retrieval_panel",
        refs=refs,
    )


def live_writer_candidate_verdict(candidate_payload):
    artifact_digest = candidate_payload.get("artifact_digest")
    if candidate_payload.get("status") != "approval_required" or not artifact_digest:
        return live_verdict(
            "nudger",
            "degraded",
            "none",
            "none",
            "Live writer candidate could not be prepared safely.",
            "do_nothing",
            suppressed_detail="raw_or_private",
        )
    return live_verdict(
        "nudger",
        "draft_candidate_possible",
        "medium",
        "low",
        "A live Knudg write candidate can be offered for explicit approval.",
        "offer_writer_draft",
        refs={"artifact_digest": artifact_digest},
    )


def command_name(args):
    parts = [args.group]
    if getattr(args, "subcommand", None):
        parts.append(args.subcommand)
    if getattr(args, "action", None):
        parts.append(args.action)
    return " ".join(parts)


def migrate_status(args):
    try:
        with connect(args) as conn:
            exists = conn.execute("select to_regclass('public.schema_migrations') is not null as exists").fetchone()["exists"]
            rows = []
            if exists:
                rows = conn.execute(
                    "select version, checksum, state, started_at, finished_at, step, error_class from schema_migrations order by version"
                ).fetchall()
            return emit(command_name(args), "ok", EXIT_OK, migrations=rows, migration_table_exists=exists)
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def db_status(args):
    try:
        with connect(args) as conn:
            row = conn.execute(
                """
                select current_database() as database,
                  current_user as user_name,
                  now() as checked_at,
                  to_regclass('public.jobs') is not null as queue_schema_exists,
                  to_regclass('public.revocation_tombstones') is not null as revocation_schema_exists
                """
            ).fetchone()
            return emit(command_name(args), "ok", EXIT_OK, database=row)
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def db_backup_status(args):
    return emit(
        command_name(args),
        "not_configured",
        EXIT_NOT_CONFIGURED,
        required_operator_role="database_on_call",
        dry_run=False,
        audit_event="db_backup_status_checked",
        detail="Backup provider integration is not configured in local M0.",
    )


def db_pitr_plan(args):
    return emit(
        command_name(args),
        "not_configured",
        EXIT_NOT_CONFIGURED,
        required_operator_role="database_on_call",
        dry_run=True,
        audit_event="db_pitr_plan_requested",
        target=opaque_arg(args.target),
        detail="PITR provider integration is not configured in local M0.",
    )


def revocation_status(args):
    try:
        with connect(args) as conn:
            tombstones = conn.execute(
                """
                select subject_type, subject_id, card_id, card_version_id, revocation_epoch,
                  revocation_event_source_type, card_revocation_event_id, domain_revocation_event_id,
                  revoked_by, reason, created_at
                from revocation_tombstones
                where tenant_id = %s and card_id = %s
                order by created_at desc
                """,
                (args.tenant, args.card_id),
            ).fetchall()
            epoch = conn.execute(
                "select last_epoch from tenant_revocation_epochs where tenant_id = %s",
                (args.tenant,),
            ).fetchone()
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                tenant=args.tenant,
                card_id=args.card_id,
                revoked=bool(tombstones),
                tenant_revocation_epoch=epoch["last_epoch"] if epoch else 0,
                tombstones=tombstones,
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def reject_local_search_raw(value):
    if isinstance(value, str):
        for pattern in LOCAL_SEARCH_RAW_PATTERNS:
            if pattern.search(value):
                raise ValueError("task profile rejected")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("task profile rejected")
    elif isinstance(value, list):
        for item in value:
            reject_local_search_raw(item)
    elif isinstance(value, dict):
        for item in value.values():
            reject_local_search_raw(item)


def require_local_search_task_profile(value):
    if not isinstance(value, dict):
        raise ValueError("task profile rejected")
    if set(value) - LOCAL_SEARCH_ALLOWED_PROFILE_FIELDS:
        raise ValueError("task profile rejected")
    if value.get("schema_version") != "task_profile.v0":
        raise ValueError("task profile rejected")
    for field in ("explicit_query", "intent", "repo_shape_category", "recent_event_kinds"):
        if field not in value:
            raise ValueError("task profile rejected")
    if not isinstance(value["explicit_query"], str) or not value["explicit_query"].strip():
        raise ValueError("task profile rejected")
    if not isinstance(value["repo_shape_category"], str) or not value["repo_shape_category"].strip():
        raise ValueError("task profile rejected")
    if not isinstance(value["recent_event_kinds"], list) or not value["recent_event_kinds"]:
        raise ValueError("task profile rejected")
    reject_local_search_raw(value)
    try:
        retrieval_domains = normalize_retrieval_domains(value.get("retrieval_domains"))
    except DomainPolicyError as error:
        raise ValueError("task profile rejected") from error
    normalized = dict(value)
    normalized["retrieval_domains"] = retrieval_domains
    return normalized


def local_search_terms(task_profile):
    values = []
    for field in (
        "explicit_query",
        "repo_shape_category",
        "subsystems",
        "symbols",
        "error_fingerprints",
        "public_packages",
        "public_frameworks_tools",
        "language_runtime",
        "coarse_os",
        "dependency_major_versions",
        "risk_tags",
    ):
        value = task_profile.get(field)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
    terms = []
    for value in values:
        normalized = re.sub(r"[^a-z0-9_.:+/@-]+", " ", value.lower()).strip()
        if normalized:
            terms.extend(term for term in normalized.split() if len(term) >= 2)
    return sorted(set(terms))[:32]


def live_wire_task_profile(task_profile):
    payload = dict(task_profile)
    if payload.get("retrieval_domains") == ["technical_work"]:
        payload.pop("retrieval_domains")
    return payload


def retrieval_no_suggestion(reason, latency_budget_ms, *, served_from):
    return {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": reason,
        "served_from": served_from,
        "latency_budget_ms": latency_budget_ms,
        "cards": [],
    }


def validate_local_private_projection_payload_v0(payload):
    if payload.get("source_class") != "local_private_dogfood":
        raise ValueError("local private projection rejected")
    if payload.get("visibility") != "local_private":
        raise ValueError("local private projection rejected")
    if payload.get("sharing_state") != "not_shared":
        raise ValueError("local private projection rejected")
    if payload.get("publication_state") != "never_publishable":
        raise ValueError("local private projection rejected")
    if payload.get("privacy", {}).get("source_class") != "local_private_dogfood":
        raise ValueError("local private projection rejected")
    if payload.get("provenance", {}).get("source_class") != "local_private_dogfood":
        raise ValueError("local private projection rejected")


def local_private_projection_payload(card, body_digest):
    payload = {
        "source_class": "local_private_dogfood",
        "visibility": "local_private",
        "sharing_state": "not_shared",
        "publication_state": "never_publishable",
        "outcome_type": "solved",
        "goal": "closed launch private card",
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
    validate_local_private_projection_payload_v0(payload)
    return payload


def local_private_search_text(card):
    parts = [
        card["title"],
        card["problem_summary"],
        card["solution_summary"],
        *card["public_packages"],
        *card["environment_tags"],
        *card["public_reference_urls"],
        *card["command_labels"],
        *card["error_fingerprints"],
        *card["lessons"],
    ]
    return " ".join(part for part in parts if part).strip()


def local_private_record_event(conn, tenant_id, workspace_id, event_name, event_json, card_id=None, card_version_id=None):
    conn.execute(
        """
        insert into local_private_value_events(
          tenant_id, workspace_id, event_name, card_id, card_version_id, event_json
        )
        values (%s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            tenant_id,
            workspace_id,
            event_name,
            card_id,
            card_version_id,
            json.dumps(event_json, sort_keys=True),
        ),
    )


def local_private_capture(args):
    try:
        local_private_check_workspace(args.workspace)
        raw = Path(args.input).read_text(encoding="utf-8")
        card = validate_local_private_card_v0(json.loads(raw))
        body_digest = canonical_digest_hex(card)
        projection_payload = local_private_projection_payload(card, body_digest)
        payload_digest = canonical_digest_hex(projection_payload)
        card_id = uuid.uuid4()
        version_id = uuid.uuid4()
        search_text = local_private_search_text(card)
        with connect(args) as conn:
            with conn.transaction():
                local_private_require_namespace_scope(conn, args.tenant, [args.namespace], args.created_by, ("submit", "admin"))
                conn.execute(
                    """
                    insert into experience_cards(
                      tenant_id, id, namespace_id, current_version_id, status,
                      outcome_type, quality_state, evidence_strength, created_by
                    )
                    values (%s, %s, %s, %s, 'approved_private',
                      'solved', 'unreviewed', 'operator_judgment', %s)
                    """,
                    (args.tenant, card_id, args.namespace, version_id, args.created_by),
                )
                conn.execute(
                    """
                    insert into card_versions(
                      tenant_id, id, card_id, version_number, card_schema_version,
                      payload_json, payload_digest, created_by
                    )
                    values (%s, %s, %s, 1, 1, %s::jsonb, %s, %s)
                    """,
                    (
                        args.tenant,
                        version_id,
                        card_id,
                        json.dumps(projection_payload, sort_keys=True),
                        payload_digest,
                        args.created_by,
                    ),
                )
                conn.execute(
                    """
                    insert into local_private_card_bodies(
                      tenant_id, card_id, card_version_id, body_json, body_digest, created_by
                    )
                    values (%s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    (args.tenant, card_id, version_id, json.dumps(card, sort_keys=True), body_digest, args.created_by),
                )
                conn.execute(
                    """
                    insert into local_private_search_documents(
                      tenant_id, card_id, card_version_id, search_text, rank_manifest_version
                    )
                    values (%s, %s, %s, %s, 'local_private_fts_v0')
                    """,
                    (args.tenant, card_id, version_id, search_text),
                )
                local_private_record_event(
                    conn,
                    args.tenant,
                    args.workspace,
                    "capture_attempt",
                    {"result": "captured", "source_class": "local_private_dogfood"},
                    card_id,
                    version_id,
                )
        return emit(
            command_name(args),
            "captured",
            EXIT_OK,
            tenant=args.tenant,
            namespace=args.namespace,
            card_id=card_id,
            card_version_id=version_id,
            body_digest=body_digest,
            source_class="local_private_dogfood",
            protected_data_serving_enabled=False,
            publication_enabled=False,
        )
    except FileNotFoundError as exc:
        return emit(command_name(args), "usage_error", EXIT_USAGE, detail=f"input file not found: {Path(exc.filename).name}")
    except (LocalPrivateCardError, json.JSONDecodeError):
        return emit(command_name(args), "rejected", EXIT_REJECTED, reject_class="local_private_card")
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def local_private_panel_card(row, terms):
    text = row["search_text"].lower()
    matched_terms = [term for term in terms if term in text][:8]
    score = int(row["exact_hits"] or 0) + (1 if float(row["fts_rank"] or 0) > 0 else 0)
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
        "match_score": max(score, 1),
        "coarse_match_reason": matched_terms,
        "handoff_ref": f"local-card:{row['card_id']}:{row['card_version_id']}",
        "provenance": {
            "source": "closed launch private exact/FTS",
            "source_class": "local_private_dogfood",
        },
    }


def local_private_search(args):
    try:
        local_private_check_workspace(args.workspace)
        task_profile = require_local_search_task_profile(load_json_arg(args.task_profile))
        terms = local_search_terms(task_profile)
        if not terms:
            with connect(args) as conn:
                local_private_require_namespace_scope(conn, args.tenant, args.namespace, args.principal, ("read", "submit", "admin"))
            result = retrieval_no_suggestion(
                "low_confidence",
                args.latency_budget_ms,
                served_from="local_private_exact_fts",
            )
            return emit(command_name(args), "ok", EXIT_OK, tenant=args.tenant, namespaces=args.namespace, result=result)
        query_text = " ".join(terms)
        with connect(args) as conn:
            local_private_require_namespace_scope(conn, args.tenant, args.namespace, args.principal, ("read", "submit", "admin"))
            rows = conn.execute(
                """
                with active_docs as (
                  select c.tenant_id, c.id as card_id, c.namespace_id,
                    c.outcome_type, c.quality_state, c.evidence_strength,
                    d.card_version_id, d.search_text, d.search_vector,
                    cv.payload_digest, c.updated_at
                  from local_private_search_documents d
                  join experience_cards c
                    on c.tenant_id = d.tenant_id
                   and c.id = d.card_id
                  join card_versions cv
                    on cv.tenant_id = d.tenant_id
                   and cv.card_id = d.card_id
                   and cv.id = d.card_version_id
                  join local_private_card_bodies b
                    on b.tenant_id = d.tenant_id
                   and b.card_id = d.card_id
                   and b.card_version_id = d.card_version_id
                  where d.tenant_id = %s::uuid
                    and c.namespace_id = any(%s::uuid[])
                    and c.status = 'approved_private'
                    and d.lifecycle_status = 'captured'
                    and d.revoked_at is null
                    and d.purged_at is null
                    and b.lifecycle_status = 'captured'
                    and b.purged_at is null
                    and not exists (
                      select 1
                      from revocation_tombstones rt
                      where rt.tenant_id = c.tenant_id
                        and (
                          rt.subject_type = 'tenant'
                          or (rt.subject_type = 'namespace' and rt.namespace_id = c.namespace_id)
                          or (rt.subject_type = 'card' and rt.card_id = c.id)
                          or (rt.subject_type = 'card_version' and rt.card_version_id = d.card_version_id)
                        )
                    )
                ),
                scored as (
                  select *,
                    plainto_tsquery('english', %s) as query,
                    (
                      select count(*)::integer
                      from unnest(%s::text[]) as exact(term)
                      where lower(active_docs.search_text) like '%%' || exact.term || '%%'
                    ) as exact_hits
                  from active_docs
                )
                select tenant_id, card_id, namespace_id, outcome_type, quality_state,
                  evidence_strength, card_version_id, search_text, payload_digest,
                  exact_hits, ts_rank_cd(search_vector, query) as fts_rank
                from scored
                where exact_hits > 0 or search_vector @@ query
                order by exact_hits desc, ts_rank_cd(search_vector, query) desc, updated_at desc, card_id
                limit %s
                """,
                (args.tenant, args.namespace, query_text, terms, args.limit),
            ).fetchall()
            local_private_record_event(
                conn,
                args.tenant,
                args.workspace,
                "search_completed",
                {"result_count": len(rows), "served_from": "local_private_exact_fts"},
            )
        cards = []
        for row in rows:
            card = local_private_panel_card(row, terms)
            if card["match_score"] >= args.min_score:
                cards.append(card)
        if cards:
            result = {
                "decision": "cards_found",
                "delivery_mode": "retrieval_panel",
                "served_from": "local_private_exact_fts",
                "latency_budget_ms": args.latency_budget_ms,
                "cards": cards[:3],
            }
        else:
            result = retrieval_no_suggestion(
                "no_authorized_match",
                args.latency_budget_ms,
                served_from="local_private_exact_fts",
            )
        return emit(
            command_name(args),
            "ok",
            EXIT_OK,
            tenant=args.tenant,
            namespaces=args.namespace,
            result=result,
            protected_data_serving_enabled=False,
            publication_enabled=False,
            public_search_enabled=False,
            vector_search_enabled=False,
        )
    except FileNotFoundError as exc:
        return emit(command_name(args), "usage_error", EXIT_USAGE, detail=f"input file not found: {Path(exc.filename).name}")
    except (ValueError, json.JSONDecodeError):
        return emit(command_name(args), "rejected", EXIT_REJECTED, reject_class="task_profile")
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def local_private_revoke(args):
    try:
        local_private_check_workspace(args.workspace)
        with connect(args) as conn:
            with conn.transaction():
                local_private_require_namespace_scope(conn, args.tenant, args.namespace, args.principal, ("submit", "admin"))
                row = conn.execute(
                    """
                    update local_private_search_documents d
                    set lifecycle_status = 'revoked', revoked_at = coalesce(revoked_at, now())
                    from experience_cards c
                    where c.tenant_id = d.tenant_id
                      and c.id = d.card_id
                      and d.tenant_id = %s::uuid
                      and d.card_id = %s::uuid
                      and c.namespace_id = any(%s::uuid[])
                      and d.lifecycle_status = 'captured'
                      and d.purged_at is null
                    returning d.card_id, d.card_version_id
                    """,
                    (args.tenant, args.card_id, args.namespace),
                ).fetchone()
                if row:
                    conn.execute(
                        """
                        update local_private_card_bodies
                        set lifecycle_status = 'revoked'
                        where tenant_id = %s::uuid and card_id = %s::uuid and card_version_id = %s::uuid
                          and lifecycle_status = 'captured' and purged_at is null
                        """,
                        (args.tenant, args.card_id, row["card_version_id"]),
                    )
                    conn.execute(
                        """
                        update experience_cards
                        set status = 'revoked', updated_at = now()
                        where tenant_id = %s::uuid and id = %s::uuid
                        """,
                        (args.tenant, args.card_id),
                    )
                    local_private_record_event(
                        conn,
                        args.tenant,
                        args.workspace,
                        "revoke_completed",
                        {"reason_digest": hashlib.sha256(args.reason.encode("utf-8")).hexdigest()},
                        row["card_id"],
                        row["card_version_id"],
                    )
        return emit(
            command_name(args),
            "revoked",
            EXIT_OK,
            tenant=args.tenant,
            card_id=args.card_id,
            revoked=bool(row),
            protected_data_serving_enabled=False,
            publication_enabled=False,
        )
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def local_private_purge(args):
    try:
        local_private_check_workspace(args.workspace)
        with connect(args) as conn:
            with conn.transaction():
                local_private_require_namespace_scope(conn, args.tenant, args.namespace, args.principal, ("submit", "admin"))
                row = conn.execute(
                    """
                    select d.card_id, d.card_version_id
                    from local_private_search_documents d
                    join experience_cards c on c.tenant_id = d.tenant_id and c.id = d.card_id
                    where d.tenant_id = %s::uuid
                      and d.card_id = %s::uuid
                      and c.namespace_id = any(%s::uuid[])
                    order by d.created_at desc
                    limit 1
                    """,
                    (args.tenant, args.card_id, args.namespace),
                ).fetchone()
                if row:
                    conn.execute(
                        """
                        update local_private_search_documents
                        set lifecycle_status = 'purged', search_text = '', revoked_at = null, purged_at = coalesce(purged_at, now())
                        where tenant_id = %s::uuid and card_id = %s::uuid and card_version_id = %s::uuid
                        """,
                        (args.tenant, args.card_id, row["card_version_id"]),
                    )
                    conn.execute(
                        """
                        update local_private_card_bodies
                        set lifecycle_status = 'purged', body_json = '{}'::jsonb, purged_at = coalesce(purged_at, now())
                        where tenant_id = %s::uuid and card_id = %s::uuid and card_version_id = %s::uuid
                        """,
                        (args.tenant, args.card_id, row["card_version_id"]),
                    )
                    conn.execute(
                        """
                        update experience_cards
                        set status = 'revoked', updated_at = now()
                        where tenant_id = %s::uuid and id = %s::uuid
                        """,
                        (args.tenant, args.card_id),
                    )
                    local_private_record_event(
                        conn,
                        args.tenant,
                        args.workspace,
                        "purge_completed",
                        {"reason_digest": hashlib.sha256(args.reason.encode("utf-8")).hexdigest()},
                        row["card_id"],
                        row["card_version_id"],
                    )
        return emit(
            command_name(args),
            "purged",
            EXIT_OK,
            tenant=args.tenant,
            card_id=args.card_id,
            purged=bool(row),
            protected_data_serving_enabled=False,
            publication_enabled=False,
        )
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def local_private_preflight_db(args):
    required_tables = (
        "local_private_card_bodies",
        "local_private_search_documents",
        "local_private_value_events",
    )
    required_indexes = (
        "local_private_card_bodies_active_card_idx",
        "local_private_search_documents_fts_idx",
        "local_private_search_documents_active_idx",
        "local_private_value_events_workspace_idx",
    )
    try:
        with connect(args) as conn:
            table_rows = conn.execute(
                """
                select name as relname
                from unnest(%s::text[]) as required(name)
                where to_regclass(name) is not null
                """,
                ([*required_tables],),
            ).fetchall()
            index_rows = conn.execute(
                """
                select name as relname
                from unnest(%s::text[]) as required(name)
                where to_regclass(name) is not null
                """,
                ([*required_indexes],),
            ).fetchall()
            rls_rows = conn.execute(
                """
                select relname, relrowsecurity, relforcerowsecurity
                from pg_class
                where oid in (
                  select to_regclass(name)
                  from unnest(%s::text[]) as required(name)
                  where to_regclass(name) is not null
                )
                order by relname
                """,
                ([*required_tables],),
            ).fetchall()
            migration_rows = conn.execute(
                """
                select version, checksum, state
                from schema_migrations
                where version in ('0001_m0_schema','0002_local_private_dogfood','0003_local_private_payload_contract')
                order by version
                """
            ).fetchall()
            db_row = conn.execute(
                """
                select current_database() as database,
                  current_user as user_name,
                  current_setting('server_version') as server_version,
                  current_setting('server_version_num')::integer as server_version_num,
                  current_setting('server_encoding') as server_encoding,
                  current_setting('default_text_search_config') as default_text_search_config,
                  d.datcollate as database_collation,
                  d.datctype as database_ctype
                from pg_database d
                where d.datname = current_database()
                """
            ).fetchone()
            extension_rows = conn.execute(
                """
                select e.extname, n.nspname as schema_name, e.extversion
                from pg_extension e
                join pg_namespace n on n.oid = e.extnamespace
                where e.extname in ('pgcrypto')
                order by e.extname
                """
            ).fetchall()
        present = {row["relname"] for row in table_rows}
        missing = sorted(set(required_tables) - present)
        present_indexes = {row["relname"] for row in index_rows}
        missing_indexes = sorted(set(required_indexes) - present_indexes)
        rls = {
            row["relname"]: {
                "row_security": row["relrowsecurity"],
                "force_row_security": row["relforcerowsecurity"],
            }
            for row in rls_rows
        }
        rls_ready = all(value["row_security"] and value["force_row_security"] for value in rls.values())
        applied_migrations = [dict(row) for row in migration_rows if row["state"] == "applied"]
        missing_migrations = sorted(
            set(("0001_m0_schema", "0002_local_private_dogfood", "0003_local_private_payload_contract"))
            - {row["version"] for row in applied_migrations}
        )
        migration_material = "\n".join(f"{row['version']}:{row['checksum']}" for row in applied_migrations)
        migration_hash = hashlib.sha256(migration_material.encode("utf-8")).hexdigest() if migration_material else None
        extensions = {row["extname"]: {"schema": row["schema_name"], "version": row["extversion"]} for row in extension_rows}
        extensions_ready = extensions.get("pgcrypto", {}).get("schema") == "knudg_crypto"
        local_private_schema_ready = not missing and not missing_indexes and rls_ready and not missing_migrations and extensions_ready
        return emit(
            command_name(args),
            "ok" if local_private_schema_ready else "preflight_failed",
            EXIT_OK if local_private_schema_ready else EXIT_LOCAL_DB_FAILURE,
            missing=missing,
            missing_indexes=missing_indexes,
            missing_migrations=missing_migrations,
            local_private_schema_ready=local_private_schema_ready,
            postgres={
                "database": db_row["database"],
                "user_name": db_row["user_name"],
                "server_version": db_row["server_version"],
                "server_version_num": db_row["server_version_num"],
                "server_encoding": db_row["server_encoding"],
                "database_collation": db_row["database_collation"],
                "database_ctype": db_row["database_ctype"],
                "default_text_search_config": db_row["default_text_search_config"],
            },
            extensions=extensions,
            migration_hash=migration_hash,
            migrations=applied_migrations,
            rls=rls,
            fts={"config": "english", "rank_manifest_version": "local_private_fts_v0"},
        )
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def local_private_verify_fences(args):
    try:
        with connect(args) as conn:
            ns_row = conn.execute(
                "select namespace_id from experience_cards where tenant_id = %s::uuid and id = %s::uuid",
                (args.tenant, args.card_id),
            ).fetchone()
            if not ns_row:
                raise PermissionError("local card binding rejected")
            local_private_require_namespace_scope(conn, args.tenant, [ns_row["namespace_id"]], args.principal, ("read", "submit", "admin"))
            row = conn.execute(
                """
                select
                  count(*) filter (
                    where d.lifecycle_status = 'captured'
                      and d.revoked_at is null
                      and d.purged_at is null
                      and c.status = 'approved_private'
                  )::integer as active_search_documents,
                  count(*) filter (
                    where b.lifecycle_status = 'captured'
                      and b.purged_at is null
                  )::integer as active_bodies,
                  count(*) filter (
                    where b.lifecycle_status = 'purged'
                      and b.body_json = '{}'::jsonb
                  )::integer as purged_bodies
                from local_private_search_documents d
                join experience_cards c on c.tenant_id = d.tenant_id and c.id = d.card_id
                join local_private_card_bodies b
                  on b.tenant_id = d.tenant_id
                 and b.card_id = d.card_id
                 and b.card_version_id = d.card_version_id
                where d.tenant_id = %s::uuid and d.card_id = %s::uuid
                """,
                (args.tenant, args.card_id),
            ).fetchone()
        return emit(
            command_name(args),
            "ok",
            EXIT_OK,
            tenant=args.tenant,
            card_id=args.card_id,
            active_search_documents=row["active_search_documents"],
            active_bodies=row["active_bodies"],
            purged_bodies=row["purged_bodies"],
            publication_enabled=False,
        )
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def local_private_audit_boundary(args):
    try:
        with connect(args) as conn:
            local_private_require_tenant_membership(conn, args.tenant, args.principal)
            row = conn.execute(
                """
                with local_versions as (
                  select tenant_id, card_id, card_version_id
                  from local_private_card_bodies
                  where (%s::uuid is null or tenant_id = %s::uuid)
                )
                select
                  (select count(*) from consent_records cr join local_versions lv
                    on lv.tenant_id = cr.tenant_id and lv.card_version_id = cr.card_version_id)::integer as consent_records,
                  (select count(*) from approval_handoffs ah join local_versions lv
                    on lv.tenant_id = ah.tenant_id and lv.card_version_id = ah.card_version_id)::integer as approval_handoffs,
                  (select count(*) from jobs j join local_versions lv
                    on lv.tenant_id = j.tenant_id
                   where j.payload_json::text like '%%' || lv.card_version_id::text || '%%')::integer as jobs,
                  (select count(*) from outbox_events oe join local_versions lv
                    on lv.tenant_id = oe.tenant_id
                   where oe.payload_json::text like '%%' || lv.card_version_id::text || '%%')::integer as outbox_events
                """,
                (args.tenant, args.tenant),
            ).fetchone()
            future_surfaces = {}
            for table_name in LOCAL_PRIVATE_FUTURE_BOUNDARY_TABLES:
                exists = conn.execute("select to_regclass(%s) is not null as exists", (table_name,)).fetchone()["exists"]
                future_surfaces[table_name] = "not_present" if not exists else "requires_manual_query"
        leaks = {key: row[key] for key in row if row[key]}
        return emit(
            command_name(args),
            "ok" if not leaks else "boundary_violation",
            EXIT_OK if not leaks else EXIT_UNAVAILABLE,
            tenant=args.tenant,
            leaks=leaks,
            checked_surfaces={key: ("violation" if row[key] else "clear") for key in row},
            future_surfaces=future_surfaces,
            local_private_publication_boundary_clear=not leaks,
            publication_enabled=False,
        )
    except PermissionError:
        return emit(command_name(args), "fence_failed", EXIT_UNAVAILABLE, fence="local_principal_binding")
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_LOCAL_DB_FAILURE, error_class=exc.__class__.__name__, detail=str(exc))


def queue_stats(args):
    try:
        with connect(args) as conn:
            params = []
            where = ""
            if args.lane:
                where = "where lane = %s"
                params.append(args.lane)
            rows = conn.execute(
                f"""
                select lane, status, count(*)::bigint as count,
                  min(created_at) as oldest_created_at,
                  min(available_at) filter (where status = 'ready') as oldest_ready_at
                from jobs
                {where}
                group by lane, status
                order by lane, status
                """,
                params,
            ).fetchall()
            return emit(command_name(args), "ok", EXIT_OK, all=args.all, lane=args.lane, queues=rows)
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def queue_peek(args):
    try:
        with connect(args) as conn:
            rows = conn.execute(
                """
                select id, lane, status, priority, payload_digest, idempotency_key,
                  outbox_event_id, attempts, max_attempts, available_at, lease_expires_at,
                  last_error_class, last_error_detail, created_at, updated_at
                from jobs
                where lane = %s
                order by created_at asc
                limit %s
                """,
                (args.lane, args.oldest),
            ).fetchall()
            return emit(command_name(args), "ok", EXIT_OK, lane=args.lane, jobs=rows)
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def queue_redrive(args):
    return emit(
        command_name(args),
        "not_configured",
        EXIT_NOT_CONFIGURED,
        dry_run=args.dry_run,
        apply=args.apply,
        required_operator_role="platform_on_call",
        audit_event="queue_redrive_requested",
        job=args.job,
        reason=opaque_arg(args.reason),
        detail="Queue redrive mutation is not configured until reconciliation commands are implemented.",
    )


def _tenant_filter_sql(args, alias):
    if getattr(args, "tenant", None):
        return f" and {alias}.tenant_id = %s", [args.tenant]
    return "", []


def writer_status(args):
    try:
        with connect(args) as conn:
            card_filter, card_params = _tenant_filter_sql(args, "c")
            card_rows = conn.execute(
                f"""
                select c.status, count(*)::bigint as count,
                  min(c.updated_at) as oldest_updated_at
                from experience_cards c
                where c.status = any(%s){card_filter}
                group by c.status
                order by c.status
                """,
                [list(WRITER_CARD_STATUSES), *card_params],
            ).fetchall()
            job_filter, job_params = _tenant_filter_sql(args, "j")
            job_rows = conn.execute(
                f"""
                select j.lane, j.status, count(*)::bigint as count,
                  min(j.available_at) filter (where j.status = 'ready') as oldest_ready_at,
                  min(j.lease_expires_at) filter (where j.status = 'leased') as oldest_lease_expires_at
                from jobs j
                where j.lane = any(%s){job_filter}
                group by j.lane, j.status
                order by j.lane, j.status
                """,
                [list(WRITER_JOB_LANES), *job_params],
            ).fetchall()
            challenge_filter, challenge_params = _tenant_filter_sql(args, "ac")
            challenge_row = conn.execute(
                f"""
                select count(*)::bigint as active_private_approval_challenges,
                  min(ac.expires_at) as next_private_approval_expiry
                from approval_challenges ac
                where ac.consent_scope = 'private_retention'
                  and ac.used_at is null
                  and ac.invalidated_at is null
                  and ac.expires_at > now(){challenge_filter}
                """,
                challenge_params,
            ).fetchone()
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                tenant=args.tenant,
                card_statuses=card_rows,
                queues=job_rows,
                approval_challenges=challenge_row,
                protected_data_serving_enabled=False,
                publication_enabled=False,
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def writer_reconcile(args):
    if args.apply:
        return emit(
            command_name(args),
            "not_configured",
            EXIT_NOT_CONFIGURED,
            dry_run=False,
            apply=True,
            required_operator_role="platform_on_call",
            audit_event="writer_reconcile_requested",
            detail="Apply mode is not configured in local M1 writer orchestration.",
        )
    try:
        with connect(args) as conn:
            card_filter, card_params = _tenant_filter_sql(args, "c")
            rows = conn.execute(
                f"""
                select c.tenant_id, c.id as card_id, c.namespace_id, c.status,
                  c.current_version_id, cv.payload_digest,
                  case c.status
                    when 'candidate_created' then 'accept_admission'
                    when 'deferred' then 'accept_admission_or_keep_deferred'
                    when 'pending_admission' then 'request_redaction'
                    when 'pending_redaction' then 'complete_redaction'
                    when 'pending_review' then 'request_private_approval'
                    when 'awaiting_user_approval' then 'wait_for_human_private_retention_approval'
                  end as recommended_next_action,
                  c.updated_at
                from experience_cards c
                join card_versions cv
                  on cv.tenant_id = c.tenant_id
                 and cv.card_id = c.id
                 and cv.id = c.current_version_id
                where c.status = any(%s){card_filter}
                order by c.updated_at asc, c.id
                limit %s
                """,
                [list(WRITER_CARD_STATUSES), *card_params, args.limit],
            ).fetchall()
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                dry_run=True,
                apply=False,
                tenant=args.tenant,
                limit=args.limit,
                candidates=rows,
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="writer_reconcile_requested",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def writer_job_plan(row):
    status = row["status"]
    if status in {"candidate_created", "deferred"}:
        operation = "accept_admission"
        lane = "public_candidate_ingest"
        worker_role = "ingestion_worker"
    elif status == "pending_admission":
        operation = "request_redaction"
        lane = "redaction"
        worker_role = "ingestion_worker"
    elif status == "pending_redaction":
        operation = "complete_redaction"
        lane = "redaction"
        worker_role = "redaction_worker"
    elif status == "pending_review":
        operation = "request_private_approval"
        lane = "review"
        worker_role = "review_worker"
    else:
        raise ValueError(f"unsupported writer status: {status}")

    payload = {
        "schema_version": "writer-orchestration-job-v0",
        "operation": operation,
        "worker_role": worker_role,
        "card_id": str(row["card_id"]),
        "current_version_id": str(row["current_version_id"]),
        "source_status": status,
        "requires_human_completion": False,
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
    }
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {
        "tenant_id": row["tenant_id"],
        "card_id": row["card_id"],
        "current_version_id": row["current_version_id"],
        "event_stream_position": row["event_stream_position"],
        "source_status": status,
        "operation": operation,
        "lane": lane,
        "worker_role": worker_role,
        "payload": payload,
        "payload_digest": "sha256:" + hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
        "idempotency_key": f"writer:{operation}:{row['card_id']}:{row['current_version_id']}",
    }


def writer_enqueue_next(args):
    try:
        with connect(args) as conn:
            plans = writer_plan_candidates(conn, args)
            results = []
            for plan in plans:
                if args.apply:
                    existing, action = enqueue_writer_plan(
                        conn,
                        plan,
                        priority=args.priority,
                        max_attempts=args.max_attempts,
                    )
                else:
                    existing = conn.execute(
                        """
                        select id as outbox_event_id, job_id, event_stream_position, lane, status
                        from outbox_events
                        where tenant_id = %s and lane = %s and idempotency_key = %s
                        """,
                        (plan["tenant_id"], plan["lane"], plan["idempotency_key"]),
                    ).fetchone()
                    action = "already_enqueued" if existing is not None else "would_enqueue"
                if existing is None:
                    action = "would_enqueue"

                results.append(
                    {
                        "tenant_id": plan["tenant_id"],
                        "card_id": plan["card_id"],
                        "current_version_id": plan["current_version_id"],
                        "event_stream_position": plan["event_stream_position"],
                        "source_status": plan["source_status"],
                        "operation": plan["operation"],
                        "lane": plan["lane"],
                        "worker_role": plan["worker_role"],
                        "payload_digest": plan["payload_digest"],
                        "idempotency_key_digest": hashlib.sha256(plan["idempotency_key"].encode("utf-8")).hexdigest(),
                        "action": action,
                        "outbox_event_id": existing["outbox_event_id"] if existing else None,
                        "job_id": existing["job_id"] if existing else None,
                    }
                )
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                dry_run=args.dry_run,
                apply=args.apply,
                tenant=args.tenant,
                limit=args.limit,
                priority=args.priority,
                max_attempts=args.max_attempts,
                planned_count=len(results),
                jobs=results,
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="writer_enqueue_next_requested",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def writer_plan_candidates(conn, args):
    card_filter, card_params = _tenant_filter_sql(args, "c")
    rows = conn.execute(
        f"""
        select c.tenant_id, c.id as card_id, c.namespace_id, c.status,
          c.current_version_id, cv.payload_digest,
          (
            select max(ce.event_stream_position)
            from card_events ce
            where ce.tenant_id = c.tenant_id and ce.card_id = c.id
          ) as event_stream_position,
          c.updated_at
        from experience_cards c
        join card_versions cv
          on cv.tenant_id = c.tenant_id
         and cv.card_id = c.id
         and cv.id = c.current_version_id
        where c.status = any(%s){card_filter}
        order by c.updated_at asc, c.id
        limit %s
        """,
        [list(WRITER_ENQUEUE_STATUSES), *card_params, args.limit],
    ).fetchall()
    return [writer_job_plan(row) for row in rows if row["event_stream_position"] is not None]


def enqueue_writer_plan(conn, plan, *, priority, max_attempts):
    existing = conn.execute(
        """
        select id as outbox_event_id, job_id, event_stream_position, lane, status
        from outbox_events
        where tenant_id = %s and lane = %s and idempotency_key = %s
        """,
        (plan["tenant_id"], plan["lane"], plan["idempotency_key"]),
    ).fetchone()
    if existing is not None:
        return existing, "already_enqueued"
    outbox_event_id = uuid.uuid4()
    job_id = uuid.uuid4()
    conn.execute(
        """
        insert into outbox_events(
          tenant_id, id, event_stream_position, lane, status, payload_json,
          payload_digest, idempotency_key, job_id
        )
        values (%s, %s, %s, %s, 'job_enqueued', %s::jsonb, %s, %s, %s)
        """,
        (
            plan["tenant_id"],
            outbox_event_id,
            plan["event_stream_position"],
            plan["lane"],
            json.dumps(plan["payload"], sort_keys=True),
            plan["payload_digest"],
            plan["idempotency_key"],
            job_id,
        ),
    )
    conn.execute(
        """
        insert into jobs(
          tenant_id, id, lane, status, priority, payload_json,
          payload_digest, idempotency_key, outbox_event_id, max_attempts
        )
        values (%s, %s, %s, 'ready', %s, %s::jsonb, %s, %s, %s, %s)
        """,
        (
            plan["tenant_id"],
            job_id,
            plan["lane"],
            priority,
            json.dumps(plan["payload"], sort_keys=True),
            plan["payload_digest"],
            plan["idempotency_key"],
            outbox_event_id,
            max_attempts,
        ),
    )
    return {
        "outbox_event_id": outbox_event_id,
        "job_id": job_id,
        "event_stream_position": plan["event_stream_position"],
        "lane": plan["lane"],
        "status": "job_enqueued",
    }, "enqueued"


def _writer_ready_job_filter(args):
    clauses = ["j.status = 'ready'", "j.available_at <= now()", "j.lane = any(%s)"]
    params = [list(WRITER_RUN_LANES)]
    if getattr(args, "tenant", None):
        clauses.append("j.tenant_id = %s")
        params.append(args.tenant)
    return " and ".join(clauses), params


def writer_next_ready_job(conn, args):
    where, params = _writer_ready_job_filter(args)
    return conn.execute(
        f"""
        select j.tenant_id, j.id as job_id, j.lane, j.status, j.priority,
          j.payload_digest, j.idempotency_key, j.outbox_event_id, j.attempts,
          j.max_attempts, j.available_at, j.created_at,
          j.payload_json->>'operation' as operation,
          j.payload_json->>'worker_role' as worker_role,
          j.payload_json->>'card_id' as card_id,
          j.payload_json->>'current_version_id' as current_version_id,
          j.payload_json->>'source_status' as source_status
        from jobs j
        where {where}
        order by j.priority desc, j.available_at, j.created_at
        limit 1
        """,
        params,
    ).fetchone()


def writer_safe_job_view(row, *, action):
    if row is None:
        return None
    return {
        "tenant_id": row["tenant_id"],
        "job_id": row["job_id"],
        "lane": row["lane"],
        "status": row["status"],
        "priority": row["priority"],
        "payload_digest": row["payload_digest"],
        "idempotency_key_digest": hashlib.sha256(row["idempotency_key"].encode("utf-8")).hexdigest(),
        "outbox_event_id": row["outbox_event_id"],
        "attempts": row["attempts"],
        "max_attempts": row["max_attempts"],
        "available_at": row["available_at"],
        "operation": row["operation"],
        "worker_role": row["worker_role"],
        "card_id": row["card_id"],
        "current_version_id": row["current_version_id"],
        "source_status": row["source_status"],
        "action": action,
    }


def _bytes(value):
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)


def local_worker_claim_context(conn, tenant_id, worker_role, allowed_operations):
    worker_subject = f"knudgctl:closed-launch-writer:{tenant_id}:{worker_role}"
    worker = conn.execute(
        """
        select id
        from principals
        where principal_type = 'worker'
          and external_subject = %s
          and disabled_at is null
        order by created_at
        limit 1
        """,
        (worker_subject,),
    ).fetchone()
    if worker:
        worker_id = worker["id"]
    else:
        worker_id = uuid.uuid4()
        conn.execute(
            """
            insert into principals(id, principal_type, display_name, external_subject)
            values (%s, 'worker', 'knudgctl closed-launch writer worker', %s)
            """,
            (worker_id, worker_subject),
        )
    membership = conn.execute(
        """
        select id
        from tenant_memberships
        where tenant_id = %s and principal_id = %s and membership_role = 'worker'
          and status = 'active'
        limit 1
        """,
        (tenant_id, worker_id),
    ).fetchone()
    if not membership:
        conn.execute(
            """
            insert into tenant_memberships(tenant_id, id, principal_id, membership_role, status, valid_from)
            values (%s, %s, %s, 'worker', 'active', now() - interval '1 minute')
            """,
            (tenant_id, uuid.uuid4(), worker_id),
        )
    operations = sorted(set(allowed_operations))
    identity = conn.execute(
        """
        select id, allowed_operations
        from worker_identities
        where principal_id = %s and worker_role = %s
        limit 1
        """,
        (worker_id, worker_role),
    ).fetchone()
    if identity:
        existing_operations = set(identity.get("allowed_operations") or [])
        operations = sorted(existing_operations | set(operations))
        conn.execute(
            """
            update worker_identities
            set allowed_operations = %s
            where id = %s
            """,
            (operations, identity["id"]),
        )
    else:
        conn.execute(
            """
            insert into worker_identities(id, principal_id, worker_role, purpose, allowed_operations)
            values (%s, %s, %s, 'closed-launch writer runner', %s)
            """,
            (uuid.uuid4(), worker_id, worker_role, operations),
        )

    key = conn.execute(
        """
        select kid, verify_secret
        from claim_signing_keys
        where alg = 'HS256'
          and disabled_at is null
          and not_before <= now()
          and (not_after is null or not_after > now())
        order by created_at desc
        limit 1
        """
    ).fetchone()
    if not key:
        raise RuntimeError("local HS256 claim signing key is not configured")

    payload = {
        "audience": "knudg-db-local-m0",
        "request_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "principal_id": str(worker_id),
        "actor_role": worker_role,
        "namespace_ids": [],
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(_bytes(key["verify_secret"]), payload_text.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "alg": "HS256",
        "kid": key["kid"],
        "payload": payload_text,
        "signature": signature,
    }


def set_local_worker_claims(conn, tenant_id, worker_role, operation):
    allowed = ["claim_job", "complete_job", "fail_job", operation]
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(local_worker_claim_context(conn, tenant_id, worker_role, allowed)),))


def writer_job_event_payload(operation, job_id):
    payload = {
        "schema_version": "writer-worker-event-v0",
        "operation": operation,
        "job_id": str(job_id),
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
    }
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, "sha256:" + hashlib.sha256(payload_text.encode("utf-8")).hexdigest()


def validate_writer_job_payload(job):
    operation = job["payload_json"].get("operation")
    spec = WRITER_RUN_OPERATIONS.get(operation)
    if not spec:
        raise ValueError("unsupported writer operation")
    if job["lane"] != spec["lane"]:
        raise ValueError("writer job lane does not match operation")
    if job["payload_json"].get("worker_role") != spec["worker_role"]:
        raise ValueError("writer job worker role does not match operation")
    if not job["payload_json"].get("card_id") or not job["payload_json"].get("current_version_id"):
        raise ValueError("writer job is missing opaque card metadata")
    return operation, spec


def dispatch_writer_job(conn, job):
    operation, spec = validate_writer_job_payload(job)
    card_id = job["payload_json"]["card_id"]
    current_version_id = job["payload_json"]["current_version_id"]
    event_payload, event_payload_digest = writer_job_event_payload(operation, job["job_id"])
    correlation_id = uuid.uuid4()
    request_digest = "sha256:" + hashlib.sha256(
        f"{job['payload_digest']}:{job['idempotency_key']}".encode("utf-8")
    ).hexdigest()

    if operation in {"accept_admission", "request_redaction"}:
        return conn.execute(
            f"""
            select event_id, event_stream_position, event_seq, card_id, previous_status,
              next_status, current_version_id
            from {spec["function"]}(%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                card_id,
                current_version_id,
                job["idempotency_key"],
                request_digest,
                correlation_id,
                json.dumps(event_payload, sort_keys=True),
                event_payload_digest,
            ),
        ).fetchone()
    if operation == "complete_redaction":
        return conn.execute(
            """
            select event_id, event_stream_position, event_seq, card_id, previous_status,
              next_status, current_version_id
            from knudg_complete_redaction(%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                card_id,
                current_version_id,
                None,
                None,
                job["idempotency_key"],
                request_digest,
                correlation_id,
                json.dumps(event_payload, sort_keys=True),
                event_payload_digest,
            ),
        ).fetchone()
    if operation == "request_private_approval":
        challenge_id = uuid.uuid4()
        challenge_material = json.dumps(
            {
                "schema_version": "local-private-approval-challenge-v0",
                "card_id": str(card_id),
                "current_version_id": str(current_version_id),
                "job_id": str(job["job_id"]),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        challenge_digest = "sha256:" + hashlib.sha256(challenge_material.encode("utf-8")).hexdigest()
        policy_digest = "sha256:" + hashlib.sha256(b"local-private-retention-v0").hexdigest()
        return conn.execute(
            """
            select event_id, event_stream_position, event_seq, card_id, previous_status,
              next_status, current_version_id, challenge_id, challenge_digest
            from knudg_request_private_approval(
              %s, %s, %s, 'local-private-retention-v0', %s, %s,
              'closed-launch-writer-runner', now() + interval '1 day',
              %s, %s, %s, %s::jsonb, %s
            )
            """,
            (
                card_id,
                current_version_id,
                challenge_id,
                policy_digest,
                challenge_digest,
                job["idempotency_key"],
                request_digest,
                correlation_id,
                json.dumps(event_payload, sort_keys=True),
                event_payload_digest,
            ),
        ).fetchone()
    raise ValueError("unsupported writer operation")


def writer_run_next(args):
    try:
        with connect(args) as conn:
            preview = writer_next_ready_job(conn, args)
            if preview is None:
                return emit(
                    command_name(args),
                    "ok",
                    EXIT_OK,
                    dry_run=args.dry_run,
                    apply=args.apply,
                    tenant=args.tenant,
                    lease_seconds=args.lease_seconds,
                    action="no_job",
                    job=None,
                    protected_data_serving_enabled=False,
                    publication_enabled=False,
                    audit_event="writer_run_next_requested",
                )
            if args.dry_run:
                return emit(
                    command_name(args),
                    "ok",
                    EXIT_OK,
                    dry_run=True,
                    apply=False,
                    tenant=args.tenant,
                    lease_seconds=args.lease_seconds,
                    job=writer_safe_job_view(preview, action="would_claim"),
                    protected_data_serving_enabled=False,
                    publication_enabled=False,
                    audit_event="writer_run_next_requested",
                )

            operation = preview["operation"]
            spec = WRITER_RUN_OPERATIONS.get(operation)
            if not spec:
                return emit(
                    command_name(args),
                    "usage_error",
                    EXIT_USAGE,
                    dry_run=False,
                    apply=True,
                    tenant=args.tenant,
                    job=writer_safe_job_view(preview, action="unsupported_operation"),
                    detail="unsupported writer operation",
                )

            set_local_worker_claims(conn, preview["tenant_id"], spec["worker_role"], operation)
            claimed = conn.execute(
                """
                select job_id, lane, attempt_number, payload_json, payload_digest, lease_expires_at
                from knudg_claim_job_by_id(%s, %s)
                """,
                (preview["job_id"], args.lease_seconds),
            ).fetchone()
            if claimed is None:
                return emit(
                    command_name(args),
                    "ok",
                    EXIT_OK,
                    dry_run=False,
                    apply=True,
                    tenant=args.tenant,
                    lease_seconds=args.lease_seconds,
                    action="no_job",
                    job=None,
                    protected_data_serving_enabled=False,
                    publication_enabled=False,
                    audit_event="writer_run_next_requested",
                )
            claimed_job_id = claimed["job_id"]
        with connect(args) as conn:
            job = conn.execute(
                """
                select tenant_id, id as job_id, lane, status, priority, payload_json,
                  payload_digest, idempotency_key, outbox_event_id, attempts,
                  max_attempts, lease_expires_at
                from jobs
                where tenant_id = %s and id = %s
                """,
                (preview["tenant_id"], claimed_job_id),
            ).fetchone()
            operation, spec = validate_writer_job_payload(job)
            set_local_worker_claims(conn, job["tenant_id"], spec["worker_role"], operation)
            transition = dispatch_writer_job(conn, job)
            completed = conn.execute(
                "select job_id, status from knudg_complete_job(%s)",
                (job["job_id"],),
            ).fetchone()
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                dry_run=False,
                apply=True,
                tenant=args.tenant,
                lease_seconds=args.lease_seconds,
                job={
                    "tenant_id": job["tenant_id"],
                    "job_id": job["job_id"],
                    "lane": job["lane"],
                    "operation": operation,
                    "worker_role": spec["worker_role"],
                    "payload_digest": job["payload_digest"],
                    "idempotency_key_digest": hashlib.sha256(job["idempotency_key"].encode("utf-8")).hexdigest(),
                    "attempts": job["attempts"],
                    "action": "completed",
                    "status": completed["status"],
                },
                transition={
                    "event_id": transition["event_id"],
                    "event_stream_position": transition["event_stream_position"],
                    "card_id": transition["card_id"],
                    "previous_status": transition["previous_status"],
                    "next_status": transition["next_status"],
                    "current_version_id": transition["current_version_id"],
                    "challenge_id": transition.get("challenge_id") if hasattr(transition, "get") else None,
                    "challenge_digest": transition.get("challenge_digest") if hasattr(transition, "get") else None,
                },
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="writer_run_next_requested",
            )
    except Exception as exc:
        try:
            if "claimed_job_id" in locals() and "preview" in locals() and preview is not None:
                with connect(args) as fail_conn:
                    operation = preview["operation"]
                    spec = WRITER_RUN_OPERATIONS.get(operation)
                    if spec:
                        set_local_worker_claims(fail_conn, preview["tenant_id"], spec["worker_role"], operation)
                        fail_conn.execute(
                            "select job_id from knudg_fail_job(%s, %s, %s, %s)",
                            (claimed_job_id, exc.__class__.__name__, "Writer runner failed with sanitized local error.", args.retry_delay_seconds),
                        )
        except Exception:
            pass
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def _writer_existing_outbox(conn, plan):
    return conn.execute(
        """
        select id as outbox_event_id, job_id, event_stream_position, lane, status
        from outbox_events
        where tenant_id = %s and lane = %s and idempotency_key = %s
        """,
        (plan["tenant_id"], plan["lane"], plan["idempotency_key"]),
    ).fetchone()


def _writer_live_job(conn, plan):
    return conn.execute(
        """
        select id as job_id, status, lane, attempts, max_attempts, lease_expires_at
        from jobs
        where tenant_id = %s
          and lane = %s
          and idempotency_key = %s
          and status in ('ready','leased')
        order by created_at
        limit 1
        """,
        (plan["tenant_id"], plan["lane"], plan["idempotency_key"]),
    ).fetchone()


def writer_missing_next_job_findings(conn, args):
    findings = []
    for plan in writer_plan_candidates(conn, args):
        live = _writer_live_job(conn, plan)
        if live is not None:
            continue
        existing = _writer_existing_outbox(conn, plan)
        if args.apply and existing is None:
            existing, action = enqueue_writer_plan(conn, plan, priority=args.priority, max_attempts=args.max_attempts)
        elif args.apply:
            action = "not_applied_existing_outbox"
        else:
            action = "would_enqueue" if existing is None else "existing_outbox_not_live"
        findings.append(
            {
                "action_class": "missing_next_job",
                "tenant_id": plan["tenant_id"],
                "card_id": plan["card_id"],
                "current_version_id": plan["current_version_id"],
                "source_status": plan["source_status"],
                "operation": plan["operation"],
                "lane": plan["lane"],
                "worker_role": plan["worker_role"],
                "payload_digest": plan["payload_digest"],
                "idempotency_key_digest": hashlib.sha256(plan["idempotency_key"].encode("utf-8")).hexdigest(),
                "event_stream_position": plan["event_stream_position"],
                "job_id": existing["job_id"] if existing else None,
                "outbox_event_id": existing["outbox_event_id"] if existing else None,
                "action": action,
            }
        )
    return findings


def writer_stale_lease_findings(conn, args):
    tenant_filter, tenant_params = _tenant_filter_sql(args, "j")
    rows = conn.execute(
        f"""
        select j.tenant_id, j.id as job_id, j.lane, j.payload_digest, j.idempotency_key,
          j.attempts, j.max_attempts, j.leased_by, j.lease_expires_at,
          j.payload_json->>'operation' as operation,
          j.payload_json->>'worker_role' as worker_role,
          j.payload_json->>'card_id' as card_id,
          j.payload_json->>'current_version_id' as current_version_id
        from jobs j
        where j.lane = any(%s)
          and j.status = 'leased'
          and j.lease_expires_at <= now(){tenant_filter}
        order by j.lease_expires_at, j.created_at
        limit %s
        """,
        [list(WRITER_RUN_LANES), *tenant_params, args.limit],
    ).fetchall()
    findings = []
    for row in rows:
        action = "would_release_lease"
        if args.apply:
            conn.execute(
                """
                update jobs
                set status = 'ready',
                    leased_by = null,
                    lease_expires_at = null,
                    available_at = now(),
                    last_error_class = 'lease_expired',
                    last_error_detail = 'Writer sweeper released an expired local lease.',
                    updated_at = now()
                where tenant_id = %s and id = %s and status = 'leased' and lease_expires_at <= now()
                """,
                (row["tenant_id"], row["job_id"]),
            )
            conn.execute(
                """
                update job_attempts
                set status = 'retry_scheduled',
                    error_class = 'lease_expired',
                    sanitized_error_detail = 'Writer sweeper released an expired local lease.',
                    finished_at = now()
                where tenant_id = %s
                  and job_id = %s
                  and attempt_number = %s
                  and status = 'leased'
                """,
                (row["tenant_id"], row["job_id"], row["attempts"]),
            )
            action = "released_lease"
        findings.append(
            {
                "action_class": "stale_leased_job",
                "tenant_id": row["tenant_id"],
                "job_id": row["job_id"],
                "lane": row["lane"],
                "operation": row["operation"],
                "worker_role": row["worker_role"],
                "card_id": row["card_id"],
                "current_version_id": row["current_version_id"],
                "payload_digest": row["payload_digest"],
                "idempotency_key_digest": hashlib.sha256(row["idempotency_key"].encode("utf-8")).hexdigest(),
                "attempts": row["attempts"],
                "max_attempts": row["max_attempts"],
                "lease_expires_at": row["lease_expires_at"],
                "action": action,
            }
        )
    return findings


def writer_duplicate_active_findings(conn, args):
    tenant_filter, tenant_params = _tenant_filter_sql(args, "j")
    return conn.execute(
        f"""
        select j.tenant_id,
          j.payload_json->>'card_id' as card_id,
          j.payload_json->>'current_version_id' as current_version_id,
          count(*)::bigint as active_job_count,
          array_agg(j.id order by j.created_at) as job_ids,
          array_agg(j.lane order by j.created_at) as lanes,
          array_agg(j.payload_json->>'operation' order by j.created_at) as operations
        from jobs j
        where j.lane = any(%s)
          and j.status in ('ready','leased')
          and j.payload_json->>'schema_version' = 'writer-orchestration-job-v0'{tenant_filter}
        group by j.tenant_id, j.payload_json->>'card_id', j.payload_json->>'current_version_id'
        having count(*) > 1
        order by active_job_count desc
        limit %s
        """,
        [list(WRITER_RUN_LANES), *tenant_params, args.limit],
    ).fetchall()


def writer_expired_challenge_findings(conn, args):
    tenant_filter, tenant_params = _tenant_filter_sql(args, "ac")
    return conn.execute(
        f"""
        select ac.tenant_id, ac.id as challenge_id, ac.subject_id, ac.namespace_id,
          ac.artifact_id, ac.card_version_id, ac.artifact_digest,
          ac.policy_version, ac.policy_digest, ac.challenge_digest, ac.expires_at
        from approval_challenges ac
        where ac.consent_scope = 'private_retention'
          and ac.used_at is null
          and ac.invalidated_at is null
          and ac.expires_at <= now(){tenant_filter}
        order by ac.expires_at
        limit %s
        """,
        [*tenant_params, args.limit],
    ).fetchall()


def writer_sweep(args):
    try:
        with connect(args) as conn:
            missing = writer_missing_next_job_findings(conn, args)
            stale = writer_stale_lease_findings(conn, args)
            duplicates = writer_duplicate_active_findings(conn, args)
            expired = writer_expired_challenge_findings(conn, args)
            findings = [*missing, *stale]
            findings.extend(
                {
                    "action_class": "duplicate_active_jobs",
                    "tenant_id": row["tenant_id"],
                    "card_id": row["card_id"],
                    "current_version_id": row["current_version_id"],
                    "active_job_count": row["active_job_count"],
                    "job_ids": row["job_ids"],
                    "lanes": row["lanes"],
                    "operations": row["operations"],
                    "action": "inspect_manually",
                }
                for row in duplicates
            )
            findings.extend(
                {
                    "action_class": "expired_private_approval_challenge",
                    "tenant_id": row["tenant_id"],
                    "challenge_id": row["challenge_id"],
                    "subject_id": row["subject_id"],
                    "namespace_id": row["namespace_id"],
                    "artifact_id": row["artifact_id"],
                    "card_version_id": row["card_version_id"],
                    "artifact_digest": row["artifact_digest"],
                    "policy_version": row["policy_version"],
                    "policy_digest": row["policy_digest"],
                    "challenge_digest": row["challenge_digest"],
                    "expires_at": row["expires_at"],
                    "action": "inspect_manually",
                }
                for row in expired
            )
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                dry_run=args.dry_run,
                apply=args.apply,
                tenant=args.tenant,
                limit=args.limit,
                priority=args.priority,
                max_attempts=args.max_attempts,
                finding_count=len(findings),
                findings=findings,
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="writer_sweep_requested",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def approval_handoff_digest(row):
    payload = {
        "schema_version": "approval-handoff-v0",
        "tenant_id": str(row["tenant_id"]),
        "challenge_id": str(row["challenge_id"]),
        "subject_id": str(row["subject_id"]),
        "namespace_id": str(row["namespace_id"]),
        "consent_scope": row["consent_scope"],
        "artifact_type": row["artifact_type"],
        "artifact_id": str(row["artifact_id"]),
        "card_version_id": str(row["card_version_id"]),
        "artifact_digest": row["artifact_digest"],
        "policy_version": row["policy_version"],
        "policy_digest": row["policy_digest"],
        "challenge_digest": row["challenge_digest"],
        "origin": row["origin"],
        "expires_at": row["expires_at"].isoformat() if hasattr(row["expires_at"], "isoformat") else str(row["expires_at"]),
    }
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload_text.encode("utf-8")).hexdigest()


def approval_handoff_candidate(conn, args):
    return conn.execute(
        """
        select c.tenant_id, c.id as card_id, c.namespace_id, c.current_version_id,
          ac.id as challenge_id, ac.subject_id, ac.consent_scope, ac.artifact_type,
          ac.artifact_id, ac.card_version_id, ac.artifact_digest, ac.policy_version,
          ac.policy_digest, ac.challenge_digest, ac.expires_at,
          'local-trusted-ui-placeholder' as origin,
          ac.created_by
        from experience_cards c
        join card_versions cv
          on cv.tenant_id = c.tenant_id
         and cv.id = c.current_version_id
         and cv.card_id = c.id
        join approval_challenges ac
          on ac.tenant_id = c.tenant_id
         and ac.namespace_id = c.namespace_id
         and ac.consent_scope = 'private_retention'
         and ac.artifact_type = 'card_version'
         and ac.artifact_id = c.current_version_id
         and ac.card_version_id = c.current_version_id
         and ac.artifact_digest = cv.payload_digest
         and ac.used_at is null
         and ac.invalidated_at is null
         and ac.expires_at > now()
        where c.tenant_id = %s
          and c.id = %s
          and c.status = 'awaiting_user_approval'
        order by ac.created_at desc
        limit 1
        """,
        (args.tenant, args.card),
    ).fetchone()


def approval_handoff_view(row, *, action):
    if row is None:
        return None
    view = {
        "tenant_id": row["tenant_id"],
        "handoff_id": row["handoff_id"],
        "challenge_id": row["challenge_id"],
        "card_id": row.get("card_id"),
        "namespace_id": row["namespace_id"],
        "consent_scope": row["consent_scope"],
        "artifact_type": row["artifact_type"],
        "artifact_id": row["artifact_id"],
        "card_version_id": row["card_version_id"],
        "artifact_digest": row["artifact_digest"],
        "policy_version": row["policy_version"],
        "policy_digest": row["policy_digest"],
        "challenge_digest": row["challenge_digest"],
        "handoff_digest": row["handoff_digest"],
        "origin": row["origin"],
        "expires_at": row["expires_at"],
        "created_at": row.get("created_at"),
        "challenge_used": bool(row.get("challenge_used")),
        "expired": bool(row.get("expired")),
        "action": action,
    }
    if "card_status" in row:
        view.update(
            {
                "state": row.get("handoff_state"),
                "card_status": row.get("card_status"),
                "current_card_version_id": row.get("current_card_version_id"),
                "handoff_expired": bool(row.get("expired")),
                "handoff_invalidated": bool(row.get("handoff_invalidated")),
                "challenge_expired": bool(row.get("challenge_expired")),
                "challenge_invalidated": bool(row.get("challenge_invalidated")),
                "consent_completed": bool(row.get("consent_record_exists")),
                "active_matching_consent": bool(row.get("active_matching_consent")),
                "card_version_current": bool(row.get("card_current_version_matches")),
                "artifact_digest_matches_version": bool(row.get("artifact_digest_matches_version")),
                "handoff_digest_valid": bool(row.get("handoff_digest_valid")),
            }
        )
    return view


def approval_handoff_verification(row):
    blockers = []
    checks = {
        "handoff_invalidated": bool(row.get("handoff_invalidated")),
        "handoff_expired": bool(row.get("expired")),
        "challenge_used": bool(row.get("challenge_used")),
        "challenge_invalidated": bool(row.get("challenge_invalidated")),
        "challenge_expired": bool(row.get("challenge_expired")),
        "consent_record_exists": bool(row.get("consent_record_exists")),
        "active_matching_consent": bool(row.get("active_matching_consent")),
        "revocation_visible": bool(row.get("revocation_visible")),
        "digest_binding_valid": bool(row.get("digest_binding_valid")),
        "handoff_digest_valid": bool(row.get("handoff_digest_valid")),
        "card_current_version_matches": bool(row.get("card_current_version_matches")),
        "card_awaiting_user_approval": row.get("card_status") == "awaiting_user_approval",
    }
    for name, value in checks.items():
        if name in {"digest_binding_valid", "handoff_digest_valid", "card_current_version_matches", "card_awaiting_user_approval"}:
            if not value:
                blockers.append(name)
        elif value:
            blockers.append(name)
    return {
        "schema_version": "approval-handoff-verification-v0",
        "read_only": True,
        "completion_enabled": False,
        "trusted_completion_enabled": False,
        "public_publication_enabled": False,
        "team_sharing_enabled": False,
        "team_namespace_grant_enabled": False,
        "protected_data_serving_enabled": False,
        "checks": checks,
        "blockers": blockers,
    }


def writer_approval_handoff_create(args):
    try:
        with connect(args) as conn:
            candidate = approval_handoff_candidate(conn, args)
            if candidate is None:
                return emit(
                    command_name(args),
                    "not_found",
                    EXIT_NOT_CONFIGURED,
                    dry_run=args.dry_run,
                    apply=args.apply,
                    tenant=args.tenant,
                    card_id=args.card,
                    detail="No active private approval challenge is ready for this card.",
                )
            existing = conn.execute(
                """
                select ah.tenant_id, ah.id as handoff_id, ah.challenge_id, cv.card_id,
                  ah.namespace_id, ah.consent_scope, ah.artifact_type, ah.artifact_id,
                  ah.card_version_id, ah.artifact_digest, ah.policy_version, ah.policy_digest,
                  ah.challenge_digest, ah.handoff_digest, ah.origin, ah.expires_at,
                  ah.created_at, ac.used_at is not null as challenge_used, ah.expires_at <= now() as expired
                from approval_handoffs ah
                join approval_challenges ac on ac.tenant_id = ah.tenant_id and ac.id = ah.challenge_id
                join card_versions cv on cv.tenant_id = ah.tenant_id and cv.id = ah.card_version_id
                where ah.tenant_id = %s and ah.challenge_id = %s
                """,
                (candidate["tenant_id"], candidate["challenge_id"]),
            ).fetchone()
            if existing is not None:
                return emit(
                    command_name(args),
                    "ok",
                    EXIT_OK,
                    dry_run=args.dry_run,
                    apply=args.apply,
                    tenant=args.tenant,
                    card_id=args.card,
                    handoff=approval_handoff_view(existing, action="already_created"),
                    completion_enabled=False,
                    protected_data_serving_enabled=False,
                    publication_enabled=False,
                    audit_event="approval_handoff_requested",
                )
            digest = approval_handoff_digest(candidate)
            if args.dry_run:
                handoff = {
                    "tenant_id": candidate["tenant_id"],
                    "handoff_id": None,
                    "challenge_id": candidate["challenge_id"],
                    "card_id": candidate["card_id"],
                    "namespace_id": candidate["namespace_id"],
                    "consent_scope": candidate["consent_scope"],
                    "artifact_type": candidate["artifact_type"],
                    "artifact_id": candidate["artifact_id"],
                    "card_version_id": candidate["card_version_id"],
                    "artifact_digest": candidate["artifact_digest"],
                    "policy_version": candidate["policy_version"],
                    "policy_digest": candidate["policy_digest"],
                    "challenge_digest": candidate["challenge_digest"],
                    "handoff_digest": digest,
                    "origin": candidate["origin"],
                    "expires_at": candidate["expires_at"],
                    "created_at": None,
                    "challenge_used": False,
                    "expired": False,
                }
                return emit(
                    command_name(args),
                    "ok",
                    EXIT_OK,
                    dry_run=True,
                    apply=False,
                    tenant=args.tenant,
                    card_id=args.card,
                    handoff=approval_handoff_view(handoff, action="would_create"),
                    completion_enabled=False,
                    protected_data_serving_enabled=False,
                    publication_enabled=False,
                    audit_event="approval_handoff_requested",
                )
            handoff_id = uuid.uuid4()
            conn.execute(
                """
                insert into approval_handoffs(
                  tenant_id, id, challenge_id, subject_id, namespace_id, consent_scope,
                  artifact_type, artifact_id, card_version_id, artifact_digest,
                  policy_version, policy_digest, challenge_digest, handoff_digest,
                  origin, expires_at, created_by
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    candidate["tenant_id"],
                    handoff_id,
                    candidate["challenge_id"],
                    candidate["subject_id"],
                    candidate["namespace_id"],
                    candidate["consent_scope"],
                    candidate["artifact_type"],
                    candidate["artifact_id"],
                    candidate["card_version_id"],
                    candidate["artifact_digest"],
                    candidate["policy_version"],
                    candidate["policy_digest"],
                    candidate["challenge_digest"],
                    digest,
                    candidate["origin"],
                    candidate["expires_at"],
                    candidate["created_by"],
                ),
            )
            created = conn.execute(
                """
                select ah.tenant_id, ah.id as handoff_id, ah.challenge_id, cv.card_id,
                  ah.namespace_id, ah.consent_scope, ah.artifact_type, ah.artifact_id,
                  ah.card_version_id, ah.artifact_digest, ah.policy_version, ah.policy_digest,
                  ah.challenge_digest, ah.handoff_digest, ah.origin, ah.expires_at,
                  ah.created_at, false as challenge_used, ah.expires_at <= now() as expired
                from approval_handoffs ah
                join card_versions cv on cv.tenant_id = ah.tenant_id and cv.id = ah.card_version_id
                where ah.tenant_id = %s and ah.id = %s
                """,
                (candidate["tenant_id"], handoff_id),
            ).fetchone()
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                dry_run=False,
                apply=True,
                tenant=args.tenant,
                card_id=args.card,
                handoff=approval_handoff_view(created, action="created"),
                completion_enabled=False,
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="approval_handoff_requested",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def writer_approval_handoff_inspect(args):
    try:
        with connect(args) as conn:
            row = conn.execute(
                """
                select ah.tenant_id, ah.id as handoff_id, ah.challenge_id, cv.card_id,
                  ah.namespace_id, ah.consent_scope, ah.artifact_type, ah.artifact_id,
                  ah.card_version_id, ah.artifact_digest, ah.policy_version, ah.policy_digest,
                  ah.challenge_digest, ah.handoff_digest, ah.origin, ah.expires_at,
                  ah.created_at, ac.used_at is not null as challenge_used, ah.expires_at <= now() as expired
                from approval_handoffs ah
                join approval_challenges ac on ac.tenant_id = ah.tenant_id and ac.id = ah.challenge_id
                join card_versions cv on cv.tenant_id = ah.tenant_id and cv.id = ah.card_version_id
                where ah.tenant_id = %s and ah.id = %s
                """,
                (args.tenant, args.handoff),
            ).fetchone()
            if row is None:
                return emit(
                    command_name(args),
                    "not_found",
                    EXIT_NOT_CONFIGURED,
                    tenant=args.tenant,
                    handoff_id=args.handoff,
                    detail="Approval handoff was not found.",
                )
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                tenant=args.tenant,
                handoff=approval_handoff_view(row, action="inspect"),
                completion_enabled=False,
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="approval_handoff_inspected",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def writer_approval_handoff_status(args):
    try:
        with connect(args) as conn:
            row = conn.execute(
                """
                select ah.tenant_id, ah.id as handoff_id, ah.challenge_id, ah.subject_id, cv.card_id,
                  ah.namespace_id, ah.consent_scope, ah.artifact_type, ah.artifact_id,
                  ah.card_version_id, ah.artifact_digest, ah.policy_version, ah.policy_digest,
                  ah.challenge_digest, ah.handoff_digest, ah.origin, ah.expires_at,
                  ah.created_at, ac.used_at is not null as challenge_used,
                  ac.invalidated_at is not null as challenge_invalidated,
                  ac.expires_at <= now() as challenge_expired,
                  ah.invalidated_at is not null as handoff_invalidated,
                  ah.expires_at <= now() as expired,
                  c.status as card_status,
                  c.current_version_id,
                  c.current_version_id = ah.card_version_id as card_current_version_matches,
                  ah.artifact_digest = cv.payload_digest as artifact_digest_matches_version,
                  (
                    ah.subject_id = ac.subject_id
                    and ah.namespace_id = ac.namespace_id
                    and ah.consent_scope = ac.consent_scope
                    and ah.artifact_type = ac.artifact_type
                    and ah.artifact_id = ac.artifact_id
                    and ah.card_version_id = ac.card_version_id
                    and ah.artifact_digest = ac.artifact_digest
                    and ah.artifact_digest = cv.payload_digest
                    and ah.policy_version = ac.policy_version
                    and ah.policy_digest = ac.policy_digest
                    and ah.challenge_digest = ac.challenge_digest
                  ) as digest_binding_valid,
                  exists (
                    select 1
                    from consent_records cr
                    where cr.tenant_id = ah.tenant_id
                      and cr.challenge_id = ah.challenge_id
                      and cr.revoked_at is null
                      and (cr.expires_at is null or cr.expires_at > now())
                  ) as consent_record_exists,
                  exists (
                    select 1
                    from consent_records cr
                    where cr.tenant_id = ah.tenant_id
                      and cr.challenge_id = ah.challenge_id
                      and cr.scope = ah.consent_scope
                      and cr.artifact_type = ah.artifact_type
                      and cr.artifact_id = ah.artifact_id
                      and cr.card_version_id = ah.card_version_id
                      and cr.artifact_digest = ah.artifact_digest
                      and cr.policy_version = ah.policy_version
                      and cr.policy_digest = ah.policy_digest
                      and cr.challenge_digest = ah.challenge_digest
                      and cr.revoked_at is null
                      and (cr.expires_at is null or cr.expires_at > now())
                  ) as active_matching_consent,
                  exists (
                    select 1
                    from revocation_tombstones rt
                    where rt.tenant_id = ah.tenant_id
                      and (
                        rt.tenant_subject_id = ah.tenant_id
                        or rt.namespace_id = ah.namespace_id
                        or rt.card_id = cv.card_id
                        or rt.card_version_id = ah.card_version_id
                      )
                  ) as revocation_visible
                from approval_handoffs ah
                join approval_challenges ac on ac.tenant_id = ah.tenant_id and ac.id = ah.challenge_id
                join card_versions cv on cv.tenant_id = ah.tenant_id and cv.id = ah.card_version_id
                join experience_cards c on c.tenant_id = cv.tenant_id and c.id = cv.card_id
                where ah.tenant_id = %s and ah.id = %s
                """,
                (args.tenant, args.handoff),
            ).fetchone()
            if row is None:
                return emit(
                    command_name(args),
                    "not_found",
                    EXIT_NOT_CONFIGURED,
                    tenant=args.tenant,
                    handoff_id=args.handoff,
                    detail="Approval handoff was not found.",
                )
            row = dict(row)
            row["handoff_digest_valid"] = row["handoff_digest"] == approval_handoff_digest(row)
            verification = approval_handoff_verification(row)
            if row["active_matching_consent"]:
                row["handoff_state"] = "consent_completed"
            elif verification["blockers"]:
                row["handoff_state"] = "blocked"
            else:
                row["handoff_state"] = "pending_user_consent"
            return emit(
                command_name(args),
                "ok",
                EXIT_OK,
                tenant=args.tenant,
                handoff_id=args.handoff,
                operation="approval_handoff_status",
                command_effect="read_only",
                completion_authority="none",
                publication_authority="none",
                creates_handoff=False,
                creates_or_rotates_challenge=False,
                opens_trusted_surface=False,
                writes_consent_event=False,
                writes_publication_event=False,
                writes_revocation_or_tombstone_event=False,
                lifecycle_state_changed=False,
                emitted_events=[],
                handoff=approval_handoff_view(row, action=args.action),
                verification=verification,
                completion_enabled=False,
                trusted_completion_enabled=False,
                team_sharing_enabled=False,
                team_namespace_grant_enabled=False,
                public_publication_enabled=False,
                terminal_publication_completion_enabled=False,
                protected_data_serving_enabled=False,
                publication_enabled=False,
                audit_event="approval_handoff_status_checked",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def outbox_reconcile(args):
    try:
        with connect(args) as conn:
            missing = conn.execute(
                """
                select esp.event_stream_position, esp.tenant_id, esp.event_source_type
                from event_stream_positions esp
                left join outbox_events oe
                  on oe.tenant_id = esp.tenant_id
                 and oe.event_stream_position = esp.event_stream_position
                where esp.event_stream_position >= %s
                  and oe.id is null
                order by esp.event_stream_position
                limit 100
                """,
                (args.from_position,),
            ).fetchall()
            return emit(
                command_name(args),
                "ok" if args.dry_run else "not_configured",
                EXIT_OK if args.dry_run else EXIT_NOT_CONFIGURED,
                dry_run=args.dry_run,
                apply=args.apply,
                from_position=args.from_position,
                missing_outbox=missing,
                audit_event="outbox_reconcile_requested",
                detail=None if args.dry_run else "Apply mode is not configured in local M0.",
            )
    except Exception as exc:
        return emit(command_name(args), "unavailable", EXIT_UNAVAILABLE, error_class=exc.__class__.__name__, detail=str(exc))


def not_configured(args):
    return emit(
        command_name(args),
        "not_configured",
        EXIT_NOT_CONFIGURED,
        dry_run=getattr(args, "dry_run", False),
        apply=getattr(args, "apply", False),
        required_operator_role=getattr(args, "required_operator_role", "operator"),
        audit_event=getattr(args, "audit_event", f"{command_name(args).replace(' ', '_')}_requested"),
        detail="Command stub exists; backing operational integration is not configured in local M0.",
    )


def emit_not_configured_custom_server(args, profile):
    return emit_client(
        command_name(args),
        "not_configured",
        EXIT_NOT_CONFIGURED,
        profile=profile,
        detail=f"{profile} custom server support is reserved for a later enterprise/auth phase.",
    )


def config_path_arg(args):
    return getattr(args, "config", None)


def config_show(args):
    try:
        config = load_config(config_path_arg(args), env=os.environ)
        profile = args.profile or config.active_profile
        if profile not in PROFILE_CHOICES:
            return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail="invalid profile")
        if profile in {"cloud", "enterprise"} and args.profile:
            entry = config.profiles.get(profile, {})
            return emit_client(
                command_name(args),
                "ok",
                EXIT_OK,
                profile=profile,
                active_profile=config.active_profile,
                server_url=entry.get("server_url"),
                auth_profile=entry.get("auth_profile"),
                tenant={"present": entry.get("tenant_id") is not None},
                pin_state="pinned" if config.pins.get(profile) else "unpinned",
                capabilities_cache_exists=profile in config.capabilities_cache,
                exploration_depth=config.exploration_depth,
            )
        if profile == "local" and not config.profiles.get("local", {}).get("server_url"):
            entry = config.profiles.get("local", {})
            return emit_client(
                command_name(args),
                "ok",
                EXIT_OK,
                profile="local",
                active_profile=config.active_profile,
                server_url=None,
                auth_profile=entry.get("auth_profile") or "local",
                tenant={"present": False},
                pin_state="unpinned",
                capabilities_cache_exists=False,
                exploration_depth=config.exploration_depth,
            )
        effective = effective_profile(config, env=os.environ, overrides={"profile": profile}, caller_context="cli")
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            profile=effective.profile,
            active_profile=config.active_profile,
            server_url=effective.server_url,
            auth_profile=effective.auth_profile,
            tenant={"present": False},
            pin_state=effective.pin_state,
            capabilities_cache_exists=effective.profile in config.capabilities_cache,
            exploration_depth=config.exploration_depth,
        )
    except (ConfigError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))


def config_set_exploration_depth(args):
    try:
        config = load_config(config_path_arg(args), env=os.environ)
        updated = config.__class__(
            active_profile=config.active_profile,
            profiles=config.profiles,
            pins=config.pins,
            capabilities_cache=config.capabilities_cache,
            exploration_depth=args.depth,
            path=config.path,
        )
        save_config(updated)
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            exploration_depth=args.depth,
            guidance_mode="disabled" if args.depth == "off" else "root_cause_hint" if args.depth == "hard" else "publication_candidate",
        )
    except (ConfigError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))


def config_set_server(args):
    if args.profile != "local":
        return emit_not_configured_custom_server(args, args.profile)
    if args.auth_profile and args.auth_profile != "local":
        return emit_client(
            command_name(args),
            "usage_error",
            EXIT_USAGE,
            profile="local",
            detail="local custom servers only support auth_profile=local in this slice",
        )
    try:
        server_url = normalize_server_url(args.server_url, "local")
        config = load_config(config_path_arg(args), env=os.environ)
        profiles = dict(config.profiles)
        profiles["local"] = {
            "server_url": server_url,
            "auth_profile": args.auth_profile or "local",
            "tenant_id": None,
        }
        updated = default_config(config.path)
        updated = updated.__class__(
            active_profile="local",
            profiles={**updated.profiles, **profiles},
            pins={key: value for key, value in config.pins.items() if key != "local"},
            capabilities_cache={key: value for key, value in config.capabilities_cache.items() if key != "local"},
            exploration_depth=config.exploration_depth,
            path=config.path,
        )
        save_config(updated)
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            profile="local",
            server_url=server_url,
            auth_profile=args.auth_profile or "local",
            tenant={"present": False},
            pin_state="unpinned",
        )
    except (ConfigError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))


def config_use_profile(args):
    try:
        config = load_config(config_path_arg(args), env=os.environ)
        if args.profile != "local":
            return emit_not_configured_custom_server(args, args.profile)
        if not config.profiles.get("local", {}).get("server_url"):
            return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail="local server_url is not configured")
        updated = config.__class__(
            active_profile="local",
            profiles=config.profiles,
            pins=config.pins,
            capabilities_cache=config.capabilities_cache,
            exploration_depth=config.exploration_depth,
            path=config.path,
        )
        save_config(updated)
        return emit_client(command_name(args), "ok", EXIT_OK, profile="local")
    except (ConfigError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))


def _server_effective(args):
    config = load_config(config_path_arg(args), env=os.environ)
    profile = args.profile or ("local" if args.server_url else config.active_profile)
    if profile != "local":
        return config, profile, None
    effective = effective_profile(
        config,
        env=os.environ,
        overrides={"profile": profile, "server_url": args.server_url},
        caller_context="cli",
    )
    return config, profile, effective


def server_status(args):
    try:
        _, profile, effective = _server_effective(args)
        if profile != "local":
            return emit_not_configured_custom_server(args, profile)
        startup = probe_json(effective.server_url, "/health/startup")
        ready = validate_ready_health(probe_json(effective.server_url, "/health/ready"))
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            profile=effective.profile,
            server_url=effective.server_url,
            auth_profile=effective.auth_profile,
            tenant={"present": False},
            pin_state=effective.pin_state,
            health={"startup": startup, "ready": ready},
        )
    except HealthInvalid as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))
    except (ConfigError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))
    except ProbeError as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))


def _pin_matches(pin, effective, capabilities, digest):
    return (
        pin.get("server_url") == effective.server_url
        and pin.get("server_id") == capabilities.get("server_id")
        and pin.get("deployment_type") == capabilities.get("deployment_type")
        and pin.get("api_version") == capabilities.get("api_version")
        and pin.get("capability_resource_origin") == capabilities.get("capability_resource_origin")
        and pin.get("capabilities_digest") == digest
        and pin.get("auth_profile") == effective.auth_profile
        and pin.get("tenant_id") is None
    )


def server_capabilities(args):
    try:
        config, profile, effective = _server_effective(args)
        if profile != "local":
            return emit_not_configured_custom_server(args, profile)
        capabilities = validate_capabilities(probe_json(effective.server_url, "/capabilities"), effective.server_url)
        digest = canonical_capabilities_digest(capabilities)
        if effective.pin and not _pin_matches(effective.pin, effective, capabilities, digest) and not args.pin:
            return emit_client(
                command_name(args),
                "server_pin_mismatch",
                EXIT_UNAVAILABLE,
                profile=effective.profile,
                server_url=effective.server_url,
                pin_state="mismatch",
                capabilities_digest=digest,
            )
        pin_state = effective.pin_state
        if args.pin:
            if not args.allow_insecure_loopback:
                return emit_client(
                    command_name(args),
                    "usage_error",
                    EXIT_USAGE,
                    profile=effective.profile,
                    server_url=effective.server_url,
                    detail="--pin requires --allow-insecure-loopback for local loopback servers",
                )
            pins = dict(config.pins)
            pins["local"] = {
                "server_url": effective.server_url,
                "server_id": capabilities["server_id"],
                "deployment_type": capabilities["deployment_type"],
                "api_version": capabilities["api_version"],
                "capabilities_digest": digest,
                "capability_resource_origin": capabilities["capability_resource_origin"],
                "auth_profile": effective.auth_profile,
                "tenant_id": None,
                "pinned_at": utc_now_iso(),
                "pin_class": "local_dev_non_authoritative"
                if capabilities["deployment_type"] == "local"
                else "closed_launch_loopback_operator_only",
            }
            cache = dict(config.capabilities_cache)
            cache["local"] = {
                "capabilities_digest": digest,
                "capabilities": capabilities,
                "cached_at": utc_now_iso(),
            }
            updated = config.__class__(
                active_profile=config.active_profile,
                profiles=config.profiles,
                pins=pins,
                capabilities_cache=cache,
                exploration_depth=config.exploration_depth,
                path=config.path,
            )
            save_config(updated)
            pin_state = "pinned"
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            profile=effective.profile,
            server_url=effective.server_url,
            auth_profile=effective.auth_profile,
            tenant={"present": False},
            pin_state=pin_state,
            capabilities_digest=digest,
            server_id=capabilities["server_id"],
            deployment_type=capabilities["deployment_type"],
            api_version=capabilities["api_version"],
        )
    except CapabilitiesInvalid as exc:
        return emit_client(command_name(args), "capabilities_invalid", EXIT_UNAVAILABLE, detail=str(exc))
    except (ConfigError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))
    except ProbeError as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))


def _live_effective(args):
    config = load_config(config_path_arg(args), env=os.environ)
    effective = effective_profile(
        config,
        env=os.environ,
        overrides={"profile": "local"},
        caller_context="cli",
    )
    if effective.pin_state != "pinned" or not effective.pin:
        raise ConfigError("live backend must use a pinned local profile")
    if effective.pin.get("deployment_type") != "greencloud_closed_launch":
        raise ConfigError("live backend pin must be greencloud_closed_launch")
    if effective.pin.get("pin_class") != "closed_launch_loopback_operator_only":
        raise ConfigError("live backend pin class rejected")
    return config, effective


def live_profile_build(args):
    try:
        profile = build_task_profile(load_json_arg(args.input))
        fields = {
            "task_profile": profile,
            "profile_digest": "sha256:" + hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        }
        if args.with_query_views:
            fields["query_views"] = build_query_views(profile)
        return emit_client(command_name(args), "ok", EXIT_OK, **fields)
    except FileNotFoundError as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=f"input file not found: {Path(exc.filename).name}")
    except (TaskProfileError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))


def live_search(args):
    try:
        _, effective = _live_effective(args)
        task_profile = require_local_search_task_profile(load_json_arg(args.task_profile))
        token = live_operator_token(args)
        status, payload = live_post_json(
            effective.server_url,
            "/v1/private/search",
            {
                "workspace": args.workspace,
                "task_profile": live_wire_task_profile(task_profile),
                "limit": args.limit,
                "min_score": args.min_score,
                "latency_budget_ms": args.latency_budget_ms,
            },
            token,
        )
        if status < 200 or status >= 300:
            return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, upstream_status=status, upstream_status_text=payload.get("status"))
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            profile=effective.profile,
            server_url=effective.server_url,
            pin_state=effective.pin_state,
            result=payload.get("result"),
            publication_enabled=payload.get("publication_enabled", False),
            public_search_enabled=payload.get("public_search_enabled", False),
            vector_search_enabled=payload.get("vector_search_enabled", False),
        )
    except FileNotFoundError as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=f"task profile not found: {Path(exc.filename).name}")
    except (ConfigError, ValueError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))
    except ProbeError as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))


def live_nudge(args):
    try:
        _, effective = _live_effective(args)
        task_profile = require_local_search_task_profile(load_json_arg(args.task_profile))
        token = live_operator_token(args)
        status, payload = live_post_json(
            effective.server_url,
            "/v1/private/search",
            {
                "workspace": args.workspace,
                "task_profile": live_wire_task_profile(task_profile),
                "limit": args.limit,
                "min_score": args.min_score,
                "latency_budget_ms": args.latency_budget_ms,
            },
            token,
        )
        if status < 200 or status >= 300:
            verdict_payload = live_verdict(
                "nudger",
                "degraded",
                "none",
                "none",
                "Live Knudg search could not produce a safe verdict.",
                "do_nothing",
                suppressed_detail="not_authorized" if status in {401, 403} else "none",
            )
        else:
            verdict_payload = live_search_verdict(payload)
        return emit_client(
            command_name(args),
            "ok" if verdict_payload["status"] != "degraded" else "degraded",
            EXIT_OK,
            verdict=verdict_payload,
        )
    except FileNotFoundError as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=f"task profile not found: {Path(exc.filename).name}")
    except (ConfigError, ValueError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))
    except ProbeError as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))


def live_write_candidate(args):
    try:
        _, effective = _live_effective(args)
        token = live_operator_token(args)
        card = validate_local_private_card_v0(load_json_arg(args.card))
        status, payload = live_post_json(
            effective.server_url,
            "/v1/private/cards:publish",
            {
                "workspace": args.workspace,
                "card": card,
            },
            token,
        )
        if status != 409 or payload.get("status") != "approval_required":
            return emit_client(
                command_name(args),
                "unavailable",
                EXIT_UNAVAILABLE,
                upstream_status=status,
                upstream_status_text=payload.get("status"),
                stored=payload.get("stored", False),
            )
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            verdict=live_writer_candidate_verdict(payload),
            artifact_digest=payload["artifact_digest"],
            stored=False,
            public_publication_enabled=False,
        )
    except FileNotFoundError as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=f"card file not found: {Path(exc.filename).name}")
    except (ConfigError, LocalPrivateCardError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))
    except ProbeError as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))


def live_final_filter_stats(args):
    try:
        _, effective = _live_effective(args)
        token = live_operator_token(args)
        status, payload = live_post_json(
            effective.server_url,
            "/v1/private/final-filter/jobs:stats",
            {},
            token,
            timeout_seconds=args.timeout_seconds,
        )
        if status < 200 or status >= 300:
            return emit_client(
                command_name(args),
                "unavailable",
                EXIT_UNAVAILABLE,
                upstream_status=status,
                upstream_status_text=payload.get("status"),
            )
        stats = payload.get("stats")
        if not isinstance(stats, dict):
            return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, upstream_status=status, upstream_status_text=payload.get("status"))
        return emit_client(
            command_name(args),
            "ok",
            EXIT_OK,
            profile=effective.profile,
            server_url=effective.server_url,
            queue_status=payload.get("status"),
            stats=stats,
        )
    except (ConfigError, ValueError, json.JSONDecodeError) as exc:
        return emit_client(command_name(args), "usage_error", EXIT_USAGE, detail=str(exc))
    except ProbeError as exc:
        return emit_client(command_name(args), "unavailable", EXIT_UNAVAILABLE, detail=str(exc))


def add_common(parser):
    parser.add_argument("--database-url", default=None)


def build_parser():
    parser = JsonArgumentParser(description="Knudg local operational CLI stubs.")
    parser.set_defaults(func=lambda args: emit("knudgctl", "usage_error", EXIT_USAGE, detail="missing command"))
    add_common(parser)
    sub = parser.add_subparsers(dest="group", parser_class=JsonArgumentParser)

    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    cfg_show = config_sub.add_parser("show")
    cfg_show.add_argument("--profile", choices=PROFILE_CHOICES)
    cfg_show.add_argument("--config")
    cfg_show.set_defaults(func=config_show)
    cfg_set = config_sub.add_parser("set-server")
    cfg_set.add_argument("--profile", choices=PROFILE_CHOICES, required=True)
    cfg_set.add_argument("--server-url", required=True)
    cfg_set.add_argument("--auth-profile", choices=PROFILE_CHOICES)
    cfg_set.add_argument("--config")
    cfg_set.set_defaults(func=config_set_server)
    cfg_use = config_sub.add_parser("use-profile")
    cfg_use.add_argument("profile", choices=PROFILE_CHOICES)
    cfg_use.add_argument("--config")
    cfg_use.set_defaults(func=config_use_profile)
    cfg_explore = config_sub.add_parser("set-exploration-depth")
    cfg_explore.add_argument("depth", choices=EXPLORATION_DEPTH_CHOICES)
    cfg_explore.add_argument("--config")
    cfg_explore.set_defaults(func=config_set_exploration_depth)

    server = sub.add_parser("server")
    server_sub = server.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    srv_status = server_sub.add_parser("status")
    srv_status.add_argument("--profile", choices=PROFILE_CHOICES)
    srv_status.add_argument("--server-url")
    srv_status.add_argument("--config")
    srv_status.set_defaults(func=server_status)
    srv_capabilities = server_sub.add_parser("capabilities")
    srv_capabilities.add_argument("--profile", choices=PROFILE_CHOICES)
    srv_capabilities.add_argument("--server-url")
    srv_capabilities.add_argument("--pin", action="store_true")
    srv_capabilities.add_argument("--allow-insecure-loopback", action="store_true")
    srv_capabilities.add_argument("--config")
    srv_capabilities.set_defaults(func=server_capabilities)
    live = sub.add_parser("live")
    live_sub = live.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    live_profile = live_sub.add_parser("profile")
    live_profile_sub = live_profile.add_subparsers(dest="action", required=True, parser_class=JsonArgumentParser)
    live_profile_build_parser = live_profile_sub.add_parser("build")
    live_profile_build_parser.add_argument("--input", required=True)
    live_profile_build_parser.add_argument("--with-query-views", action="store_true")
    live_profile_build_parser.set_defaults(func=live_profile_build)
    live_search_parser = live_sub.add_parser("search")
    live_search_parser.add_argument("--task-profile", required=True)
    live_search_parser.add_argument("--workspace", default="closed-beta-agent")
    live_search_parser.add_argument("--limit", type=positive_int, default=3)
    live_search_parser.add_argument("--min-score", type=positive_int, default=1)
    live_search_parser.add_argument("--latency-budget-ms", type=positive_int, default=250)
    live_search_parser.add_argument("--token-env", default="KNUDG_OPERATOR_TOKEN")
    live_search_parser.add_argument("--config")
    live_search_parser.set_defaults(func=live_search)
    live_nudge_parser = live_sub.add_parser("nudge")
    live_nudge_parser.add_argument("--task-profile", required=True)
    live_nudge_parser.add_argument("--workspace", default="closed-beta-agent")
    live_nudge_parser.add_argument("--limit", type=positive_int, default=3)
    live_nudge_parser.add_argument("--min-score", type=positive_int, default=1)
    live_nudge_parser.add_argument("--latency-budget-ms", type=positive_int, default=250)
    live_nudge_parser.add_argument("--token-env", default="KNUDG_OPERATOR_TOKEN")
    live_nudge_parser.add_argument("--config")
    live_nudge_parser.set_defaults(func=live_nudge)
    live_write_parser = live_sub.add_parser("write-candidate")
    live_write_parser.add_argument("--card", required=True)
    live_write_parser.add_argument("--workspace", default="closed-beta-agent")
    live_write_parser.add_argument("--token-env", default="KNUDG_OPERATOR_TOKEN")
    live_write_parser.add_argument("--config")
    live_write_parser.set_defaults(func=live_write_candidate)
    live_final_filter = live_sub.add_parser("final-filter")
    live_final_filter_sub = live_final_filter.add_subparsers(dest="action", required=True, parser_class=JsonArgumentParser)
    live_final_filter_stats_parser = live_final_filter_sub.add_parser("stats")
    live_final_filter_stats_parser.add_argument("--token-env", default="KNUDG_OPERATOR_TOKEN")
    live_final_filter_stats_parser.add_argument("--config")
    live_final_filter_stats_parser.add_argument("--timeout-seconds", type=positive_int, default=5)
    live_final_filter_stats_parser.set_defaults(func=live_final_filter_stats)

    migrate = sub.add_parser("migrate")
    migrate_sub = migrate.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    migrate_status_parser = migrate_sub.add_parser("status")
    migrate_status_parser.set_defaults(func=migrate_status)

    db = sub.add_parser("db")
    db_sub = db.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    db_sub.add_parser("status").set_defaults(func=db_status)
    backup = db_sub.add_parser("backup")
    backup_sub = backup.add_subparsers(dest="action", required=True, parser_class=JsonArgumentParser)
    backup_sub.add_parser("status").set_defaults(func=db_backup_status)
    pitr = db_sub.add_parser("pitr")
    pitr_sub = pitr.add_subparsers(dest="action", required=True, parser_class=JsonArgumentParser)
    pitr_plan = pitr_sub.add_parser("plan")
    pitr_plan.add_argument("--target", required=True)
    pitr_plan.set_defaults(func=db_pitr_plan)
    failover = db_sub.add_parser("failover")
    failover.add_argument("--target", required=True)
    failover.add_argument("--reason", required=True)
    failover.set_defaults(func=not_configured, required_operator_role="database_on_call", audit_event="db_failover_requested")

    revocation = sub.add_parser("revocation")
    revocation_sub = revocation.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    rev_status = revocation_sub.add_parser("status")
    rev_status.add_argument("card_id")
    rev_status.add_argument("--tenant", required=True)
    rev_status.set_defaults(func=revocation_status)

    local = sub.add_parser("local")
    local_sub = local.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    local_preflight = local_sub.add_parser("preflight-db")
    local_preflight.set_defaults(func=local_private_preflight_db)
    local_capture = local_sub.add_parser("capture")
    local_capture.add_argument("--tenant", required=True)
    local_capture.add_argument("--namespace", required=True)
    local_capture.add_argument("--created-by", required=True)
    local_capture.add_argument("--input", required=True)
    local_capture.add_argument("--workspace", default="closed-launch-manual")
    local_capture.set_defaults(func=local_private_capture)
    local_search = local_sub.add_parser("search")
    local_search.add_argument("--tenant", required=True)
    local_search.add_argument("--namespace", action="append", required=True)
    local_search.add_argument("--principal", required=True)
    local_search.add_argument("--task-profile", required=True)
    local_search.add_argument("--limit", type=positive_int, default=3)
    local_search.add_argument("--min-score", type=positive_int, default=2)
    local_search.add_argument("--latency-budget-ms", type=positive_int, default=250)
    local_search.add_argument("--workspace", default="closed-launch-manual")
    local_search.set_defaults(func=local_private_search)
    local_revoke = local_sub.add_parser("revoke")
    local_revoke.add_argument("--tenant", required=True)
    local_revoke.add_argument("--namespace", action="append", required=True)
    local_revoke.add_argument("--principal", required=True)
    local_revoke.add_argument("--card-id", required=True)
    local_revoke.add_argument("--reason", required=True)
    local_revoke.add_argument("--workspace", default="closed-launch-manual")
    local_revoke.set_defaults(func=local_private_revoke)
    local_purge = local_sub.add_parser("purge")
    local_purge.add_argument("--tenant", required=True)
    local_purge.add_argument("--namespace", action="append", required=True)
    local_purge.add_argument("--principal", required=True)
    local_purge.add_argument("--card-id", required=True)
    local_purge.add_argument("--reason", required=True)
    local_purge.add_argument("--workspace", default="closed-launch-manual")
    local_purge.set_defaults(func=local_private_purge)
    local_verify = local_sub.add_parser("verify-fences")
    local_verify.add_argument("--tenant", required=True)
    local_verify.add_argument("--card-id", required=True)
    local_verify.add_argument("--principal", required=True)
    local_verify.set_defaults(func=local_private_verify_fences)
    local_audit = local_sub.add_parser("audit-boundary")
    local_audit.add_argument("--tenant", required=True)
    local_audit.add_argument("--principal", required=True)
    local_audit.set_defaults(func=local_private_audit_boundary)

    queue = sub.add_parser("queue")
    queue_sub = queue.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    q_stats = queue_sub.add_parser("stats")
    q_stats.add_argument("--all", action="store_true")
    q_stats.add_argument("--lane")
    q_stats.set_defaults(func=queue_stats)
    q_peek = queue_sub.add_parser("peek")
    q_peek.add_argument("--lane", required=True)
    q_peek.add_argument("--oldest", type=positive_int, default=10)
    q_peek.set_defaults(func=queue_peek)
    q_redrive = queue_sub.add_parser("redrive")
    q_redrive.add_argument("--job", required=True)
    q_redrive.add_argument("--reason", required=True)
    q_redrive_mode = q_redrive.add_mutually_exclusive_group(required=True)
    q_redrive_mode.add_argument("--dry-run", action="store_true")
    q_redrive_mode.add_argument("--apply", action="store_true")
    q_redrive.set_defaults(func=queue_redrive)

    writer = sub.add_parser("writer")
    writer_sub = writer.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    writer_status_parser = writer_sub.add_parser("status")
    writer_status_parser.add_argument("--tenant")
    writer_status_parser.set_defaults(func=writer_status)
    writer_reconcile_parser = writer_sub.add_parser("reconcile")
    writer_reconcile_parser.add_argument("--tenant")
    writer_reconcile_parser.add_argument("--limit", type=positive_int, default=20)
    writer_mode = writer_reconcile_parser.add_mutually_exclusive_group(required=True)
    writer_mode.add_argument("--dry-run", action="store_true")
    writer_mode.add_argument("--apply", action="store_true")
    writer_reconcile_parser.set_defaults(func=writer_reconcile)
    writer_enqueue_parser = writer_sub.add_parser("enqueue-next")
    writer_enqueue_parser.add_argument("--tenant")
    writer_enqueue_parser.add_argument("--limit", type=positive_int, default=20)
    writer_enqueue_parser.add_argument("--priority", type=int, default=0)
    writer_enqueue_parser.add_argument("--max-attempts", type=positive_int, default=3)
    writer_enqueue_mode = writer_enqueue_parser.add_mutually_exclusive_group(required=True)
    writer_enqueue_mode.add_argument("--dry-run", action="store_true")
    writer_enqueue_mode.add_argument("--apply", action="store_true")
    writer_enqueue_parser.set_defaults(func=writer_enqueue_next)
    writer_run_parser = writer_sub.add_parser("run-next")
    writer_run_parser.add_argument("--tenant")
    writer_run_parser.add_argument("--lease-seconds", type=positive_int, default=60)
    writer_run_parser.add_argument("--retry-delay-seconds", type=retry_delay_seconds, default=0)
    writer_run_mode = writer_run_parser.add_mutually_exclusive_group(required=True)
    writer_run_mode.add_argument("--dry-run", action="store_true")
    writer_run_mode.add_argument("--apply", action="store_true")
    writer_run_parser.set_defaults(func=writer_run_next)
    writer_sweep_parser = writer_sub.add_parser("sweep")
    writer_sweep_parser.add_argument("--tenant")
    writer_sweep_parser.add_argument("--limit", type=positive_int, default=20)
    writer_sweep_parser.add_argument("--priority", type=int, default=0)
    writer_sweep_parser.add_argument("--max-attempts", type=positive_int, default=3)
    writer_sweep_mode = writer_sweep_parser.add_mutually_exclusive_group(required=True)
    writer_sweep_mode.add_argument("--dry-run", action="store_true")
    writer_sweep_mode.add_argument("--apply", action="store_true")
    writer_sweep_parser.set_defaults(func=writer_sweep)
    writer_handoff = writer_sub.add_parser("approval-handoff")
    writer_handoff_sub = writer_handoff.add_subparsers(dest="action", required=True, parser_class=JsonArgumentParser)
    writer_handoff_create = writer_handoff_sub.add_parser("create")
    writer_handoff_create.add_argument("--tenant", required=True)
    writer_handoff_create.add_argument("--card", required=True)
    writer_handoff_create_mode = writer_handoff_create.add_mutually_exclusive_group(required=True)
    writer_handoff_create_mode.add_argument("--dry-run", action="store_true")
    writer_handoff_create_mode.add_argument("--apply", action="store_true")
    writer_handoff_create.set_defaults(func=writer_approval_handoff_create)
    writer_handoff_inspect = writer_handoff_sub.add_parser("inspect")
    writer_handoff_inspect.add_argument("--tenant", required=True)
    writer_handoff_inspect.add_argument("--handoff", required=True)
    writer_handoff_inspect.set_defaults(func=writer_approval_handoff_inspect)
    writer_handoff_status = writer_handoff_sub.add_parser("status")
    writer_handoff_status.add_argument("--tenant", required=True)
    writer_handoff_status.add_argument("--handoff", required=True)
    writer_handoff_status.set_defaults(func=writer_approval_handoff_status)

    outbox = sub.add_parser("outbox")
    outbox_sub = outbox.add_subparsers(dest="subcommand", required=True, parser_class=JsonArgumentParser)
    outbox_reconcile_parser = outbox_sub.add_parser("reconcile")
    outbox_reconcile_parser.add_argument("--from-position", type=int, required=True)
    outbox_mode = outbox_reconcile_parser.add_mutually_exclusive_group(required=True)
    outbox_mode.add_argument("--dry-run", action="store_true")
    outbox_mode.add_argument("--apply", action="store_true")
    outbox_reconcile_parser.set_defaults(func=outbox_reconcile)

    for group_name in ("deps", "circuit", "auth", "storage", "index", "workers", "rollout", "admission", "consent", "notifications", "deploy"):
        group = sub.add_parser(group_name)
        group.add_argument("--all", action="store_true")
        group.add_argument("--tenant")
        group.add_argument("--target")
        group.add_argument("--reason")
        group.add_argument("--mode")
        group.add_argument("--generation")
        group.add_argument("--after-green")
        group.add_argument("--after-current-job", action="store_true")
        group.add_argument("--dry-run", action="store_true")
        group.add_argument("--apply", action="store_true")
        group.add_argument("args", nargs="*")
        group.set_defaults(func=not_configured)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "group", None):
        emit("knudgctl", "usage_error", EXIT_USAGE, detail="missing command")
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
