import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from psycopg import sql

from scripts.card_payload import canonical_digest_hex


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"


def admin_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def db_url(name: str) -> str:
    parsed = urlparse(admin_url())
    return urlunparse(parsed._replace(path=f"/{name}"))


def maintenance_url() -> str:
    parsed = urlparse(admin_url())
    dbname = "postgres" if parsed.path not in ("", "/postgres") else "template1"
    return urlunparse(parsed._replace(path=f"/{dbname}"))


def run_migrate(url: str, command: str = "up"):
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "migrate.py"), command],
        cwd=ROOT,
        env=env,
        check=True,
    )


def run_knudgctl(url: str, *args):
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudgctl.py"), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


@pytest.fixture(scope="session")
def migrated_db():
    name = f"knudg_test_{uuid.uuid4().hex}"
    try:
        with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not reachable for M0 schema tests: {exc}")
    url = db_url(name)
    run_migrate(url, "up")
    yield url
    with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
        conn.execute(
            "select pg_terminate_backend(pid) from pg_stat_activity where datname = %s",
            (name,),
        )
        conn.execute(sql.SQL("drop database if exists {}").format(sql.Identifier(name)))


@pytest.fixture()
def conn(migrated_db):
    with psycopg.connect(migrated_db, connect_timeout=3) as connection:
        yield connection


def scalar(conn, query, params=()):
    return conn.execute(query, params).fetchone()[0]


def signed_context(secret: bytes, tenant_id, principal_id, namespace_ids, role="app_user", kid="local-dev", **overrides):
    payload = {
        "audience": "knudg-db-local-m0",
        "request_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "principal_id": str(principal_id),
        "actor_role": role,
        "namespace_ids": [str(item) for item in namespace_ids],
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }
    payload.update(overrides)
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(secret, payload_text.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"alg": "HS256", "kid": kid, "payload": payload_text, "signature": signature}


def card_payload():
    return {
        "outcome_type": "solved",
        "goal": "capture a solved setup path",
        "symptom": "a repeatable setup issue was resolved",
        "environment": {"os": "Windows", "agent_tool": "Codex"},
        "context_fingerprint": {"repo_shape": "pytest + postgres"},
        "successful_path": ["apply the documented migration"],
        "failed_paths": [],
        "known_unknowns": [],
        "scope_limits": ["local M0 validation only"],
        "evidence_strength": "single_session",
        "quality_state": "unreviewed",
        "safety": {
            "safety_class": "low",
            "review_state": "cleared",
            "executable_advice": False,
            "mentions_urls": False,
            "mentions_packages": False,
            "mentions_repositories": False,
            "credential_risk": False,
            "billing_risk": False,
            "deletion_risk": False,
            "network_call_risk": False,
            "verification_state": "single_session",
            "withheld_reason": None,
        },
        "privacy": {"contains_personal_data": False, "source_class": "synthetic"},
        "provenance": {"source": "test fixture", "source_class": "synthetic"},
    }


def seed_base(conn):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    principal = uuid.uuid4()
    other_principal = uuid.uuid4()
    ns_a = uuid.uuid4()
    ns_b = uuid.uuid4()
    kid = f"local-dev-{uuid.uuid4().hex}"
    slug_a = f"tenant-a-{uuid.uuid4().hex}"
    slug_b = f"tenant-b-{uuid.uuid4().hex}"
    secret = b"local-test-secret"
    conn.execute(
        "insert into claim_signing_keys(kid, alg, verify_secret, not_before) values (%s, 'HS256', %s, now() - interval '1 minute')",
        (kid, secret),
    )
    conn.execute(
        "insert into tenants(id, slug, name) values (%s, %s, 'Tenant A'), (%s, %s, 'Tenant B')",
        (tenant_a, slug_a, tenant_b, slug_b),
    )
    conn.execute(
        "insert into principals(id, principal_type, display_name) values (%s, 'human_user', 'A'), (%s, 'human_user', 'B')",
        (principal, other_principal),
    )
    conn.execute(
        """
        insert into tenant_memberships(tenant_id, id, principal_id, membership_role, status, valid_from)
        values (%s, %s, %s, 'member', 'active', now() - interval '1 minute')
        """,
        (tenant_a, uuid.uuid4(), principal),
    )
    conn.execute(
        "insert into namespaces(tenant_id, id, key, name, visibility) values (%s, %s, 'a', 'A', 'private'), (%s, %s, 'b', 'B', 'private')",
        (tenant_a, ns_a, tenant_b, ns_b),
    )
    conn.execute(
        """
        insert into namespace_grants(tenant_id, id, namespace_id, principal_id, grant_scope, status, valid_from)
        values (%s, %s, %s, %s, 'read', 'active', now() - interval '1 minute')
        """,
        (tenant_a, uuid.uuid4(), ns_a, principal),
    )
    conn.commit()
    return tenant_a, tenant_b, principal, ns_a, ns_b, secret, kid


def create_card(conn, tenant_id, ns_id, principal_id, status="candidate_created"):
    card_id = uuid.uuid4()
    version_id = uuid.uuid4()
    payload = card_payload()
    with conn.transaction():
        conn.execute(
            """
            insert into experience_cards(
              tenant_id, id, namespace_id, current_version_id, status,
              outcome_type, quality_state, evidence_strength, created_by
            )
            values (%s, %s, %s, %s, %s, 'solved', 'unreviewed', 'single_session', %s)
            """,
            (tenant_id, card_id, ns_id, version_id, status, principal_id),
        )
        conn.execute(
            """
            insert into card_versions(tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by)
            values (%s, %s, %s, 1, 1, %s, %s, %s)
            """,
            (tenant_id, version_id, card_id, json.dumps(payload), canonical_digest_hex(payload), principal_id),
        )
    return card_id, version_id


def grant_submit(conn, tenant_id, ns_id, principal_id):
    conn.execute(
        """
        update namespace_grants
        set grant_scope = 'submit'
        where tenant_id = %s and namespace_id = %s and principal_id = %s
        """,
        (tenant_id, ns_id, principal_id),
    )
    conn.commit()


def submit_candidate(conn, tenant_id, principal, ns_id, secret, kid, *, idempotency_key="submit-1", request_digest="sha256:req-submit"):
    card_id = uuid.uuid4()
    version_id = uuid.uuid4()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, principal, [ns_id], kid=kid)),))
    row = conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
        from knudg_submit_candidate(
          %s, %s, %s, %s,
          %s, %s, %s, '{}'::jsonb, 'sha256:event-created'
        )
        """,
        (ns_id, card_id, version_id, json.dumps(card_payload()), idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()
    return card_id, version_id, row


def revoke_subject(conn, tenant_id, principal, ns_id, secret, kid, subject_type, subject_id, *, idempotency_key="revoke-1", request_digest="sha256:req-revoke"):
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, principal, [ns_id], kid=kid)),))
    return conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, card_version_id, revocation_epoch
        from knudg_revoke_subject(
          %s, %s, %s, %s, %s, 'test revocation', '{}'::jsonb, 'sha256:event-revoke'
        )
        """,
        (subject_type, subject_id, idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def revoke_consent_record(conn, tenant_id, principal, ns_id, secret, kid, consent_id, *, idempotency_key="consent-revoke-1", request_digest="sha256:req-consent-revoke"):
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, principal, [ns_id], kid=kid)),))
    return conn.execute(
        """
        select event_id, event_stream_position, consent_id, revoked_at
        from knudg_revoke_consent_record(
          %s, %s, %s, %s, 'user withdrew consent', '{}'::jsonb, 'sha256:event-consent-revoke'
        )
        """,
        (consent_id, idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def withdraw_publication_approval(conn, tenant_id, principal, ns_id, secret, kid, card_id, version_id, *, idempotency_key="withdraw-1", request_digest="sha256:req-withdraw"):
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, principal, [ns_id], kid=kid)),))
    return conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, consent_id, revoked_at
        from knudg_withdraw_publication_approval(
          %s, %s, %s, %s, %s, 'user withdrew publication approval', '{}'::jsonb, 'sha256:event-withdraw'
        )
        """,
        (card_id, version_id, idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def break_glass_revoke_subject(conn, tenant_id, principal, secret, kid, case_id, subject_type, subject_id, *, idempotency_key="bg-revoke-1", request_digest="sha256:req-bg-revoke"):
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, principal, [], role="break_glass_admin", kid=kid)),))
    return conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, card_version_id, revocation_epoch, break_glass_case_id
        from knudg_break_glass_revoke_subject(
          %s, %s, %s, %s, %s, %s, 'emergency revocation', '{}'::jsonb, 'sha256:event-bg-revoke'
        )
        """,
        (case_id, subject_type, subject_id, idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def insert_card_event(conn, tenant_id, card_id, principal_id, event_type, prev, nxt, seq=2, role="app_user", expected_current_version=None):
    event_id = uuid.uuid4()
    pos = scalar(conn, "select nextval('event_stream_position_seq')")
    with conn.transaction():
        conn.execute(
            """
            insert into card_events(
              tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
              actor_id, actor_role, previous_status, next_status, expected_current_version, correlation_id,
              idempotency_key, event_payload_schema_version, event_payload_json, event_payload_digest
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'idem', 1, '{}'::jsonb, 'sha256:event')
            """,
            (tenant_id, card_id, event_id, pos, seq, event_type, principal_id, role, prev, nxt, expected_current_version, uuid.uuid4()),
        )
        conn.execute(
            """
            insert into event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id)
            values (%s, %s, 'card', %s)
            """,
            (pos, tenant_id, event_id),
        )
    return event_id, pos


def create_public_publication_consent(conn, tenant_id, ns_id, principal_id):
    card_id, version_id = create_card(conn, tenant_id, ns_id, principal_id, status="approved_for_publication")
    event_id = insert_card_event(
        conn,
        tenant_id,
        card_id,
        principal_id,
        "publication_approved",
        "awaiting_user_approval",
        "approved_for_publication",
        role="app_user",
        expected_current_version=version_id,
    )[0]
    challenge_id = uuid.uuid4()
    conn.execute(
        """
        insert into approval_challenges(
          tenant_id, id, subject_id, namespace_id, consent_scope, artifact_type, artifact_id,
          card_version_id, artifact_digest, policy_version, policy_digest, challenge_digest,
          origin, expires_at, created_by
        )
        values (%s, %s, %s, %s, 'public_publication', 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', 'sha256:challenge', 'local', now() + interval '5 minutes', %s)
        """,
        (tenant_id, challenge_id, principal_id, ns_id, version_id, version_id, principal_id),
    )
    consent_id = uuid.uuid4()
    conn.execute(
        """
        insert into consent_records(
          tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
          artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
          grant_card_event_id, retention_policy, retention_purpose
        )
        values (%s, %s, %s, 'public_publication', %s, 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', %s, 'sha256:challenge', %s, 'retain', 'publish')
        """,
        (tenant_id, consent_id, principal_id, ns_id, version_id, version_id, challenge_id, event_id),
    )
    return card_id, version_id, consent_id


def create_break_glass_case(conn, tenant_id, requested_by, target_type, target_id, *, status="active", operations=None, expires="1 hour"):
    approver_1 = uuid.uuid4()
    approver_2 = uuid.uuid4()
    case_id = uuid.uuid4()
    conn.execute(
        """
        insert into principals(id, principal_type, display_name)
        values (%s, 'human_user', 'Approver 1'), (%s, 'human_user', 'Approver 2')
        """,
        (approver_1, approver_2),
    )
    conn.execute(
        """
        insert into break_glass_cases(
          tenant_id, id, status, target_type, target_id, permitted_operations,
          reason_code, approved_by_1, approved_by_2, requested_by, expires_at
        )
        values (%s, %s, %s, %s, %s, %s, 'emergency_revoke', %s, %s, %s, now() + (%s)::interval)
        """,
        (
            tenant_id,
            case_id,
            status,
            target_type,
            target_id,
            operations or ["break_glass_revoke_subject"],
            approver_1,
            approver_2,
            requested_by,
            expires,
        ),
    )
    conn.execute(
        "update tenant_memberships set membership_role = 'break_glass_admin' where tenant_id = %s and principal_id = %s",
        (tenant_id, requested_by),
    )
    return case_id


def create_worker_identity(conn, tenant_id, role="index_worker", allowed_operations=None):
    worker_id = uuid.uuid4()
    conn.execute(
        "insert into principals(id, principal_type, display_name) values (%s, 'worker', 'Worker')",
        (worker_id,),
    )
    conn.execute(
        """
        insert into tenant_memberships(tenant_id, id, principal_id, membership_role, status, valid_from)
        values (%s, %s, %s, 'worker', 'active', now() - interval '1 minute')
        """,
        (tenant_id, uuid.uuid4(), worker_id),
    )
    conn.execute(
        """
        insert into worker_identities(id, principal_id, worker_role, purpose, allowed_operations)
        values (%s, %s, %s, 'test worker', %s)
        """,
        (uuid.uuid4(), worker_id, role, allowed_operations or ["claim_job", "complete_job", "fail_job"]),
    )
    return worker_id


def set_worker_claims(conn, tenant_id, worker_id, secret, kid, role="index_worker"):
    conn.execute("set role knudg_worker")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, worker_id, [], role=role, kid=kid)),))


def worker_transition(conn, tenant_id, worker_id, secret, kid, role, function_name, card_id, version_id, *, idempotency_key, request_digest):
    set_worker_claims(conn, tenant_id, worker_id, secret, kid, role=role)
    query = sql.SQL(
        """
        select event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
        from {}(%s, %s, %s, %s, %s, '{{}}'::jsonb, 'sha256:event')
        """
    ).format(sql.Identifier(function_name))
    return conn.execute(query, (card_id, version_id, idempotency_key, request_digest, uuid.uuid4())).fetchone()


