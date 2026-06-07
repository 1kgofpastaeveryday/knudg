import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from tests.test_m0_schema import db_url, maintenance_url, run_migrate


ROOT = Path(__file__).resolve().parents[1]
UP_SQL = ROOT / "migrations" / "0012_redacted_experience_storage.up.sql"
DOWN_SQL = ROOT / "migrations" / "0012_redacted_experience_storage.down.sql"
DETAIL_CLASSES = [
    "selection_status",
    "private_message",
    "private_person_identity",
    "exact_timestamp",
    "raw_source_material",
    "protected_identity_signal",
    "device_or_network_signal",
]


@pytest.fixture(scope="module")
def migrated_db():
    name = f"knudg_redacted_experience_{uuid.uuid4().hex}"
    try:
        with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not reachable for redacted experience storage migration tests: {exc}")
    url = db_url(name)
    run_migrate(url, "up")
    yield url
    with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
        conn.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = %s", (name,))
        conn.execute(sql.SQL("drop database if exists {}").format(sql.Identifier(name)))


@pytest.fixture()
def conn(migrated_db):
    with psycopg.connect(migrated_db, connect_timeout=3) as connection:
        yield connection


def seed_scope(conn):
    tenant_id = uuid.uuid4()
    principal_id = uuid.uuid4()
    namespace_id = uuid.uuid4()
    conn.execute("insert into tenants(id, slug, name) values (%s, %s, 'Tenant')", (tenant_id, f"tenant-{tenant_id.hex}"))
    conn.execute(
        "insert into principals(id, principal_type, display_name) values (%s, 'human_user', 'Test User')",
        (principal_id,),
    )
    conn.execute(
        "insert into namespaces(tenant_id, id, key, name, visibility) values (%s, %s, 'experience', 'Experience', 'private')",
        (tenant_id, namespace_id),
    )
    return tenant_id, principal_id, namespace_id