def complete_redaction(conn, tenant_id, worker_id, secret, kid, card_id, version_id, new_version_id, payload, *, idempotency_key="redaction-complete-1", request_digest="sha256:req-redaction-complete"):
    set_worker_claims(conn, tenant_id, worker_id, secret, kid, role="redaction_worker")
    return conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
        from knudg_complete_redaction(%s, %s, %s, %s, %s, %s, %s, '{}'::jsonb, 'sha256:event-redaction-complete')
        """,
        (card_id, version_id, new_version_id, None if payload is None else json.dumps(payload), idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def request_private_approval(conn, tenant_id, worker_id, secret, kid, card_id, version_id, challenge_id, *, idempotency_key="private-approval-request-1", request_digest="sha256:req-private-approval-request"):
    set_worker_claims(conn, tenant_id, worker_id, secret, kid, role="review_worker")
    return conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id, challenge_id, challenge_digest
        from knudg_request_private_approval(
          %s, %s, %s, 'private-retention-v1', 'sha256:policy-private-v1', 'sha256:challenge-private-v1',
          'local-synthetic-test', now() + interval '5 minutes',
          %s, %s, %s, '{}'::jsonb, 'sha256:event-private-approval-request'
        )
        """,
        (card_id, version_id, challenge_id, idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def approve_private_retention(conn, tenant_id, principal, ns_id, secret, kid, card_id, challenge_id, *, idempotency_key="private-retention-approve-1", request_digest="sha256:req-private-retention-approve"):
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_id, principal, [ns_id], kid=kid)),))
    return conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, consent_id, previous_status, next_status, current_version_id
        from knudg_approve_private_retention(%s, %s, %s, %s, %s, '{}'::jsonb, 'sha256:event-private-retention-approve')
        """,
        (card_id, challenge_id, idempotency_key, request_digest, uuid.uuid4()),
    ).fetchone()


def test_empty_apply_reapply_and_rollback():
    name = f"knudg_migration_{uuid.uuid4().hex}"
    try:
        with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as admin:
            admin.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not reachable for migration tests: {exc}")
    url = db_url(name)
    try:
        run_migrate(url, "up")
        run_migrate(url, "up")
        with psycopg.connect(url, connect_timeout=3) as check:
            expected_migrations = len(list((ROOT / "migrations").glob("*.up.sql")))
            assert scalar(check, "select count(*) from schema_migrations where state = 'applied'") == expected_migrations
        run_migrate(url, "down")
        with psycopg.connect(url, connect_timeout=3) as check:
            assert scalar(check, "select to_regclass('public.experience_cards') is null")
    finally:
        with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as admin:
            admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s", (name,))
            admin.execute(sql.SQL("drop database if exists {}").format(sql.Identifier(name)))


def test_down_migration_keeps_cluster_roles():
    down_sql = (ROOT / "migrations" / "0001_m0_schema.down.sql").read_text(encoding="utf-8")
    assert "revoke all privileges on schema public from knudg_app" in down_sql
    assert "drop role if exists knudg_app" not in down_sql
    assert "drop role if exists knudg_worker" not in down_sql
    assert "drop role if exists knudg_readonly_ops" not in down_sql


def test_m0_migration_static_contracts():
    up_sql = (ROOT / "migrations" / "0001_m0_schema.up.sql").read_text(encoding="utf-8").lower()

    assert "is_current" not in up_sql
    assert re.search(
        r"create\s+unique\s+index\s+if\s+not\s+exists\s+consent_records_one_active_public_approval_uidx"
        r"\s+on\s+consent_records\s*\(\s*tenant_id\s*,\s*card_version_id\s*,\s*scope\s*\)"
        r"\s+where\s+revoked_at\s+is\s+null\s+and\s+scope\s*=\s*'public_publication'"
        r"\s+and\s+artifact_type\s*=\s*'card_version'",
        up_sql,
        re.S,
    )
    assert "'public_publish'" not in up_sql
    for deprecated_scope in (
        "commercial_derived",
        "model_eval'",
        "canonical_trail",
        "aggregate_stats",
        "verified_rewrite",
        "curated_pack",
    ):
        assert deprecated_scope not in up_sql
    for canonical_scope in (
        "public_publication",
        "team_namespace_grant",
        "intake_review_escrow",
        "derived_artifact",
        "commercial_use",
        "model_eval_use",
    ):
        assert canonical_scope in up_sql
    assert "create constraint trigger card_events_position_bijection" in up_sql
    assert "create constraint trigger domain_events_position_bijection" in up_sql
    assert "create constraint trigger event_stream_positions_position_bijection" in up_sql
    assert "create trigger card_versions_append_only before update or delete on card_versions" in up_sql
    assert "create trigger card_events_append_only before update or delete on card_events" in up_sql
    assert "create trigger domain_events_append_only before update or delete on domain_events" in up_sql
    assert "create trigger audit_events_append_only before update or delete on audit_events" in up_sql
    assert "create trigger revocation_tombstones_append_only before update or delete on revocation_tombstones" in up_sql
    assert "grant insert on audit_events" not in up_sql
    assert "payload_digest_alg text not null default 'sha256:jcs-rfc8785:v1'" in up_sql
    assert "check (payload_digest ~ '^[0-9a-f]{64}$')" in up_sql
    security_definer_search_paths = re.findall(
        r"create\s+or\s+replace\s+function\s+.*?security\s+definer.*?set\s+search_path\s*=\s*([^\n]+)",
        up_sql,
        re.S,
    )
    assert security_definer_search_paths
    assert all("public" not in path for path in security_definer_search_paths)


def test_core_constraints_and_lookup_seeds(conn):
    tenant_a, tenant_b, principal, ns_a, ns_b, _secret, _kid = seed_base(conn)
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into namespace_grants(tenant_id, id, namespace_id, principal_id, grant_scope, status, valid_from)
            values (%s, %s, %s, %s, 'read', 'active', now())
            """,
            (tenant_a, uuid.uuid4(), ns_b, principal),
        )
        conn.commit()
    conn.rollback()
    assert scalar(conn, "select count(*) from card_statuses where key = 'approved_for_publication'") == 1
    assert scalar(conn, "select count(*) from actor_roles where key = 'break_glass_admin'") == 1


def test_card_payload_minimum_shape_and_digest_constraints(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)

    def insert_version_with(payload, digest=None):
        card_id = uuid.uuid4()
        version_id = uuid.uuid4()
        with conn.transaction():
            conn.execute(
                """
                insert into experience_cards(
                  tenant_id, id, namespace_id, current_version_id, status,
                  outcome_type, quality_state, evidence_strength, created_by
                )
                values (%s, %s, %s, %s, 'candidate_created', %s, %s, %s, %s)
                """,
                (
                    tenant_a,
                    card_id,
                    ns_a,
                    version_id,
                    payload.get("outcome_type", "solved"),
                    payload.get("quality_state", "unreviewed"),
                    payload.get("evidence_strength", "single_session"),
                    principal,
                ),
            )
            conn.execute(
                """
                insert into card_versions(
                  tenant_id, id, card_id, version_number, card_schema_version,
                  payload_json, payload_digest, created_by
                )
                values (%s, %s, %s, 1, 1, %s, %s, %s)
                """,
                (tenant_a, version_id, card_id, json.dumps(payload), digest or canonical_digest_hex(payload), principal),
            )

    valid = card_payload()
    insert_version_with(valid)

    invalid_digest = card_payload()
    with pytest.raises(psycopg.Error):
        insert_version_with(invalid_digest, digest="sha256:payload-1")
    conn.rollback()

    mismatched_digest = card_payload()
    other_payload = card_payload()
    other_payload["goal"] = "different canonical payload"
    with pytest.raises(psycopg.Error):
        insert_version_with(mismatched_digest, digest=canonical_digest_hex(other_payload))
    conn.rollback()

    projection_owned = card_payload()
    projection_owned["tenant_id"] = str(tenant_a)
    with pytest.raises(psycopg.Error):
        insert_version_with(projection_owned)
    conn.rollback()

    solved_without_path = card_payload()
    solved_without_path["successful_path"] = []
    with pytest.raises(psycopg.Error):
        insert_version_with(solved_without_path)
    conn.rollback()

    failed_only_with_success = card_payload()
    failed_only_with_success["outcome_type"] = "failed_only"
    with pytest.raises(psycopg.Error):
        insert_version_with(failed_only_with_success)
    conn.rollback()

    failed_only_without_failures = card_payload()
    failed_only_without_failures["outcome_type"] = "failed_only"
    failed_only_without_failures["successful_path"] = []
    failed_only_without_failures["failed_paths"] = []
    with pytest.raises(psycopg.Error):
        insert_version_with(failed_only_without_failures)
    conn.rollback()

    unknown_without_unknowns = card_payload()
    unknown_without_unknowns["outcome_type"] = "unknown_clarified"
    unknown_without_unknowns["successful_path"] = []
    unknown_without_unknowns["known_unknowns"] = []
    with pytest.raises(psycopg.Error):
        insert_version_with(unknown_without_unknowns)
    conn.rollback()

    extra_top_level = card_payload()
    extra_top_level["extra"] = "not schema v1"
    with pytest.raises(psycopg.Error):
        insert_version_with(extra_top_level)
    conn.rollback()

    extra_safety = card_payload()
    extra_safety["safety"]["extra"] = True
    with pytest.raises(psycopg.Error):
        insert_version_with(extra_safety)
    conn.rollback()

    non_string_step = card_payload()
    non_string_step["successful_path"] = [{"step": "object"}]
    with pytest.raises(psycopg.Error):
        insert_version_with(non_string_step)
    conn.rollback()

    object_goal = card_payload()
    object_goal["goal"] = {"not": "text"}
    with pytest.raises(psycopg.Error):
        insert_version_with(object_goal)
    conn.rollback()

    bad_optional = card_payload()
    bad_optional["twist"] = {"not": "text"}
    with pytest.raises(psycopg.Error):
        insert_version_with(bad_optional)
    conn.rollback()

    bad_embedding_ref = card_payload()
    bad_embedding_ref["embedding_refs"] = ["not-object"]
    with pytest.raises(psycopg.Error):
        insert_version_with(bad_embedding_ref)
    conn.rollback()


def test_event_cursor_bijection(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_id, _version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = uuid.uuid4()
    with pytest.raises(psycopg.Error):
        with conn.transaction():
            conn.execute(
                """
                insert into card_events(
                  tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
                  actor_id, actor_role, previous_status, next_status, correlation_id,
                  idempotency_key, event_payload_schema_version, event_payload_json, event_payload_digest
                )
                values (%s, %s, %s, nextval('event_stream_position_seq'), 2, 'discard_requested',
                  %s, 'app_user', 'candidate_created', 'discard_pending', %s, 'idem', 1, '{}'::jsonb, 'sha256:event')
                """,
                (tenant_a, card_id, event_id, principal, uuid.uuid4()),
            )
    conn.rollback()
    _event_id, pos = insert_card_event(conn, tenant_a, card_id, principal, "discard_requested", "candidate_created", "discard_pending")
    assert pos > 0


def test_rls_claim_spoof_denial(conn):
    tenant_a, tenant_b, principal, ns_a, ns_b, secret, kid = seed_base(conn)
    create_card(conn, tenant_a, ns_a, principal)
    conn.execute("set role knudg_app")
    conn.execute("select set_config('knudg.claims.tenant_id', %s, true)", (str(tenant_b),))
    with pytest.raises(psycopg.Error):
        conn.execute("select count(*) from experience_cards").fetchone()
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from experience_cards") == 1
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into namespaces(tenant_id, id, key, name, visibility)
            values (%s, %s, 'spoofed', 'Spoofed', 'private')
            """,
            (tenant_b, ns_b),
        )


def test_claim_revalidation_after_revocation(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    create_card(conn, tenant_a, ns_a, principal)
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from experience_cards") == 1
    conn.execute("reset role")
    conn.execute("update tenant_memberships set revoked_at = now(), status = 'revoked' where tenant_id = %s", (tenant_a,))
    conn.execute("set role knudg_app")
    with pytest.raises(psycopg.Error):
        conn.execute("select count(*) from experience_cards").fetchone()


def test_namespace_claims_require_active_grants(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    ungranted_ns = uuid.uuid4()
    conn.execute(
        """
        insert into namespaces(tenant_id, id, key, name, visibility)
        values (%s, %s, 'ungranted', 'Ungranted', 'private')
        """,
        (tenant_a, ungranted_ns),
    )
    conn.commit()

    conn.execute("set role knudg_app")
    with pytest.raises(psycopg.Error):
        conn.execute(
            "select knudg_set_claims(%s::jsonb)",
            (json.dumps(signed_context(secret, tenant_a, principal, [ungranted_ns], kid=kid)),),
        )
    conn.rollback()

    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from namespaces") == 1
    conn.execute("reset role")
    conn.execute("update namespace_grants set revoked_at = now(), status = 'revoked' where tenant_id = %s", (tenant_a,))
    conn.execute("set role knudg_app")
    with pytest.raises(psycopg.Error):
        conn.execute("select count(*) from namespaces").fetchone()


def test_lifecycle_transitions(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_id, _version_id = create_card(conn, tenant_a, ns_a, principal)
    insert_card_event(conn, tenant_a, card_id, principal, "discard_requested", "candidate_created", "discard_pending")
    with pytest.raises(psycopg.Error):
        insert_card_event(conn, tenant_a, card_id, principal, "reviewer_published", "candidate_created", "published", seq=3, role="reviewer")


def test_app_role_appends_card_event_through_function(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    assert created[2] == 1
    assert created[4] is None
    assert created[5] == "candidate_created"
    conn.commit()
    conn.execute("reset role")
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    row = conn.execute(
        """
        select event_id, event_stream_position, event_seq, previous_status, next_status, current_version_id
        from knudg_append_card_event(
          %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
          'append-1', 'sha256:req-append-1', %s, '{}'::jsonb, 'sha256:event-append-1'
        )
        """,
        (card_id, version_id, uuid.uuid4()),
    ).fetchone()
    assert row[2] == 2
    assert row[3] == "candidate_created"
    assert row[4] == "discard_pending"
    assert row[5] == version_id
    assert scalar(conn, "select status = 'discard_pending' from experience_cards where id = %s", (card_id,))
    assert scalar(conn, "select count(*) from card_events where card_id = %s", (card_id,)) == 2
    assert scalar(conn, "select count(*) from idempotency_keys where logical_object_id = %s", (card_id,)) == 2

    replay = conn.execute(
        """
        select event_id, event_stream_position, event_seq
        from knudg_append_card_event(
          %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
          'append-1', 'sha256:req-append-1', %s, '{}'::jsonb, 'sha256:event-append-1'
        )
        """,
        (card_id, version_id, uuid.uuid4()),
    ).fetchone()
    assert replay == row[:3]


def test_app_role_submits_candidate_through_creation_function(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, row = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    assert row[2] == 1
    assert row[3] == card_id
    assert row[4] is None
    assert row[5] == "candidate_created"
    assert row[6] == version_id
    assert scalar(conn, "select current_version_id = %s from experience_cards where id = %s", (version_id, card_id))
    assert scalar(conn, "select count(*) from card_versions where card_id = %s", (card_id,)) == 1
    assert scalar(conn, "select payload_digest from card_versions where card_id = %s", (card_id,)) == canonical_digest_hex(card_payload())
    assert scalar(conn, "select payload_digest_alg from card_versions where card_id = %s", (card_id,)) == "sha256:jcs-rfc8785:v1"
    assert scalar(conn, "select count(*) from card_events where card_id = %s and event_type = 'card_created'", (card_id,)) == 1
    conn.execute("reset role")
    assert scalar(conn, "select count(*) from event_stream_positions where card_event_id = %s", (row[0],)) == 1

    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    replay = conn.execute(
        """
        select event_id, event_stream_position, event_seq, card_id, previous_status, next_status, current_version_id
        from knudg_submit_candidate(
          %s, %s, %s, %s,
          'submit-1', 'sha256:req-submit', %s, '{}'::jsonb, 'sha256:event-created'
        )
        """,
        (ns_a, card_id, version_id, json.dumps(card_payload()), uuid.uuid4()),
    ).fetchone()
    assert replay == row

    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_submit_candidate(
              %s, %s, %s, %s,
              'submit-1', 'sha256:req-conflict', %s, '{}'::jsonb, 'sha256:event-created'
            )
            """,
            (ns_a, card_id, version_id, json.dumps(card_payload()), uuid.uuid4()),
        )