def seed_private_retention_proof(conn, tenant_id, principal_id, namespace_id):
    card_id = uuid.uuid4()
    version_id = uuid.uuid4()
    challenge_id = uuid.uuid4()
    handoff_id = uuid.uuid4()
    event_id = uuid.uuid4()
    consent_id = uuid.uuid4()
    event_stream_position = conn.execute("select nextval('event_stream_position_seq')").fetchone()[0]
    artifact_digest = conn.execute(
        "select encode(knudg_crypto.digest(knudg_private.canonical_jsonb('{}'::jsonb), 'sha256'), 'hex')"
    ).fetchone()[0]
    policy_digest = "sha256:" + "b" * 64
    challenge_digest = "sha256:" + "e" * 64
    handoff_digest = "sha256:" + "f" * 64
    conn.execute(
        """
        insert into experience_cards(
          tenant_id, id, namespace_id, current_version_id, status,
          outcome_type, quality_state, evidence_strength, created_by
        )
        values (%s, %s, %s, %s, 'approved_private', 'solved', 'unreviewed', 'operator_judgment', %s)
        """,
        (tenant_id, card_id, namespace_id, version_id, principal_id),
    )
    conn.execute(
        """
        insert into card_versions(
          tenant_id, id, card_id, version_number, card_schema_version,
          payload_json, payload_digest, created_by
        )
        values (%s, %s, %s, 1, 1, '{}'::jsonb, %s, %s)
        """,
        (tenant_id, version_id, card_id, artifact_digest, principal_id),
    )
    conn.execute(
        """
        insert into card_events(
          tenant_id, card_id, event_id, event_stream_position, event_seq, event_type,
          actor_id, actor_role, previous_status, next_status, expected_current_version,
          correlation_id, idempotency_key, event_payload_schema_version,
          event_payload_json, event_payload_digest
        )
        values (
          %s, %s, %s, %s, 1, 'private_approved',
          %s, 'app_user', 'awaiting_user_approval', 'approved_private', %s,
          %s, 'proof-event', 1, '{}'::jsonb, 'sha256:event-private-approved'
        )
        """,
        (tenant_id, card_id, event_id, event_stream_position, principal_id, version_id, uuid.uuid4()),
    )
    conn.execute(
        "insert into event_stream_positions(event_stream_position, tenant_id, event_source_type, card_event_id) values (%s, %s, 'card', %s)",
        (event_stream_position, tenant_id, event_id),
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
          %s, %s, %s, 'private-retention-v1',
          %s, %s, 'test-proof', now() + interval '5 minutes', %s
        )
        """,
        (
            tenant_id,
            challenge_id,
            principal_id,
            namespace_id,
            version_id,
            version_id,
            artifact_digest,
            policy_digest,
            challenge_digest,
            principal_id,
        ),
    )
    conn.execute(
        """
        insert into approval_handoffs(
          tenant_id, id, challenge_id, subject_id, namespace_id, consent_scope,
          artifact_type, artifact_id, card_version_id, artifact_digest,
          policy_version, policy_digest, challenge_digest, handoff_digest,
          origin, expires_at, created_by
        )
        values (
          %s, %s, %s, %s, %s, 'private_retention',
          'card_version', %s, %s, %s,
          'private-retention-v1', %s, %s, %s,
          'test-proof', now() + interval '5 minutes', %s
        )
        """,
        (
            tenant_id,
            handoff_id,
            challenge_id,
            principal_id,
            namespace_id,
            version_id,
            version_id,
            artifact_digest,
            policy_digest,
            challenge_digest,
            handoff_digest,
            principal_id,
        ),
    )
    conn.execute(
        """
        insert into consent_records(
          tenant_id, id, subject_id, scope, namespace_id, artifact_type,
          artifact_id, card_version_id, artifact_digest, policy_version,
          policy_digest, challenge_id, challenge_digest, grant_card_event_id,
          retention_policy, retention_purpose
        )
        values (
          %s, %s, %s, 'private_retention', %s, 'card_version',
          %s, %s, %s, 'private-retention-v1',
          %s, %s, %s, %s, 'private_mvp_default', 'agent_experience_reuse'
        )
        """,
        (
            tenant_id,
            consent_id,
            principal_id,
            namespace_id,
            version_id,
            version_id,
            artifact_digest,
            policy_digest,
            challenge_id,
            challenge_digest,
            event_id,
        ),
    )
    return {
        "consent_id": consent_id,
        "handoff_id": handoff_id,
        "challenge_id": challenge_id,
        "card_id": card_id,
        "card_version_id": version_id,
        "artifact_digest": artifact_digest,
        "policy_version": "private-retention-v1",
        "policy_digest": policy_digest,
        "challenge_digest": challenge_digest,
        "handoff_digest": handoff_digest,
        "granted_at": conn.execute("select granted_at from consent_records where tenant_id = %s and id = %s", (tenant_id, consent_id)).fetchone()[0],
        "grant_card_event_id": event_id,
    }


def insert_redacted_record(conn, tenant_id, principal_id, namespace_id, **overrides):
    proof = overrides.pop("proof", None) or seed_private_retention_proof(conn, tenant_id, principal_id, namespace_id)
    values = {
        "tenant_id": tenant_id,
        "id": uuid.uuid4(),
        "namespace_id": namespace_id,
        "created_by": principal_id,
        "domain": "career_private",
        "subject_type": "company",
        "subject_public_name": "Example Company",
        "subject_aliases": [],
        "title": "Interview process felt slow",
        "summary": "A redacted career experience record with company name retained and private details removed.",
        "observations": ["The process cadence felt slower than expected."],
        "subjective_impressions": ["The experience felt somewhat disorganized."],
        "disallowed_detail_classes": DETAIL_CLASSES,
        "private_retention_consent_id": proof["consent_id"],
        "private_retention_handoff_id": proof["handoff_id"],
        "private_retention_challenge_id": proof["challenge_id"],
        "consented_card_id": proof["card_id"],
        "consented_card_version_id": proof["card_version_id"],
        "consented_artifact_digest": proof["artifact_digest"],
        "consent_policy_version": proof["policy_version"],
        "consent_policy_digest": proof["policy_digest"],
        "consent_challenge_digest": proof["challenge_digest"],
        "consent_handoff_digest": proof["handoff_digest"],
        "consent_granted_at": proof["granted_at"],
        "consent_grant_card_event_id": proof["grant_card_event_id"],
        "source_digest": "sha256:" + proof["artifact_digest"].removeprefix("sha256:"),
        "redaction_digest": "sha256:" + "d" * 64,
        "payload_digest": "sha256:" + "e" * 64,
        "retrieval_policy": "explicit_or_contextual",
        "database_write_enabled": True,
        "record_visible_to_retrieval": False,
        "public_candidate_conversion_enabled": False,
        "public_serving_enabled": False,
        "b2b_delivery_enabled": False,
        "identity_processing_enabled": False,
        "raw_detail_escrow_enabled": False,
        "dashboard_enabled": False,
    }
    values.update(overrides)
    conn.execute(
        """
        insert into redacted_private_experience_records(
          tenant_id, id, namespace_id, created_by, domain, subject_type,
          subject_public_name, subject_aliases, title, summary, observations, subjective_impressions,
          disallowed_detail_classes, private_retention_consent_id, private_retention_handoff_id,
          private_retention_challenge_id, consented_card_id, consented_card_version_id,
          consented_artifact_digest, consent_policy_version, consent_policy_digest,
          consent_challenge_digest, consent_handoff_digest, consent_granted_at,
          consent_grant_card_event_id, source_digest, redaction_digest, payload_digest,
          retrieval_policy, database_write_enabled, record_visible_to_retrieval,
          public_candidate_conversion_enabled, public_serving_enabled,
          b2b_delivery_enabled, identity_processing_enabled,
          raw_detail_escrow_enabled, dashboard_enabled
        )
        values (
          %(tenant_id)s, %(id)s, %(namespace_id)s, %(created_by)s, %(domain)s,
          %(subject_type)s, %(subject_public_name)s, %(subject_aliases)s, %(title)s, %(summary)s,
          %(observations)s, %(subjective_impressions)s, %(disallowed_detail_classes)s,
          %(private_retention_consent_id)s, %(private_retention_handoff_id)s,
          %(private_retention_challenge_id)s, %(consented_card_id)s, %(consented_card_version_id)s,
          %(consented_artifact_digest)s, %(consent_policy_version)s, %(consent_policy_digest)s,
          %(consent_challenge_digest)s, %(consent_handoff_digest)s, %(consent_granted_at)s,
          %(consent_grant_card_event_id)s,
          %(source_digest)s, %(redaction_digest)s, %(payload_digest)s,
          %(retrieval_policy)s, %(database_write_enabled)s, %(record_visible_to_retrieval)s,
          %(public_candidate_conversion_enabled)s, %(public_serving_enabled)s,
          %(b2b_delivery_enabled)s, %(identity_processing_enabled)s,
          %(raw_detail_escrow_enabled)s, %(dashboard_enabled)s
        )
        """,
        values,
    )
    return values["id"]


def test_redacted_experience_storage_sql_keeps_future_surfaces_disabled():
    sql_text = UP_SQL.read_text(encoding="utf-8")
    assert "create table if not exists redacted_private_experience_records" in sql_text
    assert "raw_source_retention text not null default 'none'" in sql_text
    assert "raw_detail_escrow_ref uuid null check (raw_detail_escrow_ref is null)" in sql_text
    assert "raw_source_available_to_model boolean not null default false" in sql_text
    assert "subject_aliases text[] not null default '{}'::text[] check" in sql_text
    assert "coalesce(array_length(subject_aliases, 1), 0) <= 8" in sql_text
    assert "coalesce(array_length(observations, 1), 0) between 1 and 8" in sql_text
    assert "disallowed_detail_classes <@ array[" in sql_text
    assert "not knudg_private.text_array_has_duplicates(disallowed_detail_classes)" in sql_text
    assert "private_retention_consent_id uuid not null" in sql_text
    assert "private_retention_handoff_id uuid not null" in sql_text
    assert "foreign key (tenant_id, private_retention_consent_id) references consent_records(tenant_id, id)" in sql_text
    assert "foreign key (tenant_id, private_retention_handoff_id) references approval_handoffs(tenant_id, id)" in sql_text
    assert "enforce_redacted_private_experience_consent_binding" in sql_text
    assert "regexp_replace(source_digest, '^sha256:', '') = regexp_replace(consented_artifact_digest, '^sha256:', '')" in sql_text
    assert "private_retention_consent_completed" not in sql_text
    assert "lifecycle_status text not null default 'captured'" in sql_text
    assert "revoked_at timestamptz null" in sql_text
    assert "purged_at timestamptz null" in sql_text
    assert "database_write_enabled boolean not null default true" in sql_text
    assert "record_visible_to_retrieval boolean not null default false" in sql_text
    assert "retrieval_policy text not null default 'explicit_or_contextual'" in sql_text
    for flag in [
        "public_candidate_conversion_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "identity_processing_enabled",
        "raw_detail_escrow_enabled",
        "dashboard_enabled",
    ]:
        assert f"{flag} boolean not null default false" in sql_text
        assert f"check ({flag} = false)" in sql_text
    assert "grant insert" not in sql_text.lower()
    assert "grant update" not in sql_text.lower()
    assert "grant delete" not in sql_text.lower()
    assert "grant execute on function knudg_closed_api_store_redacted_experience(text, jsonb) to knudg_api_app" in sql_text
    assert "grant execute on function knudg_closed_api_complete_private_retention(text, uuid, text, text, uuid, text, text, text, boolean, boolean, boolean) to knudg_api_app" in sql_text
    assert "grant execute on function knudg_closed_api_revoke_redacted_experience(text, uuid, text) to knudg_api_app" in sql_text
    assert "grant execute on function knudg_closed_api_purge_redacted_experience(text, uuid, text) to knudg_api_app" in sql_text
    assert "grant select on redacted_private_experience_records to knudg_app" not in sql_text
    assert "grant select on redacted_private_experience_records to knudg_worker" not in sql_text
    assert "payload_json" not in sql_text
    assert "raw_body" not in sql_text
    assert "search_text" not in sql_text
    assert "search_vector" not in sql_text
    assert "embedding" not in sql_text


def test_redacted_experience_storage_down_drops_only_storage_table():
    sql_text = DOWN_SQL.read_text(encoding="utf-8")
    assert "drop table if exists redacted_private_experience_records" in sql_text
    assert "experience_domain_policies" not in sql_text
    assert "candidate_domain_facets" not in sql_text


def test_redacted_experience_storage_accepts_redacted_career_record(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    record_id = insert_redacted_record(conn, tenant_id, principal_id, namespace_id)
    row = conn.execute(
        """
        select domain, subject_type, raw_source_retention, raw_detail_escrow_ref,
          database_write_enabled, lifecycle_status, public_candidate_conversion_enabled, b2b_delivery_enabled, dashboard_enabled
        from redacted_private_experience_records
        where tenant_id = %s and id = %s
        """,
        (tenant_id, record_id),
    ).fetchone()
    assert row == ("career_private", "company", "none", None, True, "captured", False, False, False)


def test_redacted_experience_storage_rejects_mismatched_consent_proof(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(
            conn,
            tenant_id,
            principal_id,
            namespace_id,
            consent_policy_digest="sha256:" + "9" * 64,
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("private_retention_handoff_id", uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")),
        ("private_retention_challenge_id", uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")),
        ("consented_card_id", uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")),
        ("consented_card_version_id", uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")),
        ("consent_handoff_digest", "sha256:" + "9" * 64),
        ("source_digest", "sha256:" + "8" * 64),
    ],
)
def test_redacted_experience_storage_rejects_broken_consent_binding_fields(conn, field, value):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation)):
        insert_redacted_record(conn, tenant_id, principal_id, namespace_id, **{field: value})


def test_redacted_experience_storage_rejects_raw_summary_marker(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(
            conn,
            tenant_id,
            principal_id,
            namespace_id,
            summary="This redacted record accidentally includes user@example.com.",
        )


def test_redacted_experience_storage_rejects_place_domain_with_company_subject(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(
            conn,
            tenant_id,
            principal_id,
            namespace_id,
            domain="place_service_experience",
            subject_type="company",
        )


def test_redacted_experience_storage_rejects_missing_disallowed_detail_classes(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(
            conn,
            tenant_id,
            principal_id,
            namespace_id,
            disallowed_detail_classes=[item for item in DETAIL_CLASSES if item != "selection_status"],
        )


def test_redacted_experience_storage_rejects_extra_disallowed_detail_class(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(
            conn,
            tenant_id,
            principal_id,
            namespace_id,
            disallowed_detail_classes=[*DETAIL_CLASSES, "private_extra"],
        )


def test_redacted_experience_storage_rejects_duplicate_disallowed_detail_class(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(
            conn,
            tenant_id,
            principal_id,
            namespace_id,
            disallowed_detail_classes=[*DETAIL_CLASSES, "selection_status"],
        )


def test_redacted_experience_storage_rejects_empty_observations(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(conn, tenant_id, principal_id, namespace_id, observations=[])


def test_redacted_experience_storage_rejects_raw_marker_in_alias(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(conn, tenant_id, principal_id, namespace_id, subject_aliases=["team@example.com"])


def test_redacted_experience_storage_rejects_duplicate_alias(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(conn, tenant_id, principal_id, namespace_id, subject_aliases=["Example", "Example"])


@pytest.mark.parametrize(
    "flag",
    [
        "database_write_enabled",
        "record_visible_to_retrieval",
        "public_candidate_conversion_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "identity_processing_enabled",
        "raw_detail_escrow_enabled",
        "dashboard_enabled",
    ],
)
def test_redacted_experience_storage_rejects_enabled_future_surface_flags(conn, flag):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    value = False if flag == "database_write_enabled" else True
    with pytest.raises(psycopg.errors.CheckViolation):
        insert_redacted_record(conn, tenant_id, principal_id, namespace_id, **{flag: value})


def test_redacted_experience_storage_app_role_has_no_insert_grant(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    conn.commit()
    conn.execute("set role knudg_app")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        insert_redacted_record(conn, tenant_id, principal_id, namespace_id)


def test_redacted_experience_storage_worker_role_has_no_select_grant(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    insert_redacted_record(conn, tenant_id, principal_id, namespace_id)
    conn.commit()
    conn.execute("set role knudg_worker")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select count(*) from redacted_private_experience_records").fetchone()


def test_redacted_experience_storage_readonly_ops_rls_returns_no_rows(conn):
    tenant_id, principal_id, namespace_id = seed_scope(conn)
    insert_redacted_record(conn, tenant_id, principal_id, namespace_id)
    conn.commit()
    conn.execute("set role knudg_readonly_ops")
    assert conn.execute("select count(*) from redacted_private_experience_records").fetchone()[0] == 0