def test_private_writer_flow_reaches_approved_private_with_bound_consent(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    ingestion_worker = create_worker_identity(conn, tenant_a, role="ingestion_worker", allowed_operations=["accept_admission", "request_redaction"])
    redaction_worker = create_worker_identity(conn, tenant_a, role="redaction_worker", allowed_operations=["complete_redaction"])
    review_worker = create_worker_identity(conn, tenant_a, role="review_worker", allowed_operations=["request_private_approval"])
    conn.commit()

    card_id, original_version_id, created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    assert created[5] == "candidate_created"
    conn.commit()
    conn.execute("reset role")

    accepted = worker_transition(
        conn, tenant_a, ingestion_worker, secret, kid, "ingestion_worker", "knudg_accept_admission",
        card_id, original_version_id, idempotency_key="admission-1", request_digest="sha256:req-admission-1"
    )
    assert accepted[4:7] == ("candidate_created", "pending_admission", original_version_id)
    requested = worker_transition(
        conn, tenant_a, ingestion_worker, secret, kid, "ingestion_worker", "knudg_request_redaction",
        card_id, original_version_id, idempotency_key="redaction-request-1", request_digest="sha256:req-redaction-request-1"
    )
    assert requested[4:7] == ("pending_admission", "pending_redaction", original_version_id)

    redacted_payload = card_payload()
    redacted_payload["goal"] = "capture a redacted solved setup path"
    new_version_id = uuid.uuid4()
    completed = complete_redaction(conn, tenant_a, redaction_worker, secret, kid, card_id, original_version_id, new_version_id, redacted_payload)
    assert completed[4:7] == ("pending_redaction", "pending_review", new_version_id)
    conn.execute("reset role")
    assert scalar(conn, "select current_version_id = %s from experience_cards where id = %s", (new_version_id, card_id))
    assert scalar(conn, "select version_number from card_versions where id = %s", (new_version_id,)) == 2
    assert scalar(conn, "select payload_digest from card_versions where id = %s", (new_version_id,)) == canonical_digest_hex(redacted_payload)

    challenge_id = uuid.uuid4()
    approval_request = request_private_approval(conn, tenant_a, review_worker, secret, kid, card_id, new_version_id, challenge_id)
    assert approval_request[4:9] == ("pending_review", "awaiting_user_approval", new_version_id, challenge_id, "sha256:challenge-private-v1")
    conn.execute("reset role")
    assert scalar(conn, "select consent_scope from approval_challenges where id = %s", (challenge_id,)) == "private_retention"
    assert scalar(conn, "select artifact_id = %s from approval_challenges where id = %s", (new_version_id, challenge_id))
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        request_private_approval(conn, tenant_a, review_worker, secret, kid, card_id, new_version_id, uuid.uuid4())
    conn.rollback()
    conn.execute("reset role")

    conn.commit()
    conn.execute("reset role")
    approval = approve_private_retention(conn, tenant_a, principal, ns_a, secret, kid, card_id, challenge_id)
    consent_id = approval[4]
    assert approval[5:8] == ("awaiting_user_approval", "approved_private", new_version_id)
    assert scalar(conn, "select status from experience_cards where id = %s", (card_id,)) == "approved_private"
    assert scalar(conn, "select scope from consent_records where id = %s", (consent_id,)) == "private_retention"
    assert scalar(conn, "select used_by_consent_id = %s from approval_challenges where id = %s", (consent_id, challenge_id))

    replay = approve_private_retention(conn, tenant_a, principal, ns_a, secret, kid, card_id, challenge_id)
    assert replay == approval
    conn.commit()
    conn.execute("reset role")
    with pytest.raises(psycopg.Error):
        approve_private_retention(conn, tenant_a, principal, ns_a, secret, kid, card_id, uuid.uuid4())
    conn.rollback()
    conn.execute("reset role")
    with pytest.raises(psycopg.Error):
        approve_private_retention(
            conn,
            tenant_a,
            principal,
            ns_a,
            secret,
            kid,
            card_id,
            challenge_id,
            idempotency_key="private-retention-approve-1",
            request_digest="sha256:req-private-retention-conflict",
        )


def test_private_writer_flow_rejects_unallowed_worker_operation(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    worker_id = create_worker_identity(conn, tenant_a, role="ingestion_worker", allowed_operations=["request_redaction"])
    conn.commit()
    card_id, version_id, _row = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        worker_transition(
            conn, tenant_a, worker_id, secret, kid, "ingestion_worker", "knudg_accept_admission",
            card_id, version_id, idempotency_key="admission-denied", request_digest="sha256:req-admission-denied"
        )
    conn.rollback()
    conn.execute("reset role")
    assert scalar(conn, "select status from experience_cards where id = %s", (card_id,)) == "candidate_created"

    conn.execute(
        "update worker_identities set allowed_operations = array['accept_admission'] where principal_id = %s",
        (worker_id,),
    )
    conn.commit()
    set_worker_claims(conn, tenant_a, worker_id, secret, kid, role="ingestion_worker")
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select *
            from knudg_private.worker_advance_card(
              'accept_admission', 'ingestion_worker', 'admission_accepted',
              array['candidate_created'], 'pending_admission',
              %s, %s, 'direct-helper-denied', 'sha256:req-direct-helper-denied',
              %s, '{}'::jsonb, 'sha256:event-direct-helper-denied'
            )
            """,
            (card_id, version_id, uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")
    assert scalar(conn, "select status from experience_cards where id = %s", (card_id,)) == "candidate_created"


def test_private_retention_approval_requires_submit_scope_and_active_challenge(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    ingestion_worker = create_worker_identity(conn, tenant_a, role="ingestion_worker", allowed_operations=["accept_admission", "request_redaction"])
    redaction_worker = create_worker_identity(conn, tenant_a, role="redaction_worker", allowed_operations=["complete_redaction"])
    review_worker = create_worker_identity(conn, tenant_a, role="review_worker", allowed_operations=["request_private_approval"])
    conn.commit()
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    worker_transition(conn, tenant_a, ingestion_worker, secret, kid, "ingestion_worker", "knudg_accept_admission", card_id, version_id, idempotency_key="admission-guard", request_digest="sha256:req-admission-guard")
    worker_transition(conn, tenant_a, ingestion_worker, secret, kid, "ingestion_worker", "knudg_request_redaction", card_id, version_id, idempotency_key="redaction-request-guard", request_digest="sha256:req-redaction-request-guard")
    completed = complete_redaction(conn, tenant_a, redaction_worker, secret, kid, card_id, version_id, None, None, idempotency_key="redaction-complete-guard", request_digest="sha256:req-redaction-complete-guard")
    challenge_id = uuid.uuid4()
    request_private_approval(conn, tenant_a, review_worker, secret, kid, card_id, completed[6], challenge_id, idempotency_key="private-approval-request-guard", request_digest="sha256:req-private-approval-request-guard")
    conn.commit()
    conn.execute("reset role")
    conn.execute(
        "update namespace_grants set grant_scope = 'read' where tenant_id = %s and namespace_id = %s and principal_id = %s",
        (tenant_a, ns_a, principal),
    )
    conn.commit()

    with pytest.raises(psycopg.Error):
        approve_private_retention(conn, tenant_a, principal, ns_a, secret, kid, card_id, challenge_id, idempotency_key="private-retention-readonly", request_digest="sha256:req-private-retention-readonly")
    conn.rollback()
    conn.execute("reset role")
    assert scalar(conn, "select used_by_consent_id is null from approval_challenges where id = %s", (challenge_id,))


def test_submit_candidate_rejects_duplicate_payload_keys_before_jsonb(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    raw_payload = json.dumps(card_payload())
    duplicate_raw = raw_payload.replace('"goal": "capture a solved setup path"', '"goal": "first", "goal": "second"')
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_submit_candidate(
              %s, %s, %s, %s,
              'submit-duplicate-key', 'sha256:req-duplicate-key', %s, '{}'::jsonb, 'sha256:event-created'
            )
            """,
            (ns_a, uuid.uuid4(), uuid.uuid4(), duplicate_raw, uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")
    assert scalar(conn, "select count(*) from experience_cards where tenant_id = %s", (tenant_a,)) == 0


def test_submit_candidate_rejects_non_ascii_payload_keys(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    payload = card_payload()
    payload["environment"]["\u30c4\u30fc\u30eb"] = "Codex"
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_submit_candidate(
              %s, %s, %s, %s,
              'submit-non-ascii-key', 'sha256:req-non-ascii-key', %s, '{}'::jsonb, 'sha256:event-created'
            )
            """,
            (ns_a, uuid.uuid4(), uuid.uuid4(), json.dumps(payload), uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")
    assert scalar(conn, "select count(*) from experience_cards where tenant_id = %s", (tenant_a,)) == 0


def test_submit_candidate_rejects_non_portable_payload_numbers(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    payload = card_payload()
    payload["environment"]["confidence"] = 0.5
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_submit_candidate(
              %s, %s, %s, %s,
              'submit-float', 'sha256:req-float', %s, '{}'::jsonb, 'sha256:event-created'
            )
            """,
            (ns_a, uuid.uuid4(), uuid.uuid4(), json.dumps(payload), uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")

    payload = card_payload()
    payload["environment"]["large"] = 9007199254740992
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_submit_candidate(
              %s, %s, %s, %s,
              'submit-unsafe-int', 'sha256:req-unsafe-int', %s, '{}'::jsonb, 'sha256:event-created'
            )
            """,
            (ns_a, uuid.uuid4(), uuid.uuid4(), json.dumps(payload), uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")
    assert scalar(conn, "select count(*) from experience_cards where tenant_id = %s", (tenant_a,)) == 0


def test_submit_candidate_rejects_non_synthetic_source_class(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)

    for index, mutate in enumerate(
        (
            lambda payload: payload["privacy"].pop("source_class"),
            lambda payload: payload["privacy"].update(source_class="private_session"),
            lambda payload: payload["provenance"].update(source_class="private_session"),
        ),
        start=1,
    ):
        payload = card_payload()
        mutate(payload)
        candidate_id = uuid.uuid4()
        version_id = uuid.uuid4()
        conn.execute("set role knudg_app")
        conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
        with pytest.raises(psycopg.Error):
            conn.execute(
                """
                select * from knudg_submit_candidate(
                  %s, %s, %s, %s,
                  %s, %s, %s, '{}'::jsonb, 'sha256:event-created'
                )
                """,
                (
                    ns_a,
                    candidate_id,
                    version_id,
                    json.dumps(payload),
                    f"submit-source-class-{index}",
                    f"sha256:req-source-class-{index}",
                    uuid.uuid4(),
                ),
            )
        conn.rollback()
        conn.execute("reset role")
        assert scalar(conn, "select count(*) from experience_cards where id = %s", (candidate_id,)) == 0
        assert scalar(conn, "select count(*) from card_versions where id = %s", (version_id,)) == 0
        assert scalar(conn, "select count(*) from idempotency_keys where logical_object_id = %s", (candidate_id,)) == 0


def test_card_versions_table_rejects_non_synthetic_payload(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    payload = card_payload()
    payload["privacy"]["source_class"] = "private_session"
    card_id = uuid.uuid4()
    version_id = uuid.uuid4()
    with pytest.raises(psycopg.Error):
        with conn.transaction():
            conn.execute(
                """
                insert into experience_cards(
                  tenant_id, id, namespace_id, current_version_id, status,
                  outcome_type, quality_state, evidence_strength, created_by
                )
                values (%s, %s, %s, %s, 'candidate_created', 'solved', 'unreviewed', 'single_session', %s)
                """,
                (tenant_a, card_id, ns_a, version_id, principal),
            )
            conn.execute(
                """
                insert into card_versions(
                  tenant_id, id, card_id, version_number, card_schema_version,
                  payload_json, payload_digest, created_by
                )
                values (%s, %s, %s, 1, 1, %s, %s, %s)
                """,
                (tenant_a, version_id, card_id, json.dumps(payload), canonical_digest_hex(payload), principal),
            )
    conn.rollback()
    assert scalar(conn, "select count(*) from card_versions where id = %s", (version_id,)) == 0


def test_read_only_namespace_grant_cannot_submit_or_append(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_submit_candidate(
              %s, %s, %s, %s,
              'submit-readonly', 'sha256:req-readonly', %s, '{}'::jsonb, 'sha256:event-created'
            )
            """,
            (ns_a, uuid.uuid4(), uuid.uuid4(), json.dumps(card_payload()), uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_append_card_event(
              %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
              'append-readonly', 'sha256:req-readonly', %s, '{}'::jsonb, 'sha256:event'
            )
            """,
            (card_id, version_id, uuid.uuid4()),
        )


def test_app_role_append_rejects_stale_projection_and_digest_conflict(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_append_card_event(
              %s, 'discard_requested', %s, 'pending_review', 'discard_pending',
              'append-stale-status', 'sha256:req-stale-status', %s, '{}'::jsonb, 'sha256:event'
            )
            """,
            (card_id, version_id, uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_append_card_event(
              %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
              'append-stale-version', 'sha256:req-stale-version', %s, '{}'::jsonb, 'sha256:event'
            )
            """,
            (card_id, uuid.uuid4(), uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    conn.execute(
        """
        select * from knudg_append_card_event(
          %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
          'append-conflict', 'sha256:req-1', %s, '{}'::jsonb, 'sha256:event'
        )
        """,
        (card_id, version_id, uuid.uuid4()),
    )
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_append_card_event(
              %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
              'append-conflict', 'sha256:req-2', %s, '{}'::jsonb, 'sha256:event'
            )
            """,
            (card_id, version_id, uuid.uuid4()),
        )


def test_app_role_cannot_directly_mutate_event_owned_tables(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute("update experience_cards set status = 'discard_pending' where id = %s", (card_id,))
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into card_events(
              tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
              actor_id, actor_role, previous_status, next_status, expected_current_version,
              correlation_id, idempotency_key, event_payload_schema_version, event_payload_json, event_payload_digest
            )
            values (%s, %s, %s, nextval('event_stream_position_seq'), 1, 'discard_requested',
              %s, 'app_user', 'candidate_created', 'discard_pending', %s,
              %s, 'direct-event', 1, '{}'::jsonb, 'sha256:event')
            """,
            (tenant_a, card_id, uuid.uuid4(), principal, version_id, uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into idempotency_keys(
              tenant_id, id, operation, logical_object_type, logical_object_id, operation_version,
              idempotency_key, request_digest, response_digest, effect_event_source_type, effect_card_event_id
            )
            values (%s, %s, 'append_card_event', 'card', %s, 1, 'direct-idem', 'sha256:req', 'sha256:resp', 'card', %s)
            """,
            (tenant_a, uuid.uuid4(), card_id, uuid.uuid4()),
        )


def test_revocation_tombstones_hide_cards(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "revoked", "candidate_created", "revoked", expected_current_version=version_id)[0]
    conn.execute(
        """
        insert into revocation_tombstones(
          tenant_id, id, subject_type, subject_id, card_id, card_version_id, revocation_epoch,
          revocation_event_source_type, card_revocation_event_id, revoked_by, reason
        )
        values (%s, %s, 'card_version', %s, %s, %s, 1, 'card', %s, %s, 'test')
        """,
        (tenant_a, uuid.uuid4(), version_id, card_id, version_id, event_id, principal),
    )
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from experience_cards where id = %s", (card_id,)) == 0
    assert scalar(conn, "select count(*) from card_versions where card_id = %s", (card_id,)) == 0
    assert scalar(conn, "select count(*) from card_events where card_id = %s", (card_id,)) == 0


def test_card_version_tombstone_hides_matching_version_events(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "revoked", "candidate_created", "revoked", expected_current_version=version_id)[0]
    conn.execute(
        """
        insert into revocation_tombstones(
          tenant_id, id, subject_type, subject_id, card_id, card_version_id, revocation_epoch,
          revocation_event_source_type, card_revocation_event_id, revoked_by, reason
        )
        values (%s, %s, 'card_version', %s, %s, %s, 1, 'card', %s, %s, 'test')
        """,
        (tenant_a, uuid.uuid4(), version_id, card_id, version_id, event_id, principal),
    )
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from card_events where event_id = %s", (event_id,)) == 0


def test_append_replay_respects_revocation_fence(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    row = conn.execute(
        """
        select event_id, event_stream_position, event_seq
        from knudg_append_card_event(
          %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
          'append-before-revoke', 'sha256:req-before-revoke', %s, '{}'::jsonb, 'sha256:event'
        )
        """,
        (card_id, version_id, uuid.uuid4()),
    ).fetchone()
    conn.commit()
    conn.execute("reset role")
    revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card_version", version_id)
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select * from knudg_append_card_event(
              %s, 'discard_requested', %s, 'candidate_created', 'discard_pending',
              'append-before-revoke', 'sha256:req-before-revoke', %s, '{}'::jsonb, 'sha256:event'
            )
            """,
            (card_id, version_id, uuid.uuid4()),
        )


def test_revoke_subject_card_allocates_epoch_and_hides_card(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    row = revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)
    assert row[2] == 2
    assert row[3] == card_id
    assert row[4] == version_id
    assert row[5] == 1
    conn.commit()

    conn.execute("reset role")
    assert scalar(conn, "select last_epoch from tenant_revocation_epochs where tenant_id = %s", (tenant_a,)) == 1
    assert scalar(conn, "select status = 'revoked' from experience_cards where id = %s", (card_id,))
    assert scalar(conn, "select count(*) from revocation_tombstones where card_revocation_event_id = %s and revoked_by = %s", (row[0], principal)) == 1
    assert scalar(conn, "select count(*) from audit_events where action = 'revoke_subject' and target_id = %s", (card_id,)) == 1

    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from experience_cards where id = %s", (card_id,)) == 0
    assert scalar(conn, "select count(*) from card_versions where id = %s", (version_id,)) == 0
    assert scalar(conn, "select count(*) from card_events where card_id = %s", (card_id,)) == 0

    replay = revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)
    assert replay == row
    with pytest.raises(psycopg.Error):
        revoke_subject(
            conn,
            tenant_a,
            principal,
            ns_a,
            secret,
            kid,
            "card",
            card_id,
            idempotency_key="revoke-1",
            request_digest="sha256:req-revoke-conflict",
        )


def test_revoke_subject_replay_revalidates_namespace_scope(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, _version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)
    conn.commit()
    conn.execute("reset role")
    conn.execute(
        """
        update namespace_grants
        set status = 'revoked', revoked_at = now()
        where tenant_id = %s and namespace_id = %s and principal_id = %s
        """,
        (tenant_a, ns_a, principal),
    )
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)


def test_revoke_subject_concurrent_duplicate_replays_after_first_commit(migrated_db):
    with psycopg.connect(migrated_db, connect_timeout=3) as first_conn:
        tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(first_conn)
        grant_submit(first_conn, tenant_a, ns_a, principal)
        card_id, _version_id, _created = submit_candidate(first_conn, tenant_a, principal, ns_a, secret, kid)
        first_conn.commit()
        first_conn.execute("reset role")

        first_row = revoke_subject(first_conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)
        started = threading.Event()

        def duplicate_revoke():
            with psycopg.connect(migrated_db, connect_timeout=3) as second_conn:
                started.set()
                row = revoke_subject(second_conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)
                second_conn.commit()
                return row

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(duplicate_revoke)
            assert started.wait(timeout=3)
            first_conn.commit()
            assert future.result(timeout=5) == first_row


def test_break_glass_revoke_subject_requires_active_scoped_case(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    case_id = create_break_glass_case(conn, tenant_a, principal, "card", card_id)
    conn.commit()
    conn.execute("reset role")

    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [], role="app_user", kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select event_id
            from knudg_break_glass_revoke_subject(
              %s, 'card', %s, 'bg-revoke-ordinary', 'sha256:req-bg-revoke-ordinary',
              %s, 'ordinary actor rejected', '{}'::jsonb, 'sha256:event-bg-revoke'
            )
            """,
            (case_id, card_id, uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("reset role")

    row = break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, case_id, "card", card_id)
    assert row[3] == card_id
    assert row[4] == version_id
    assert row[5] == 1
    assert row[6] == case_id
    conn.commit()
    conn.execute("reset role")

    assert scalar(conn, "select status = 'revoked' from experience_cards where id = %s", (card_id,))
    assert scalar(conn, "select count(*) from audit_events where action = 'break_glass_revoke_subject' and target_id = %s", (card_id,)) == 1
    assert scalar(conn, "select count(*) from revocation_tombstones where card_revocation_event_id = %s", (row[0],)) == 1

    replay = break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, case_id, "card", card_id)
    assert replay == row


def test_break_glass_revoke_subject_rejects_expired_or_wrong_scope_case(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, _version_id = create_card(conn, tenant_a, ns_a, principal)
    other_card_id, _other_version_id = create_card(conn, tenant_a, ns_a, principal)
    wrong_case_id = create_break_glass_case(conn, tenant_a, principal, "card", other_card_id)
    expired_case_id = create_break_glass_case(conn, tenant_a, principal, "card", card_id)
    conn.execute(
        "update break_glass_cases set created_at = now() - interval '2 hours', expires_at = now() - interval '1 hour' where id = %s",
        (expired_case_id,),
    )
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, wrong_case_id, "card", card_id)
    conn.rollback()
    conn.execute("reset role")
    with pytest.raises(psycopg.Error):
        break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, expired_case_id, "card", card_id)


def test_break_glass_revoke_subject_rejects_wrong_operation_and_non_admin_membership(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, _version_id = create_card(conn, tenant_a, ns_a, principal)
    wrong_operation_case_id = create_break_glass_case(conn, tenant_a, principal, "card", card_id, operations=["read_private_card"])
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, wrong_operation_case_id, "card", card_id)
    conn.rollback()
    conn.execute("reset role")
    conn.execute(
        "update tenant_memberships set membership_role = 'member' where tenant_id = %s and principal_id = %s",
        (tenant_a, principal),
    )
    conn.commit()
    conn.execute("reset role")

    case_id = create_break_glass_case(conn, tenant_a, principal, "card", card_id)
    conn.execute(
        "update tenant_memberships set membership_role = 'member' where tenant_id = %s and principal_id = %s",
        (tenant_a, principal),
    )
    conn.commit()
    conn.execute("reset role")
    with pytest.raises(psycopg.Error):
        break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, case_id, "card", card_id)


def test_break_glass_revoke_subject_rejects_non_current_card_version(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, old_version_id = create_card(conn, tenant_a, ns_a, principal)
    new_version_id = uuid.uuid4()
    payload = card_payload()
    with conn.transaction():
        conn.execute(
            """
            insert into card_versions(tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by)
            values (%s, %s, %s, 2, 1, %s, %s, %s)
            """,
            (tenant_a, new_version_id, card_id, json.dumps(payload), canonical_digest_hex(payload), principal),
        )
        conn.execute(
            "update experience_cards set current_version_id = %s where tenant_id = %s and id = %s",
            (new_version_id, tenant_a, card_id),
        )
    case_id = create_break_glass_case(conn, tenant_a, principal, "card", card_id)
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, case_id, "card_version", old_version_id)


def test_break_glass_revoke_subject_supports_namespace_scoped_case_without_namespace_claim(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    case_id = create_break_glass_case(conn, tenant_a, principal, "namespace", ns_a)
    conn.commit()
    conn.execute("reset role")

    row = break_glass_revoke_subject(conn, tenant_a, principal, secret, kid, case_id, "card_version", version_id)
    assert row[3] == card_id
    assert row[4] == version_id
    assert row[6] == case_id


def test_app_role_cannot_read_or_write_break_glass_cases(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, _version_id = create_card(conn, tenant_a, ns_a, principal)
    case_id = create_break_glass_case(conn, tenant_a, principal, "card", card_id)
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute("select count(*) from break_glass_cases where id = %s", (case_id,))
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into break_glass_cases(
              tenant_id, id, status, target_type, target_id, permitted_operations,
              reason_code, approved_by_1, approved_by_2, requested_by, expires_at
            )
            values (%s, %s, 'active', 'card', %s, array['break_glass_revoke_subject'],
              'spoof', %s, %s, %s, now() + interval '1 hour')
            """,
            (tenant_a, uuid.uuid4(), card_id, principal, uuid.uuid4(), principal),
        )
    conn.rollback()
    conn.execute("set role knudg_worker")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute("select count(*) from break_glass_cases where id = %s", (case_id,))


def test_revoke_subject_card_version_allocates_monotonic_epoch(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_a, version_a, _created_a = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid, idempotency_key="submit-a", request_digest="sha256:req-submit-a")
    conn.commit()
    conn.execute("reset role")
    card_b, version_b, _created_b = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid, idempotency_key="submit-b", request_digest="sha256:req-submit-b")
    conn.commit()
    conn.execute("reset role")

    first = revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card_version", version_a, idempotency_key="revoke-a", request_digest="sha256:req-revoke-a")
    conn.commit()
    conn.execute("reset role")
    second = revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card_version", version_b, idempotency_key="revoke-b", request_digest="sha256:req-revoke-b")
    conn.commit()

    assert first[3] == card_a
    assert first[4] == version_a
    assert first[5] == 1
    assert second[3] == card_b
    assert second[4] == version_b
    assert second[5] == 2
    conn.execute("reset role")
    assert scalar(conn, "select last_epoch from tenant_revocation_epochs where tenant_id = %s", (tenant_a,)) == 2


def test_revoke_subject_rejects_non_current_card_version(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, old_version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    new_version_id = uuid.uuid4()
    payload = card_payload()
    with conn.transaction():
        conn.execute(
            """
            insert into card_versions(tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by)
            values (%s, %s, %s, 2, 1, %s, %s, %s)
            """,
            (tenant_a, new_version_id, card_id, json.dumps(payload), canonical_digest_hex(payload), principal),
        )
        conn.execute(
            "update experience_cards set current_version_id = %s where tenant_id = %s and id = %s",
            (new_version_id, tenant_a, card_id),
        )
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card_version", old_version_id)


def test_revocation_tombstones_reject_mismatched_card_version_subject(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_a, version_a = create_card(conn, tenant_a, ns_a, principal)
    card_b, version_b = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_a, principal, "revoked", "candidate_created", "revoked")[0]
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into revocation_tombstones(
              tenant_id, id, subject_type, subject_id, card_id, card_version_id, revocation_epoch,
              revocation_event_source_type, card_revocation_event_id, revoked_by, reason
            )
            values (%s, %s, 'card_version', %s, %s, %s, 1, 'card', %s, %s, 'mismatch')
            """,
            (tenant_a, uuid.uuid4(), version_b, card_a, version_b, event_id, principal),
        )
    conn.rollback()
    assert card_b != card_a
    assert version_a != version_b


def test_revocation_tombstones_reject_wrong_card_version_event_binding(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_id, old_version_id = create_card(conn, tenant_a, ns_a, principal)
    new_version_id = uuid.uuid4()
    payload = card_payload()
    with conn.transaction():
        conn.execute(
            """
            insert into card_versions(tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by)
            values (%s, %s, %s, 2, 1, %s, %s, %s)
            """,
            (tenant_a, new_version_id, card_id, json.dumps(payload), canonical_digest_hex(payload), principal),
        )
        conn.execute(
            "update experience_cards set current_version_id = %s where tenant_id = %s and id = %s",
            (new_version_id, tenant_a, card_id),
        )
    event_id = insert_card_event(
        conn,
        tenant_a,
        card_id,
        principal,
        "revoked",
        "candidate_created",
        "revoked",
        expected_current_version=new_version_id,
    )[0]
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into revocation_tombstones(
              tenant_id, id, subject_type, subject_id, card_id, card_version_id, revocation_epoch,
              revocation_event_source_type, card_revocation_event_id, revoked_by, reason
            )
            values (%s, %s, 'card_version', %s, %s, %s, 1, 'card', %s, %s, 'wrong version event')
            """,
            (tenant_a, uuid.uuid4(), old_version_id, card_id, old_version_id, event_id, principal),
        )
        conn.execute("set constraints revocation_tombstones_event_consistency immediate")


def test_revocation_tombstones_reject_wrong_card_event_binding(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_id, old_version_id = create_card(conn, tenant_a, ns_a, principal)
    new_version_id = uuid.uuid4()
    payload = card_payload()
    with conn.transaction():
        conn.execute(
            """
            insert into card_versions(tenant_id, id, card_id, version_number, card_schema_version, payload_json, payload_digest, created_by)
            values (%s, %s, %s, 2, 1, %s, %s, %s)
            """,
            (tenant_a, new_version_id, card_id, json.dumps(payload), canonical_digest_hex(payload), principal),
        )
        conn.execute(
            "update experience_cards set current_version_id = %s where tenant_id = %s and id = %s",
            (new_version_id, tenant_a, card_id),
        )
    event_id = insert_card_event(
        conn,
        tenant_a,
        card_id,
        principal,
        "revoked",
        "candidate_created",
        "revoked",
        expected_current_version=new_version_id,
    )[0]
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into revocation_tombstones(
              tenant_id, id, subject_type, subject_id, card_id, card_version_id, revocation_epoch,
              revocation_event_source_type, card_revocation_event_id, revoked_by, reason
            )
            values (%s, %s, 'card', %s, %s, %s, 1, 'card', %s, %s, 'wrong card event version')
            """,
            (tenant_a, uuid.uuid4(), card_id, card_id, old_version_id, event_id, principal),
        )
        conn.execute("set constraints revocation_tombstones_event_consistency immediate")


def test_revocation_tombstones_reject_mismatched_actor(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    other_principal = uuid.uuid4()
    conn.execute("insert into principals(id, principal_type, display_name) values (%s, 'human_user', 'Other')", (other_principal,))
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "revoked", "candidate_created", "revoked")[0]
    with pytest.raises(psycopg.Error):
        with conn.transaction():
            conn.execute(
                """
                insert into revocation_tombstones(
                  tenant_id, id, subject_type, subject_id, card_id, card_version_id, revocation_epoch,
                  revocation_event_source_type, card_revocation_event_id, revoked_by, reason
                )
                values (%s, %s, 'card_version', %s, %s, %s, 1, 'card', %s, %s, 'actor mismatch')
                """,
                (tenant_a, uuid.uuid4(), version_id, card_id, version_id, event_id, other_principal),
            )
            conn.execute("set constraints revocation_tombstones_event_consistency immediate")


def test_read_path_denies_namespace_and_tenant_tombstones(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", role="app_user")[0]
    challenge_id = uuid.uuid4()
    conn.execute(
        """
        insert into approval_challenges(
          tenant_id, id, subject_id, namespace_id, consent_scope, artifact_type, artifact_id,
          card_version_id, artifact_digest, policy_version, policy_digest, challenge_digest,
          origin, expires_at, created_by
        )
        values (%s, %s, %s, %s, 'public_publication', 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', 'sha256:challenge', 'local', now() + interval '5 minutes', %s)
        """,
        (tenant_a, challenge_id, principal, ns_a, version_id, version_id, principal),
    )
    conn.execute(
        """
        insert into consent_records(
          tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
          artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
          grant_card_event_id, retention_policy, retention_purpose
        )
        values (%s, %s, %s, 'public_publication', %s, 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', %s, 'sha256:challenge', %s, 'retain', 'publish')
        """,
        (tenant_a, uuid.uuid4(), principal, ns_a, version_id, version_id, challenge_id, event_id),
    )

    domain_event_id = uuid.uuid4()
    position = scalar(conn, "select nextval('event_stream_position_seq')")
    with conn.transaction():
        conn.execute(
            """
            insert into domain_events(
              tenant_id, event_id, event_type, actor_id, actor_role, target_type, target_id,
              event_payload_schema_version, event_payload_json, event_payload_digest,
              correlation_id, idempotency_key, event_stream_position
            )
            values (%s, %s, 'namespace_revoked', %s, 'app_user', 'namespace', %s,
              1, '{}'::jsonb, 'sha256:event', %s, 'domain-revoke-ns', %s)
            """,
            (tenant_a, domain_event_id, principal, ns_a, uuid.uuid4(), position),
        )
        conn.execute(
            """
            insert into event_stream_positions(event_stream_position, tenant_id, event_source_type, domain_event_id)
            values (%s, %s, 'domain', %s)
            """,
            (position, tenant_a, domain_event_id),
        )
        conn.execute(
            """
            insert into revocation_tombstones(
              tenant_id, id, subject_type, subject_id, namespace_id, revocation_epoch,
              revocation_event_source_type, domain_revocation_event_id, revoked_by, reason
            )
            values (%s, %s, 'namespace', %s, %s, 1, 'domain', %s, %s, 'namespace revoke')
            """,
            (tenant_a, uuid.uuid4(), ns_a, ns_a, domain_event_id, principal),
        )
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from experience_cards where id = %s", (card_id,)) == 0
    assert scalar(conn, "select count(*) from card_versions where id = %s", (version_id,)) == 0
    assert scalar(conn, "select count(*) from card_events where card_id = %s", (card_id,)) == 0
    assert scalar(conn, "select count(*) from approval_challenges where id = %s", (challenge_id,)) == 0
    assert scalar(conn, "select count(*) from consent_records where card_version_id = %s", (version_id,)) == 0
    conn.rollback()

    tenant_b, _tenant_c, principal_b, ns_b, _ns_c, secret_b, kid_b = seed_base(conn)
    card_b, version_b = create_card(conn, tenant_b, ns_b, principal_b)
    domain_event_b = uuid.uuid4()
    position_b = scalar(conn, "select nextval('event_stream_position_seq')")
    with conn.transaction():
        conn.execute(
            """
            insert into domain_events(
              tenant_id, event_id, event_type, actor_id, actor_role, target_type, target_id,
              event_payload_schema_version, event_payload_json, event_payload_digest,
              correlation_id, idempotency_key, event_stream_position
            )
            values (%s, %s, 'tenant_revoked', %s, 'app_user', 'tenant', %s,
              1, '{}'::jsonb, 'sha256:event', %s, 'domain-revoke-tenant', %s)
            """,
            (tenant_b, domain_event_b, principal_b, tenant_b, uuid.uuid4(), position_b),
        )
        conn.execute(
            "insert into event_stream_positions(event_stream_position, tenant_id, event_source_type, domain_event_id) values (%s, %s, 'domain', %s)",
            (position_b, tenant_b, domain_event_b),
        )
        conn.execute(
            """
            insert into revocation_tombstones(
              tenant_id, id, subject_type, subject_id, tenant_subject_id, revocation_epoch,
              revocation_event_source_type, domain_revocation_event_id, revoked_by, reason
            )
            values (%s, %s, 'tenant', %s, %s, 1, 'domain', %s, %s, 'tenant revoke')
            """,
            (tenant_b, uuid.uuid4(), tenant_b, tenant_b, domain_event_b, principal_b),
        )
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret_b, tenant_b, principal_b, [ns_b], kid=kid_b)),))
    assert scalar(conn, "select count(*) from experience_cards where id = %s", (card_b,)) == 0
    assert scalar(conn, "select count(*) from card_versions where id = %s", (version_b,)) == 0


def test_card_version_revoke_hides_approval_artifacts(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", role="app_user")[0]
    challenge_id = uuid.uuid4()
    conn.execute(
        """
        insert into approval_challenges(
          tenant_id, id, subject_id, namespace_id, consent_scope, artifact_type, artifact_id,
          card_version_id, artifact_digest, policy_version, policy_digest, challenge_digest,
          origin, expires_at, created_by
        )
        values (%s, %s, %s, %s, 'public_publication', 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', 'sha256:challenge', 'local', now() + interval '5 minutes', %s)
        """,
        (tenant_a, challenge_id, principal, ns_a, version_id, version_id, principal),
    )
    conn.execute(
        """
        insert into consent_records(
          tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
          artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
          grant_card_event_id, retention_policy, retention_purpose
        )
        values (%s, %s, %s, 'public_publication', %s, 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', %s, 'sha256:challenge', %s, 'retain', 'publish')
        """,
        (tenant_a, uuid.uuid4(), principal, ns_a, version_id, version_id, challenge_id, event_id),
    )
    conn.commit()
    conn.execute("reset role")
    revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card_version", version_id)
    conn.commit()

    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    assert scalar(conn, "select count(*) from approval_challenges where id = %s", (challenge_id,)) == 0
    assert scalar(conn, "select count(*) from consent_records where card_version_id = %s", (version_id,)) == 0


def test_consent_challenge_binding(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", role="app_user")[0]
    challenge_id = uuid.uuid4()
    conn.execute(
        """
        insert into approval_challenges(
          tenant_id, id, subject_id, namespace_id, consent_scope, artifact_type, artifact_id,
          card_version_id, artifact_digest, policy_version, policy_digest, challenge_digest,
          origin, expires_at, created_by
        )
        values (%s, %s, %s, %s, 'public_publication', 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', 'sha256:challenge', 'local', now() + interval '5 minutes', %s)
        """,
        (tenant_a, challenge_id, principal, ns_a, version_id, version_id, principal),
    )
    consent_id = uuid.uuid4()
    conn.execute(
        """
        insert into consent_records(
          tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
          artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
          grant_card_event_id, retention_policy, retention_purpose
        )
        values (%s, %s, %s, 'public_publication', %s, 'card_version', %s, %s,
          'sha256:artifact', 'v1', 'sha256:policy', %s, 'sha256:challenge', %s, 'retain', 'publish')
        """,
        (tenant_a, consent_id, principal, ns_a, version_id, version_id, challenge_id, event_id),
    )
    assert scalar(conn, "select used_by_consent_id = %s from approval_challenges where id = %s", (consent_id, challenge_id))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into consent_records(
              tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
              artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
              grant_card_event_id, retention_policy, retention_purpose
            )
            values (%s, %s, %s, 'public_publication', %s, 'card_version', %s, %s,
              'sha256:other', 'v1', 'sha256:policy', %s, 'sha256:challenge', %s, 'retain', 'publish')
            """,
            (tenant_a, uuid.uuid4(), principal, ns_a, version_id, version_id, challenge_id, event_id),
        )


def test_revoke_consent_record_writes_domain_event_and_blocks_reuse(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id, consent_id = create_public_publication_consent(conn, tenant_a, ns_a, principal)
    conn.commit()
    conn.execute("reset role")

    row = revoke_consent_record(conn, tenant_a, principal, ns_a, secret, kid, consent_id)
    assert row[2] == consent_id
    conn.commit()
    conn.execute("reset role")

    assert scalar(conn, "select count(*) from domain_events where event_id = %s and event_type = 'consent_terminated'", (row[0],)) == 1
    assert scalar(conn, "select termination_domain_event_id = %s from consent_records where id = %s", (row[0], consent_id))
    assert scalar(conn, "select revoked_at is not null from consent_records where id = %s", (consent_id,))
    assert scalar(conn, "select count(*) from audit_events where action = 'revoke_consent_record' and target_id = %s", (consent_id,)) == 1
    assert scalar(
        conn,
        "select count(*) from consent_records where card_version_id = %s and scope = 'public_publication' and revoked_at is null",
        (version_id,),
    ) == 0

    replay = revoke_consent_record(conn, tenant_a, principal, ns_a, secret, kid, consent_id)
    assert replay[:3] == row[:3]
    with pytest.raises(psycopg.Error):
        revoke_consent_record(
            conn,
            tenant_a,
            principal,
            ns_a,
            secret,
            kid,
            consent_id,
            idempotency_key="consent-revoke-1",
            request_digest="sha256:req-consent-revoke-conflict",
        )
    conn.rollback()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into consent_records(
              tenant_id, id, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
              artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
              grant_card_event_id, retention_policy, retention_purpose
            )
            select tenant_id, %s, subject_id, scope, namespace_id, artifact_type, artifact_id, card_version_id,
              artifact_digest, policy_version, policy_digest, challenge_id, challenge_digest,
              grant_card_event_id, retention_policy, retention_purpose
            from consent_records
            where id = %s
            """,
            (uuid.uuid4(), consent_id),
        )
    assert card_id


def test_revoke_consent_record_replay_revalidates_namespace_scope(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    _card_id, _version_id, consent_id = create_public_publication_consent(conn, tenant_a, ns_a, principal)
    conn.commit()
    conn.execute("reset role")

    revoke_consent_record(conn, tenant_a, principal, ns_a, secret, kid, consent_id)
    conn.commit()
    conn.execute("reset role")
    conn.execute(
        """
        update namespace_grants
        set status = 'revoked', revoked_at = now()
        where tenant_id = %s and namespace_id = %s and principal_id = %s
        """,
        (tenant_a, ns_a, principal),
    )
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        revoke_consent_record(conn, tenant_a, principal, ns_a, secret, kid, consent_id)


def test_withdraw_publication_approval_replay_revalidates_namespace_scope(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _consent_id = create_public_publication_consent(conn, tenant_a, ns_a, principal)
    conn.commit()
    conn.execute("reset role")

    withdraw_publication_approval(conn, tenant_a, principal, ns_a, secret, kid, card_id, version_id)
    conn.commit()
    conn.execute("reset role")
    conn.execute(
        """
        update namespace_grants
        set status = 'revoked', revoked_at = now()
        where tenant_id = %s and namespace_id = %s and principal_id = %s
        """,
        (tenant_a, ns_a, principal),
    )
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        withdraw_publication_approval(conn, tenant_a, principal, ns_a, secret, kid, card_id, version_id)


def test_withdraw_publication_approval_terminates_active_consent(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id, consent_id = create_public_publication_consent(conn, tenant_a, ns_a, principal)
    conn.commit()
    conn.execute("reset role")

    row = withdraw_publication_approval(conn, tenant_a, principal, ns_a, secret, kid, card_id, version_id)
    assert row[2] == 3
    assert row[3] == card_id
    assert row[4] == consent_id
    conn.commit()
    conn.execute("reset role")

    assert scalar(conn, "select status = 'publication_withdrawn' from experience_cards where id = %s", (card_id,))
    assert scalar(conn, "select termination_card_event_id = %s from consent_records where id = %s", (row[0], consent_id))
    assert scalar(conn, "select revoked_at is not null from consent_records where id = %s", (consent_id,))
    assert scalar(conn, "select count(*) from audit_events where action = 'withdraw_publication_approval' and target_id = %s", (card_id,)) == 1
    assert scalar(
        conn,
        "select count(*) from consent_records where card_version_id = %s and scope = 'public_publication' and revoked_at is null",
        (version_id,),
    ) == 0

    replay = withdraw_publication_approval(conn, tenant_a, principal, ns_a, secret, kid, card_id, version_id)
    assert replay[:5] == row[:5]
    with pytest.raises(psycopg.Error):
        withdraw_publication_approval(
            conn,
            tenant_a,
            principal,
            ns_a,
            secret,
            kid,
            card_id,
            version_id,
            idempotency_key="withdraw-1",
            request_digest="sha256:req-withdraw-conflict",
        )


def test_withdraw_publication_approval_requires_active_public_consent(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal, status="approved_for_publication")
    conn.commit()
    conn.execute("reset role")

    with pytest.raises(psycopg.Error):
        withdraw_publication_approval(conn, tenant_a, principal, ns_a, secret, kid, card_id, version_id)


def test_audit_insert_function_accepts_only_sanitized_detail(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    target_id = uuid.uuid4()
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))

    row = conn.execute(
        """
        select audit_event_id
        from knudg_insert_audit_event(
          'operator_note', 'card', %s, 'manual_check', 'Reviewed sanitized operation metadata.', %s
        )
        """,
        (target_id, uuid.uuid4()),
    ).fetchone()
    assert scalar(conn, "select count(*) from audit_events where id = %s", (row[0],)) == 1

    rejected_details = [
        "password=plain-text",
        "authorization header placeholder",
        "token=plain-text",
        "auth_token=plain-text",
        "authorization=Token plain-text",
        "github_pat_plaintext",
        "ghp_plaintext",
        "C:\\redacted\\secret.txt",
        "/home/user/raw-source.txt",
        "line one\nline two",
        "```raw snippet```",
        "x" * 2049,
    ]
    for detail in rejected_details:
        assert not scalar(conn, "select knudg_private.audit_detail_is_sanitized(%s)", (detail,)), detail
        with pytest.raises(psycopg.Error):
            conn.execute(
                """
                select audit_event_id
                from knudg_insert_audit_event(
                  'operator_note', 'card', %s, 'manual_check', %s, %s
                )
                """,
                (target_id, detail, uuid.uuid4()),
            )
        conn.rollback()
        conn.execute("set role knudg_app")
        conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))


def test_app_role_cannot_directly_insert_or_mutate_audit_events(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into audit_events(
              tenant_id, id, actor_id, actor_role, action, target_type, target_id,
              reason_code, sanitized_detail, correlation_id
            )
            values (%s, %s, %s, 'platform_admin', 'spoofed', 'card', %s,
              'manual_check', 'Spoofed sanitized operation metadata.', %s)
            """,
            (tenant_a, uuid.uuid4(), principal, uuid.uuid4(), uuid.uuid4()),
        )
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    audit_id = conn.execute(
        """
        select audit_event_id
        from knudg_insert_audit_event(
          'operator_note', 'card', %s, 'manual_check', 'Reviewed sanitized operation metadata.', %s
        )
        """,
        (uuid.uuid4(), uuid.uuid4()),
    ).fetchone()[0]
    with pytest.raises(psycopg.Error):
        conn.execute("update audit_events set sanitized_detail = 'changed' where id = %s", (audit_id,))
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute("delete from audit_events where id = %s", (audit_id,))


def test_enqueue_outbox_job_is_idempotent_and_tables_are_guarded(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    event_id = insert_card_event(
        conn,
        tenant_a,
        card_id,
        principal,
        "private_approved",
        "awaiting_user_approval",
        "approved_private",
        expected_current_version=version_id,
    )[0]
    event_position = scalar(conn, "select event_stream_position from card_events where event_id = %s", (event_id,))
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    first = conn.execute(
        """
        select outbox_event_id, job_id, event_stream_position, lane, status
        from knudg_enqueue_outbox_job(
          %s, 'event_projection', '{"target":"card"}'::jsonb,
          'sha256:payload', 'outbox-1', 10, 3
        )
        """,
        (event_position,),
    ).fetchone()
    replay = conn.execute(
        """
        select outbox_event_id, job_id, event_stream_position, lane, status
        from knudg_enqueue_outbox_job(
          %s, 'event_projection', '{"target":"card"}'::jsonb,
          'sha256:payload', 'outbox-1', 10, 3
        )
        """,
        (event_position,),
    ).fetchone()
    assert replay == first
    assert scalar(conn, "select count(*) from jobs where id = %s and status = 'ready'", (first[1],)) == 1
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            select job_id from knudg_enqueue_outbox_job(
              %s, 'event_projection', '{"target":"other"}'::jsonb,
              'sha256:different', 'outbox-1', 10, 3
            )
            """,
            (event_position,),
        )
    conn.rollback()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into jobs(
              tenant_id, id, lane, payload_json, payload_digest, idempotency_key
            )
            values (%s, %s, 'event_projection', '{}'::jsonb, 'sha256:payload', 'direct-job')
            """,
            (tenant_a, uuid.uuid4()),
        )


def test_enqueue_outbox_job_concurrent_duplicate_replays(migrated_db):
    with psycopg.connect(migrated_db, connect_timeout=3) as first_conn:
        tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(first_conn)
        grant_submit(first_conn, tenant_a, ns_a, principal)
        card_id, version_id, _created = submit_candidate(first_conn, tenant_a, principal, ns_a, secret, kid)
        first_conn.commit()
        first_conn.execute("reset role")
        event_id = insert_card_event(
            first_conn,
            tenant_a,
            card_id,
            principal,
            "private_approved",
            "awaiting_user_approval",
            "approved_private",
            expected_current_version=version_id,
        )[0]
        event_position = scalar(first_conn, "select event_stream_position from card_events where event_id = %s", (event_id,))
        first_conn.commit()
        first_conn.execute("set role knudg_app")
        first_conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
        first_row = first_conn.execute(
            """
            select outbox_event_id, job_id, event_stream_position, lane, status
            from knudg_enqueue_outbox_job(
              %s, 'event_projection', '{}'::jsonb, 'sha256:concurrent', 'outbox-concurrent', 0, 3
            )
            """,
            (event_position,),
        ).fetchone()
        started = threading.Event()

        def duplicate_enqueue():
            with psycopg.connect(migrated_db, connect_timeout=3) as second_conn:
                second_conn.execute("set role knudg_app")
                second_conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
                started.set()
                row = second_conn.execute(
                    """
                    select outbox_event_id, job_id, event_stream_position, lane, status
                    from knudg_enqueue_outbox_job(
                      %s, 'event_projection', '{}'::jsonb, 'sha256:concurrent', 'outbox-concurrent', 0, 3
                    )
                    """,
                    (event_position,),
                ).fetchone()
                second_conn.commit()
                return row

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(duplicate_enqueue)
            assert started.wait(timeout=3)
            first_conn.commit()
            assert future.result(timeout=5) == first_row


def test_worker_claim_complete_and_skip_leased_jobs(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    worker_id = create_worker_identity(conn, tenant_a)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_a = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", expected_current_version=version_id)[1]
    event_b = insert_card_event(conn, tenant_a, card_id, principal, "approval_withdrawn", "approved_for_publication", "publication_withdrawn", seq=3, expected_current_version=version_id)[1]
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    job_a = conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'event_projection', '{}'::jsonb, 'sha256:a', 'outbox-a', 0, 3)", (event_a,)).fetchone()[0]
    job_b = conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'event_projection', '{}'::jsonb, 'sha256:b', 'outbox-b', 0, 3)", (event_b,)).fetchone()[0]
    conn.commit()
    conn.execute("reset role")

    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    first = conn.execute("select job_id, attempt_number from knudg_claim_job('event_projection', 60)").fetchone()
    second = conn.execute("select job_id, attempt_number from knudg_claim_job('event_projection', 60)").fetchone()
    assert {first[0], second[0]} == {job_a, job_b}
    assert first[1] == 1
    assert second[1] == 1
    completed = conn.execute("select job_id, status from knudg_complete_job(%s)", (first[0],)).fetchone()
    assert completed == (first[0], "succeeded")
    assert scalar(conn, "select count(*) from job_attempts where job_id = %s and status = 'succeeded'", (first[0],)) == 1
    assert scalar(conn, "select status from jobs where id = %s", (first[0],)) == "succeeded"


def test_worker_claim_job_by_id_leases_only_requested_ready_job(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    worker_id = create_worker_identity(conn, tenant_a)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_a = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", expected_current_version=version_id)[1]
    event_b = insert_card_event(conn, tenant_a, card_id, principal, "approval_withdrawn", "approved_for_publication", "publication_withdrawn", seq=3, expected_current_version=version_id)[1]
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    job_a = conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'redaction', '{}'::jsonb, 'sha256:a', 'outbox-by-id-a', 0, 3)", (event_a,)).fetchone()[0]
    job_b = conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'redaction', '{}'::jsonb, 'sha256:b', 'outbox-by-id-b', 0, 3)", (event_b,)).fetchone()[0]
    conn.commit()
    conn.execute("reset role")

    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    claimed = conn.execute("select job_id, attempt_number from knudg_claim_job_by_id(%s, 60)", (job_b,)).fetchone()
    assert claimed == (job_b, 1)
    assert scalar(conn, "select status from jobs where id = %s", (job_b,)) == "leased"
    assert scalar(conn, "select status from jobs where id = %s", (job_a,)) == "ready"
    assert conn.execute("select job_id from knudg_claim_job_by_id(%s, 60)", (job_b,)).fetchone() is None


def test_worker_fail_job_retries_then_dead_letters(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    worker_id = create_worker_identity(conn, tenant_a)
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_position = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", expected_current_version=version_id)[1]
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    job_id = conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'event_projection', '{}'::jsonb, 'sha256:fail', 'outbox-fail', 0, 1)", (event_position,)).fetchone()[0]
    conn.commit()
    conn.execute("reset role")

    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    claimed = conn.execute("select job_id from knudg_claim_job('event_projection', 60)").fetchone()
    assert claimed[0] == job_id
    with pytest.raises(psycopg.Error):
        conn.execute("select status from knudg_fail_job(%s, 'dependency_error', 'token=unsafe', 0)", (job_id,))
    conn.rollback()
    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    conn.execute("select job_id from knudg_claim_job('event_projection', 60)")
    failed = conn.execute("select job_id, status, attempts from knudg_fail_job(%s, 'dependency_error', 'Dependency returned retryable error.', 0)", (job_id,)).fetchone()
    assert failed == (job_id, "dead", 1)
    assert scalar(conn, "select status from jobs where id = %s", (job_id,)) == "dead"
    assert scalar(conn, "select count(*) from outbox_events where job_id = %s and status = 'dead'", (job_id,)) == 1


def test_claim_job_requires_worker_identity(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    with pytest.raises(psycopg.Error):
        conn.execute("select job_id from knudg_claim_job('event_projection', 60)")
    conn.rollback()
    conn.execute("set role knudg_worker")
    with pytest.raises(psycopg.Error):
        conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [], role="index_worker", kid=kid)),))


def test_worker_queue_functions_require_allowed_operations(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    worker_id = create_worker_identity(conn, tenant_a, allowed_operations=["complete_job"])
    card_id, version_id = create_card(conn, tenant_a, ns_a, principal)
    event_position = insert_card_event(conn, tenant_a, card_id, principal, "private_approved", "awaiting_user_approval", "approved_private", expected_current_version=version_id)[1]
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'event_projection', '{}'::jsonb, 'sha256:ops', 'outbox-ops', 0, 3)", (event_position,))
    conn.commit()
    conn.execute("reset role")

    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    with pytest.raises(psycopg.Error):
        conn.execute("select job_id from knudg_claim_job('event_projection', 60)")
    conn.rollback()
    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    with pytest.raises(psycopg.Error):
        conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'consent', '{}'::jsonb, 'sha256:ops2', 'outbox-ops2', 0, 3)", (event_position,))

    conn.rollback()
    conn.execute("reset role")
    conn.execute(
        "update worker_identities set allowed_operations = array['enqueue_outbox_job'] where principal_id = %s",
        (worker_id,),
    )
    conn.commit()
    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    with pytest.raises(psycopg.Error):
        conn.execute("select job_id from knudg_claim_job('event_projection', 60)")
    conn.rollback()
    set_worker_claims(conn, tenant_a, worker_id, secret, kid)
    row = conn.execute("select job_id from knudg_enqueue_outbox_job(%s, 'consent', '{}'::jsonb, 'sha256:ops2', 'outbox-ops2', 0, 3)", (event_position,)).fetchone()
    assert row[0]


def test_knudgctl_status_and_not_configured_commands(migrated_db):
    code, payload = run_knudgctl(migrated_db, "migrate", "status")
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["migration_table_exists"]
    assert payload["migrations"]

    code, payload = run_knudgctl(migrated_db, "db", "status")
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["database"]["queue_schema_exists"]

    code, payload = run_knudgctl(migrated_db, "db", "backup", "status")
    assert code == 2
    assert payload["status"] == "not_configured"
    assert payload["required_operator_role"] == "database_on_call"


def test_knudgctl_usage_unavailable_and_stub_exit_codes(migrated_db):
    code, payload = run_knudgctl(migrated_db)
    assert code == 3
    assert payload["status"] == "usage_error"

    code, payload = run_knudgctl(migrated_db, "queue")
    assert code == 3
    assert payload["status"] == "usage_error"

    code, payload = run_knudgctl(migrated_db, "deps", "check", "--all")
    assert code == 2
    assert payload["status"] == "not_configured"

    code, payload = run_knudgctl(migrated_db, "db", "pitr", "plan", "--target", "customer@example.com")
    assert code == 2
    assert payload["status"] == "not_configured"
    assert payload["target"]["present"] is True
    assert "customer@example.com" not in json.dumps(payload)

    code, payload = run_knudgctl(migrated_db, "notifications", "pause", "--target", "https://private.example/incidents/1", "--reason", "secret note")
    assert code == 2
    assert payload["status"] == "not_configured"
    assert "private.example" not in json.dumps(payload)
    assert "secret note" not in json.dumps(payload)

    code, payload = run_knudgctl(migrated_db, "queue", "peek", "--lane", "analytics", "--oldest", "-1")
    assert code == 3
    assert payload["status"] == "usage_error"

    code, payload = run_knudgctl(
        "postgresql://knudg_migration:knudg_migration@localhost:1/missing",
        "db",
        "status",
    )
    assert code == 4
    assert payload["status"] == "unavailable"


def test_knudgctl_queue_stats_and_peek_redact_payload(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    event_id = insert_card_event(
        conn,
        tenant_a,
        card_id,
        principal,
        "private_approved",
        "awaiting_user_approval",
        "approved_private",
        expected_current_version=version_id,
    )[0]
    event_position = scalar(conn, "select event_stream_position from card_events where event_id = %s", (event_id,))
    conn.commit()
    conn.execute("set role knudg_app")
    conn.execute("select knudg_set_claims(%s::jsonb)", (json.dumps(signed_context(secret, tenant_a, principal, [ns_a], kid=kid)),))
    conn.execute(
        """
        select job_id from knudg_enqueue_outbox_job(
          %s, 'analytics', '{"raw":"must not appear"}'::jsonb,
          'sha256:cli', 'outbox-cli', 0, 3
        )
        """,
        (event_position,),
    )
    conn.commit()

    code, payload = run_knudgctl(migrated_db, "queue", "stats", "--all")
    assert code == 0
    assert any(item["lane"] == "analytics" and item["status"] == "ready" for item in payload["queues"])

    code, payload = run_knudgctl(migrated_db, "queue", "peek", "--lane", "analytics", "--oldest", "5")
    assert code == 0
    assert payload["jobs"]
    assert all("payload_json" not in job for job in payload["jobs"])
    assert any(job["payload_digest"] == "sha256:cli" for job in payload["jobs"])

    code, payload = run_knudgctl(migrated_db, "queue", "redrive", "--job", str(uuid.uuid4()), "--reason", "ticket-1", "--dry-run")
    assert code == 2
    assert payload["status"] == "not_configured"
    assert payload["audit_event"] == "queue_redrive_requested"
    assert payload["reason"]["present"] is True
    assert payload["reason"]["sha256"] == hashlib.sha256(b"ticket-1").hexdigest()
    assert "ticket-1" not in json.dumps(payload)

    code, payload = run_knudgctl(migrated_db, "outbox", "reconcile", "--from-position", "1", "--dry-run")
    assert code == 0
    assert payload["status"] == "ok"
    assert "missing_outbox" in payload

    code, payload = run_knudgctl(migrated_db, "outbox", "reconcile", "--from-position", "1", "--apply")
    assert code == 2
    assert payload["status"] == "not_configured"


def test_knudgctl_writer_status_and_reconcile_are_readonly_and_redacted(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    code, payload = run_knudgctl(migrated_db, "writer", "status", "--tenant", str(tenant_a))
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["protected_data_serving_enabled"] is False
    assert payload["publication_enabled"] is False
    assert any(item["status"] == "candidate_created" and item["count"] == 1 for item in payload["card_statuses"])
    assert "payload_json" not in json.dumps(payload)

    code, payload = run_knudgctl(
        migrated_db,
        "writer",
        "reconcile",
        "--tenant",
        str(tenant_a),
        "--limit",
        "5",
        "--dry-run",
    )
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert payload["candidates"]
    assert payload["candidates"][0]["card_id"] == str(card_id)
    assert payload["candidates"][0]["current_version_id"] == str(version_id)
    assert payload["candidates"][0]["recommended_next_action"] == "accept_admission"
    assert "payload_json" not in json.dumps(payload)
    assert "capture a repeated" not in json.dumps(payload)

    code, payload = run_knudgctl(migrated_db, "writer", "reconcile", "--apply")
    assert code == 2
    assert payload["status"] == "not_configured"
    assert payload["audit_event"] == "writer_reconcile_requested"


def test_knudgctl_writer_enqueue_next_plans_and_enqueues_opaque_jobs(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    code, payload = run_knudgctl(
        migrated_db,
        "writer",
        "enqueue-next",
        "--tenant",
        str(tenant_a),
        "--limit",
        "5",
        "--dry-run",
    )
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert payload["apply"] is False
    assert payload["protected_data_serving_enabled"] is False
    assert payload["publication_enabled"] is False
    assert payload["jobs"][0]["action"] == "would_enqueue"
    assert payload["jobs"][0]["card_id"] == str(card_id)
    assert payload["jobs"][0]["current_version_id"] == str(version_id)
    assert payload["jobs"][0]["operation"] == "accept_admission"
    assert payload["jobs"][0]["lane"] == "public_candidate_ingest"
    assert "payload_json" not in json.dumps(payload)
    assert "capture a repeated" not in json.dumps(payload)
    assert scalar(conn, "select count(*) from jobs where tenant_id = %s", (tenant_a,)) == 0

    code, payload = run_knudgctl(
        migrated_db,
        "writer",
        "enqueue-next",
        "--tenant",
        str(tenant_a),
        "--limit",
        "5",
        "--apply",
    )
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["apply"] is True
    assert payload["jobs"][0]["action"] == "enqueued"
    job_id = payload["jobs"][0]["job_id"]
    assert job_id
    assert scalar(conn, "select status from jobs where id = %s", (job_id,)) == "ready"
    assert scalar(conn, "select payload_json->>'operation' from jobs where id = %s", (job_id,)) == "accept_admission"
    assert scalar(conn, "select payload_json->>'publication_enabled' from jobs where id = %s", (job_id,)) == "false"
    assert scalar(conn, "select payload_json ? 'successful_path' from jobs where id = %s", (job_id,)) is False

    code, replay = run_knudgctl(
        migrated_db,
        "writer",
        "enqueue-next",
        "--tenant",
        str(tenant_a),
        "--limit",
        "5",
        "--apply",
    )
    assert code == 0
    assert replay["jobs"][0]["action"] == "already_enqueued"
    assert replay["jobs"][0]["job_id"] == job_id
    assert scalar(conn, "select count(*) from jobs where tenant_id = %s", (tenant_a,)) == 1

    code, status_payload = run_knudgctl(migrated_db, "writer", "status", "--tenant", str(tenant_a))
    assert code == 0
    assert any(
        item["lane"] == "public_candidate_ingest" and item["status"] == "ready" and item["count"] == 1
        for item in status_payload["queues"]
    )


def test_knudgctl_writer_run_next_claims_dispatches_and_completes_opaque_jobs(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    code, enqueue = run_knudgctl(
        migrated_db,
        "writer",
        "enqueue-next",
        "--tenant",
        str(tenant_a),
        "--apply",
    )
    assert code == 0
    job_id = enqueue["jobs"][0]["job_id"]

    code, preview = run_knudgctl(
        migrated_db,
        "writer",
        "run-next",
        "--tenant",
        str(tenant_a),
        "--dry-run",
    )
    assert code == 0
    assert preview["job"]["action"] == "would_claim"
    assert preview["job"]["job_id"] == job_id
    assert scalar(conn, "select status from jobs where id = %s", (job_id,)) == "ready"
    assert "payload_json" not in json.dumps(preview)
    assert "capture a solved setup path" not in json.dumps(preview)
    assert "capture a repeated" not in json.dumps(preview)

    expected_steps = [
        ("accept_admission", "candidate_created", "pending_admission"),
        ("request_redaction", "pending_admission", "pending_redaction"),
        ("complete_redaction", "pending_redaction", "pending_review"),
        ("request_private_approval", "pending_review", "awaiting_user_approval"),
    ]
    for index, (operation, previous_status, next_status) in enumerate(expected_steps):
        if index:
            code, enqueue = run_knudgctl(
                migrated_db,
                "writer",
                "enqueue-next",
                "--tenant",
                str(tenant_a),
                "--apply",
            )
            assert code == 0
            assert enqueue["jobs"][0]["operation"] == operation

        code, payload = run_knudgctl(
            migrated_db,
            "writer",
            "run-next",
            "--tenant",
            str(tenant_a),
            "--apply",
        )
        assert code == 0
        assert payload["status"] == "ok"
        assert payload["job"]["action"] == "completed"
        assert payload["job"]["operation"] == operation
        assert payload["transition"]["previous_status"] == previous_status
        assert payload["transition"]["next_status"] == next_status
        assert scalar(conn, "select status from experience_cards where id = %s", (card_id,)) == next_status
        assert scalar(conn, "select status from jobs where id = %s", (payload["job"]["job_id"],)) == "succeeded"
        assert "payload_json" not in json.dumps(payload)
        assert "capture a solved setup path" not in json.dumps(payload)
        assert "capture a repeated" not in json.dumps(payload)

    assert scalar(conn, "select current_version_id from experience_cards where id = %s", (card_id,)) == version_id
    assert scalar(conn, "select count(*) from approval_challenges where artifact_id = %s", (version_id,)) == 1

    code, empty = run_knudgctl(
        migrated_db,
        "writer",
        "run-next",
        "--tenant",
        str(tenant_a),
        "--apply",
    )
    assert code == 0
    assert empty["action"] == "no_job"


def test_knudgctl_writer_sweep_detects_and_repairs_safe_writer_queue_cases(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")

    code, sweep = run_knudgctl(
        migrated_db,
        "writer",
        "sweep",
        "--tenant",
        str(tenant_a),
        "--dry-run",
    )
    assert code == 0
    assert sweep["status"] == "ok"
    assert any(item["action_class"] == "missing_next_job" and item["action"] == "would_enqueue" for item in sweep["findings"])
    assert "payload_json" not in json.dumps(sweep)
    assert "capture a solved setup path" not in json.dumps(sweep)

    code, applied = run_knudgctl(
        migrated_db,
        "writer",
        "sweep",
        "--tenant",
        str(tenant_a),
        "--apply",
    )
    assert code == 0
    enqueued = [item for item in applied["findings"] if item["action_class"] == "missing_next_job"]
    assert enqueued[0]["action"] == "enqueued"
    job_id = enqueued[0]["job_id"]
    assert scalar(conn, "select status from jobs where id = %s", (job_id,)) == "ready"

    worker_id = create_worker_identity(conn, tenant_a)
    conn.execute(
        """
        update jobs
        set status = 'leased',
            leased_by = %s,
            lease_expires_at = now() - interval '1 minute',
            attempts = attempts + 1
        where id = %s
        """,
        (worker_id, job_id),
    )
    conn.execute(
        """
        insert into job_attempts(tenant_id, id, job_id, attempt_number, worker_id, worker_role, status)
        values (%s, %s, %s, 1, %s, 'index_worker', 'leased')
        """,
        (tenant_a, uuid.uuid4(), job_id, worker_id),
    )
    conn.commit()

    code, stale = run_knudgctl(
        migrated_db,
        "writer",
        "sweep",
        "--tenant",
        str(tenant_a),
        "--dry-run",
    )
    assert code == 0
    assert any(item["action_class"] == "stale_leased_job" and item["action"] == "would_release_lease" for item in stale["findings"])

    code, released = run_knudgctl(
        migrated_db,
        "writer",
        "sweep",
        "--tenant",
        str(tenant_a),
        "--apply",
    )
    assert code == 0
    assert any(item["action_class"] == "stale_leased_job" and item["action"] == "released_lease" for item in released["findings"])
    assert scalar(conn, "select status from jobs where id = %s", (job_id,)) == "ready"
    assert scalar(conn, "select lease_expires_at is null from jobs where id = %s", (job_id,))

    duplicate_payload = {
        "schema_version": "writer-orchestration-job-v0",
        "operation": "request_redaction",
        "worker_role": "ingestion_worker",
        "card_id": str(card_id),
        "current_version_id": str(version_id),
        "source_status": "pending_admission",
        "requires_human_completion": False,
        "protected_data_serving_enabled": False,
        "publication_enabled": False,
    }
    conn.execute(
        """
        insert into jobs(tenant_id, id, lane, status, payload_json, payload_digest, idempotency_key)
        values (%s, %s, 'redaction', 'ready', %s::jsonb, 'sha256:dup-a', 'dup-a'),
               (%s, %s, 'redaction', 'ready', %s::jsonb, 'sha256:dup-b', 'dup-b')
        """,
        (tenant_a, uuid.uuid4(), json.dumps(duplicate_payload), tenant_a, uuid.uuid4(), json.dumps(duplicate_payload)),
    )
    conn.execute(
        """
        insert into approval_challenges(
          tenant_id, id, subject_id, namespace_id, consent_scope, artifact_type,
          artifact_id, card_version_id, artifact_digest, policy_version,
          policy_digest, challenge_digest, origin, expires_at, created_by
        )
        values (
          %s, %s, %s, %s, 'private_retention', 'card_version',
          %s, %s, 'sha256:artifact', 'local-private-retention-v0',
          'sha256:policy', 'sha256:challenge', 'local-test', now() - interval '1 minute', %s
        )
        """,
        (tenant_a, uuid.uuid4(), principal, ns_a, version_id, version_id, principal),
    )
    conn.commit()

    code, detected = run_knudgctl(
        migrated_db,
        "writer",
        "sweep",
        "--tenant",
        str(tenant_a),
        "--dry-run",
    )
    assert code == 0
    assert any(item["action_class"] == "duplicate_active_jobs" for item in detected["findings"])
    assert any(item["action_class"] == "expired_private_approval_challenge" for item in detected["findings"])
    assert "payload_json" not in json.dumps(detected)
    assert "capture a solved setup path" not in json.dumps(detected)


def test_knudgctl_writer_approval_handoff_binds_digest_without_completing_consent(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    ingestion_worker = create_worker_identity(conn, tenant_a, role="ingestion_worker", allowed_operations=["accept_admission", "request_redaction"])
    redaction_worker = create_worker_identity(conn, tenant_a, role="redaction_worker", allowed_operations=["complete_redaction"])
    review_worker = create_worker_identity(conn, tenant_a, role="review_worker", allowed_operations=["request_private_approval"])
    conn.commit()
    card_id, version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    worker_transition(conn, tenant_a, ingestion_worker, secret, kid, "ingestion_worker", "knudg_accept_admission", card_id, version_id, idempotency_key="handoff-admission", request_digest="sha256:req-handoff-admission")
    worker_transition(conn, tenant_a, ingestion_worker, secret, kid, "ingestion_worker", "knudg_request_redaction", card_id, version_id, idempotency_key="handoff-redaction-request", request_digest="sha256:req-handoff-redaction-request")
    completed = complete_redaction(conn, tenant_a, redaction_worker, secret, kid, card_id, version_id, None, None, idempotency_key="handoff-redaction-complete", request_digest="sha256:req-handoff-redaction-complete")
    challenge_id = uuid.uuid4()
    request_private_approval(conn, tenant_a, review_worker, secret, kid, card_id, completed[6], challenge_id, idempotency_key="handoff-private-approval", request_digest="sha256:req-handoff-private-approval")
    conn.commit()
    conn.execute("reset role")
    payload_digest = scalar(conn, "select payload_digest from card_versions where id = %s", (version_id,))

    code, preview = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "create",
        "--tenant",
        str(tenant_a),
        "--card",
        str(card_id),
        "--dry-run",
    )
    assert code == 0
    assert preview["handoff"]["action"] == "would_create"
    assert preview["handoff"]["challenge_id"] == str(challenge_id)
    assert preview["handoff"]["card_version_id"] == str(version_id)
    assert preview["handoff"]["artifact_digest"] == payload_digest
    assert preview["completion_enabled"] is False
    assert "payload_json" not in json.dumps(preview)
    assert "capture a solved setup path" not in json.dumps(preview)
    assert scalar(conn, "select count(*) from approval_handoffs where tenant_id = %s", (tenant_a,)) == 0

    code, created = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "create",
        "--tenant",
        str(tenant_a),
        "--card",
        str(card_id),
        "--apply",
    )
    assert code == 0
    handoff_id = created["handoff"]["handoff_id"]
    assert created["handoff"]["action"] == "created"
    assert scalar(conn, "select artifact_digest from approval_handoffs where id = %s", (handoff_id,)) == payload_digest
    assert scalar(conn, "select card_version_id from approval_handoffs where id = %s", (handoff_id,)) == version_id
    assert scalar(conn, "select count(*) from consent_records where challenge_id = %s", (challenge_id,)) == 0
    assert scalar(conn, "select used_by_consent_id is null from approval_challenges where id = %s", (challenge_id,))

    code, replay = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "create",
        "--tenant",
        str(tenant_a),
        "--card",
        str(card_id),
        "--apply",
    )
    assert code == 0
    assert replay["handoff"]["action"] == "already_created"
    assert replay["handoff"]["handoff_id"] == handoff_id

    code, inspected = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "inspect",
        "--tenant",
        str(tenant_a),
        "--handoff",
        handoff_id,
    )
    assert code == 0
    assert inspected["handoff"]["action"] == "inspect"
    assert inspected["handoff"]["artifact_digest"] == payload_digest
    assert inspected["completion_enabled"] is False
    assert "capture a solved setup path" not in json.dumps(inspected)

    card_status_before_status = scalar(conn, "select status from experience_cards where id = %s", (card_id,))
    card_events_before_status = scalar(conn, "select count(*) from card_events where tenant_id = %s and card_id = %s", (tenant_a, card_id))
    handoffs_before_status = scalar(conn, "select count(*) from approval_handoffs where tenant_id = %s", (tenant_a,))
    code, status_payload = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "status",
        "--tenant",
        str(tenant_a),
        "--handoff",
        handoff_id,
    )
    assert code == 0
    assert status_payload["handoff_id"] == handoff_id
    assert status_payload["handoff"]["action"] == "status"
    assert status_payload["handoff"]["state"] == "pending_user_consent"
    assert status_payload["handoff"]["card_status"] == "awaiting_user_approval"
    assert status_payload["handoff"]["consent_completed"] is False
    assert status_payload["handoff"]["active_matching_consent"] is False
    assert status_payload["handoff"]["challenge_used"] is False
    assert status_payload["handoff"]["handoff_digest_valid"] is True
    assert status_payload["operation"] == "approval_handoff_status"
    assert status_payload["command_effect"] == "read_only"
    assert status_payload["completion_authority"] == "none"
    assert status_payload["publication_authority"] == "none"
    assert status_payload["creates_handoff"] is False
    assert status_payload["creates_or_rotates_challenge"] is False
    assert status_payload["opens_trusted_surface"] is False
    assert status_payload["writes_consent_event"] is False
    assert status_payload["writes_publication_event"] is False
    assert status_payload["writes_revocation_or_tombstone_event"] is False
    assert status_payload["lifecycle_state_changed"] is False
    assert status_payload["emitted_events"] == []
    assert status_payload["verification"]["schema_version"] == "approval-handoff-verification-v0"
    assert status_payload["verification"]["read_only"] is True
    assert status_payload["verification"]["completion_enabled"] is False
    assert status_payload["verification"]["trusted_completion_enabled"] is False
    assert status_payload["verification"]["public_publication_enabled"] is False
    assert status_payload["verification"]["team_sharing_enabled"] is False
    assert status_payload["verification"]["team_namespace_grant_enabled"] is False
    assert status_payload["verification"]["checks"]["digest_binding_valid"] is True
    assert status_payload["verification"]["checks"]["handoff_digest_valid"] is True
    assert status_payload["verification"]["checks"]["consent_record_exists"] is False
    assert status_payload["verification"]["checks"]["active_matching_consent"] is False
    assert status_payload["verification"]["checks"]["revocation_visible"] is False
    assert status_payload["verification"]["blockers"] == []
    assert status_payload["completion_enabled"] is False
    assert status_payload["trusted_completion_enabled"] is False
    assert status_payload["public_publication_enabled"] is False
    assert status_payload["team_sharing_enabled"] is False
    assert status_payload["team_namespace_grant_enabled"] is False
    assert status_payload["terminal_publication_completion_enabled"] is False
    assert "payload_json" not in json.dumps(status_payload)
    assert "event_payload_json" not in json.dumps(status_payload)
    assert "subject_id" not in json.dumps(status_payload)
    assert "created_by" not in json.dumps(status_payload)
    assert "capture a solved setup path" not in json.dumps(status_payload)
    serialized_verified = json.dumps(status_payload, sort_keys=True)
    for forbidden in [
        "approved_private",
        "approved_for_publication",
        "published",
        "reviewer_published",
        "complete_publication_approval",
        "complete_private_retention_approval",
        "complete_team_namespace_grant",
    ]:
        assert forbidden not in serialized_verified
    assert scalar(conn, "select count(*) from consent_records where challenge_id = %s", (challenge_id,)) == 0
    assert scalar(conn, "select used_by_consent_id is null from approval_challenges where id = %s", (challenge_id,))
    assert scalar(conn, "select used_at is null from approval_challenges where id = %s", (challenge_id,))
    assert scalar(conn, "select status from experience_cards where id = %s", (card_id,)) == card_status_before_status
    assert scalar(conn, "select count(*) from card_events where tenant_id = %s and card_id = %s", (tenant_a, card_id)) == card_events_before_status
    assert scalar(conn, "select count(*) from approval_handoffs where tenant_id = %s", (tenant_a,)) == handoffs_before_status
    assert scalar(conn, "select count(*) from consent_records where card_version_id = %s and scope in ('public_publication', 'team_namespace_grant')", (version_id,)) == 0
    assert scalar(conn, "select status not in ('approved_for_publication', 'published', 'indexed_hot', 'indexed_main') from experience_cards where id = %s", (card_id,))

    conn.execute("update approval_handoffs set invalidated_at = now() where id = %s", (handoff_id,))
    conn.commit()
    code, invalidated = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "status",
        "--tenant",
        str(tenant_a),
        "--handoff",
        handoff_id,
    )
    assert code == 0
    assert invalidated["handoff"]["action"] == "status"
    assert invalidated["verification"]["completion_enabled"] is False
    assert invalidated["verification"]["checks"]["handoff_invalidated"] is True
    assert "handoff_invalidated" in invalidated["verification"]["blockers"]
    assert scalar(conn, "select count(*) from consent_records where challenge_id = %s", (challenge_id,)) == 0

    code, denied = run_knudgctl(
        migrated_db,
        "writer",
        "approval-handoff",
        "complete",
        "--tenant",
        str(tenant_a),
        "--handoff",
        handoff_id,
    )
    assert code == 3
    assert denied["status"] == "usage_error"
    assert scalar(conn, "select count(*) from consent_records where challenge_id = %s", (challenge_id,)) == 0


def test_approval_handoff_verification_contract_is_read_only_and_disabled():
    from scripts import knudgctl

    row = {
        "handoff_invalidated": False,
        "expired": False,
        "challenge_used": False,
        "challenge_invalidated": False,
        "challenge_expired": False,
        "consent_record_exists": False,
        "active_matching_consent": False,
        "revocation_visible": False,
        "digest_binding_valid": True,
        "handoff_digest_valid": True,
        "card_current_version_matches": True,
        "card_status": "awaiting_user_approval",
    }

    verification = knudgctl.approval_handoff_verification(row)
    assert verification["schema_version"] == "approval-handoff-verification-v0"
    assert verification["read_only"] is True
    assert verification["completion_enabled"] is False
    assert verification["trusted_completion_enabled"] is False
    assert verification["public_publication_enabled"] is False
    assert verification["team_sharing_enabled"] is False
    assert verification["team_namespace_grant_enabled"] is False
    assert verification["protected_data_serving_enabled"] is False
    assert verification["blockers"] == []

    row["consent_record_exists"] = True
    row["digest_binding_valid"] = False
    blocked = knudgctl.approval_handoff_verification(row)
    assert "consent_record_exists" in blocked["blockers"]
    assert "digest_binding_valid" in blocked["blockers"]
    assert blocked["completion_enabled"] is False


def test_knudgctl_approval_handoff_status_subcommand_is_registered():
    from scripts import knudgctl

    tenant_id = str(uuid.uuid4())
    handoff_id = str(uuid.uuid4())
    parser = knudgctl.build_parser()

    status_args = parser.parse_args([
        "writer",
        "approval-handoff",
        "status",
        "--tenant",
        tenant_id,
        "--handoff",
        handoff_id,
    ])

    assert status_args.func is knudgctl.writer_approval_handoff_status


def test_knudgctl_local_private_capture_search_revoke_purge_vertical_loop(conn, migrated_db, tmp_path):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    conn.commit()
    local_card = {
        "source_class": "local_private_dogfood",
        "title": "Psycopg migration capture path",
        "human_summary": {
            "content": "Local database migration cards need a bounded capture and search path.",
            "redaction_summary": "Removed private paths, hostnames, usernames, env values, and raw logs.",
        },
        "problem_summary": "The local database migration search fixture needed a reusable capture path.",
        "solution_summary": "Restart the local queue worker after applying the migration and re-run pytest.",
        "public_packages": ["psycopg", "pytest"],
        "environment_tags": ["windows", "postgres"],
        "public_reference_urls": ["https://docs.python.org/3/library/json.html"],
        "command_labels": ["pytest", "migrate status"],
        "error_fingerprints": ["migration-search-fixture"],
        "lessons": ["Keep local private bodies in the side table."],
    }
    local_card_path = tmp_path / "local-card.json"
    local_card_path.write_text(json.dumps(local_card), encoding="utf-8")
    task_profile = {
        "schema_version": "task_profile.v0",
        "intent": "debug",
        "explicit_query": "psycopg migration capture",
        "repo_shape_category": "pytest-postgres",
        "public_packages": ["psycopg"],
        "error_fingerprints": ["migration-search-fixture"],
        "coarse_os": "windows",
        "recent_event_kinds": ["task_start"],
    }
    task_profile_path = tmp_path / "task-profile.json"
    task_profile_path.write_text(json.dumps(task_profile), encoding="utf-8")

    code, preflight = run_knudgctl(migrated_db, "local", "preflight-db")
    assert code == 0
    assert preflight["local_private_schema_ready"] is True
    assert preflight["missing"] == []
    assert preflight["missing_indexes"] == []
    assert preflight["missing_migrations"] == []
    assert preflight["extensions"]["pgcrypto"]["schema"] == "knudg_crypto"
    assert preflight["postgres"]["server_version_num"] >= 160000
    assert preflight["fts"]["rank_manifest_version"] == "local_private_fts_v0"
    assert all(item["force_row_security"] for item in preflight["rls"].values())

    code, captured = run_knudgctl(
        migrated_db,
        "local",
        "capture",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--created-by",
        str(principal),
        "--input",
        str(local_card_path),
    )
    assert code == 0
    assert captured["status"] == "captured"
    assert captured["source_class"] == "local_private_dogfood"
    assert re.fullmatch(r"[0-9a-f]{64}", captured["body_digest"])
    card_id = captured["card_id"]
    version_id = captured["card_version_id"]
    assert scalar(conn, "select status from experience_cards where id = %s", (card_id,)) == "approved_private"
    assert scalar(conn, "select count(*) from local_private_card_bodies where card_id = %s", (card_id,)) == 1
    stored_version = conn.execute("select payload_json, payload_digest from card_versions where id = %s", (version_id,)).fetchone()
    stored_projection = stored_version[0]
    assert stored_projection["source_class"] == "local_private_dogfood"
    assert stored_projection["visibility"] == "local_private"
    assert stored_projection["sharing_state"] == "not_shared"
    assert stored_projection["publication_state"] == "never_publishable"
    assert stored_projection["privacy"]["source_class"] == "local_private_dogfood"
    assert stored_projection["privacy"]["body_digest"] == captured["body_digest"]
    assert local_card["title"] not in json.dumps(stored_projection)
    assert local_card["problem_summary"] not in json.dumps(stored_projection)

    code, found = run_knudgctl(
        migrated_db,
        "local",
        "search",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--principal",
        str(principal),
        "--task-profile",
        str(task_profile_path),
    )
    assert code == 0
    result = found["result"]
    assert result["decision"] == "cards_found"
    assert result["served_from"] == "local_private_exact_fts"
    assert result["cards"][0]["card_id"] == card_id
    assert result["cards"][0]["card_version_id"] == version_id
    assert result["cards"][0]["digest"] == stored_version[1]
    assert result["cards"][0]["local_only_status"] == "local_private"
    assert result["cards"][0]["freshness_bucket"] == "local_private_current"
    assert "summary" not in result["cards"][0]
    assert result["cards"][0]["provenance"]["source_class"] == "local_private_dogfood"
    serialized = json.dumps(found)
    assert local_card["title"] not in serialized
    assert local_card["problem_summary"] not in serialized
    assert "Restart the local queue worker" not in serialized
    assert "search_text" not in serialized
    assert "payload_json" not in serialized
    assert found["publication_enabled"] is False

    code, denied = run_knudgctl(
        migrated_db,
        "local",
        "search",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--principal",
        str(uuid.uuid4()),
        "--task-profile",
        str(task_profile_path),
    )
    assert code == 4
    assert denied["status"] == "fence_failed"
    assert denied["fence"] == "local_principal_binding"

    code, audit = run_knudgctl(
        migrated_db,
        "local",
        "audit-boundary",
        "--tenant",
        str(tenant_a),
        "--principal",
        str(principal),
    )
    assert code == 0
    assert audit["local_private_publication_boundary_clear"] is True
    assert all(value == "clear" for value in audit["checked_surfaces"].values())
    assert "embedding_vectors" in audit["future_surfaces"]

    code, revoked = run_knudgctl(
        migrated_db,
        "local",
        "revoke",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--principal",
        str(principal),
        "--card-id",
        card_id,
        "--reason",
        "operator test revoke",
    )
    assert code == 0
    assert revoked["revoked"] is True

    code, hidden = run_knudgctl(
        migrated_db,
        "local",
        "search",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--principal",
        str(principal),
        "--task-profile",
        str(task_profile_path),
    )
    assert code == 0
    assert hidden["result"]["decision"] == "no_suggestion"

    code, fences = run_knudgctl(
        migrated_db,
        "local",
        "verify-fences",
        "--tenant",
        str(tenant_a),
        "--card-id",
        card_id,
        "--principal",
        str(principal),
    )
    assert code == 0
    assert fences["active_search_documents"] == 0

    code, purged = run_knudgctl(
        migrated_db,
        "local",
        "purge",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--principal",
        str(principal),
        "--card-id",
        card_id,
        "--reason",
        "operator test purge",
    )
    assert code == 0
    assert purged["purged"] is True
    assert scalar(conn, "select body_json = '{}'::jsonb from local_private_card_bodies where card_id = %s", (card_id,))
    assert scalar(conn, "select search_text = '' from local_private_search_documents where card_id = %s", (card_id,))

    code, post_purge_hidden = run_knudgctl(
        migrated_db,
        "local",
        "search",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--principal",
        str(principal),
        "--task-profile",
        str(task_profile_path),
    )
    assert code == 0
    assert post_purge_hidden["result"]["decision"] == "no_suggestion"

    code, post_purge_fences = run_knudgctl(
        migrated_db,
        "local",
        "verify-fences",
        "--tenant",
        str(tenant_a),
        "--card-id",
        card_id,
        "--principal",
        str(principal),
    )
    assert code == 0
    assert post_purge_fences["active_search_documents"] == 0
    assert post_purge_fences["active_bodies"] == 0
    assert post_purge_fences["purged_bodies"] == 1


def test_knudgctl_local_private_capture_rejects_raw_data_without_echo(conn, migrated_db, tmp_path):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    conn.commit()
    canary = r"C:\redacted\private\repo"
    local_card = {
        "source_class": "local_private_dogfood",
        "title": "Private path capture leak",
        "human_summary": {
            "content": "Private path card inputs must be rejected before storage.",
            "redaction_summary": "Removed private paths, hostnames, usernames, env values, and raw logs.",
        },
        "problem_summary": f"The capture includes a forbidden machine path {canary}.",
        "solution_summary": "The record should be rejected before it reaches storage.",
        "public_packages": ["pytest"],
        "environment_tags": ["windows"],
        "public_reference_urls": [],
        "command_labels": ["pytest"],
        "error_fingerprints": ["private-path"],
        "lessons": ["Reject raw private paths."],
    }
    local_card_path = tmp_path / "raw-local-card.json"
    local_card_path.write_text(json.dumps(local_card), encoding="utf-8")

    code, rejected = run_knudgctl(
        migrated_db,
        "local",
        "capture",
        "--tenant",
        str(tenant_a),
        "--namespace",
        str(ns_a),
        "--created-by",
        str(principal),
        "--input",
        str(local_card_path),
    )
    assert code == 2
    assert rejected["status"] == "rejected"
    assert rejected["reject_class"] == "local_private_card"
    serialized = json.dumps(rejected)
    assert "C:\\Users" not in serialized
    assert "private\\repo" not in serialized
    assert scalar(conn, "select count(*) from local_private_card_bodies where tenant_id = %s", (tenant_a,)) == 0


def test_knudgctl_revocation_status(conn, migrated_db):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, secret, kid = seed_base(conn)
    grant_submit(conn, tenant_a, ns_a, principal)
    card_id, _version_id, _created = submit_candidate(conn, tenant_a, principal, ns_a, secret, kid)
    conn.commit()
    conn.execute("reset role")
    revoke_subject(conn, tenant_a, principal, ns_a, secret, kid, "card", card_id)
    conn.commit()

    code, payload = run_knudgctl(migrated_db, "revocation", "status", str(card_id), "--tenant", str(tenant_a))
    assert code == 0
    assert payload["revoked"] is True
    assert payload["tenant_revocation_epoch"] == 1
    assert payload["tombstones"][0]["card_id"] == str(card_id)


def test_idempotency_conflicts(conn):
    tenant_a, _tenant_b, principal, ns_a, _ns_b, _secret, _kid = seed_base(conn)
    card_id, _version_id = create_card(conn, tenant_a, ns_a, principal)
    event_id = insert_card_event(conn, tenant_a, card_id, principal, "discard_requested", "candidate_created", "discard_pending")[0]
    logical_id = uuid.uuid4()
    conn.execute(
        """
        insert into idempotency_keys(
          tenant_id, id, operation, logical_object_type, logical_object_id, operation_version,
          idempotency_key, request_digest, response_digest, effect_event_source_type, effect_card_event_id
        )
        values (%s, %s, 'submit_candidate', 'card', %s, 1, 'same-key', 'sha256:req1', 'sha256:resp', 'card', %s)
        """,
        (tenant_a, uuid.uuid4(), logical_id, event_id),
    )
    with pytest.raises(psycopg.Error):
        conn.execute(
            """
            insert into idempotency_keys(
              tenant_id, id, operation, logical_object_type, logical_object_id, operation_version,
              idempotency_key, request_digest, response_digest, effect_event_source_type, effect_card_event_id
            )
            values (%s, %s, 'submit_candidate', 'card', %s, 1, 'same-key', 'sha256:req2', 'sha256:resp', 'card', %s)
            """,
            (tenant_a, uuid.uuid4(), logical_id, event_id),
        )

