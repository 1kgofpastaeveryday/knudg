import json
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from tests.test_m0_schema import db_url, maintenance_url, run_migrate


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FIXTURE = ROOT / "fixtures" / "domain-policy-registry.draft.json"
UP_SQL = ROOT / "migrations" / "0011_domain_policy_lookup.up.sql"


@pytest.fixture(scope="module")
def migrated_db():
    name = f"knudg_domain_policy_{uuid.uuid4().hex}"
    try:
        with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not reachable for domain policy migration tests: {exc}")
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


def test_domain_policy_lookup_matches_registry_fixture(conn):
    registry = json.loads(REGISTRY_FIXTURE.read_text(encoding="utf-8"))["domains"]
    rows = conn.execute(
        """
        select domain, allowed_intents, default_visibility, default_retrieval_policy,
          ingest_enablement, public_eligible, redaction_class, ttl_class, cross_domain_search
        from experience_domain_policies
        """
    ).fetchall()
    policies = {
        row[0]: {
            "allowed_intents": row[1],
            "default_visibility": row[2],
            "default_retrieval_policy": row[3],
            "ingest_enablement": row[4],
            "public_eligible": row[5],
            "redaction_class": row[6],
            "ttl_class": row[7],
            "cross_domain_search": row[8],
        }
        for row in rows
    }
    assert set(policies) == set(registry)
    for domain, expected in registry.items():
        actual = policies[domain]
        for key, value in expected.items():
            if key == "domain":
                continue
            assert actual[key] == value


def test_domain_policy_lookup_keeps_broader_domains_non_ingestable(conn):
    rows = conn.execute(
        """
        select domain, ingest_enablement, public_eligible
        from experience_domain_policies
        where domain in ('career_private', 'place_service_experience', 'public_experience_candidate')
        order by domain
        """
    ).fetchall()
    assert rows == [
        ("career_private", "disabled_until_gate", False),
        ("place_service_experience", "disabled_until_gate", False),
        ("public_experience_candidate", "disabled_until_gate", False),
    ]


def test_domain_policy_lookup_rejects_unknown_domain(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            """
            insert into experience_domain_policies(
              domain, allowed_intents, default_visibility, default_retrieval_policy,
              ingest_enablement, public_eligible, redaction_class, ttl_class, cross_domain_search
            )
            values (
              'unknown_domain', array['unknown']::text[], 'private', 'explicit_or_contextual',
              'disabled_until_gate', false, 'career', 'policy_defined', 'deny_by_default'
            )
            """
        )


def test_candidate_domain_facets_sql_is_metadata_only():
    sql_text = UP_SQL.read_text(encoding="utf-8")
    assert "create table if not exists candidate_domain_facets" in sql_text
    assert "stores_raw_body boolean not null default false" in sql_text
    assert "creates_card boolean not null default false" in sql_text
    assert "indexes boolean not null default false" in sql_text
    assert "check (stores_raw_body = false)" in sql_text
    assert "check (indexes = false)" in sql_text
    assert "check (creates_card = false)" in sql_text
    assert "raw_body" not in sql_text.replace("stores_raw_body", "")


def test_candidate_domain_facets_rejects_broader_domain_ingest_when_db_available(conn):
    tenant_id = uuid.uuid4()
    principal_id = uuid.uuid4()
    namespace_id = uuid.uuid4()
    conn.execute("insert into tenants(id, slug, name) values (%s, %s, 'Tenant')", (tenant_id, f"tenant-{tenant_id.hex}"))
    conn.execute(
        "insert into principals(id, principal_type, display_name, external_subject) values (%s, 'human_user', 'Test User', %s)",
        (principal_id, f"subject-{principal_id.hex}"),
    )
    conn.execute(
        "insert into namespaces(tenant_id, id, key, name, visibility) values (%s, %s, 'career', 'Career', 'private')",
        (tenant_id, namespace_id),
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            """
            insert into candidate_domain_facets(
              tenant_id, id, namespace_id, created_by, domain, experience_intent,
              claim_type, subject_type, subject_public_name, payload_digest,
              policy_version, retrieval_policy, raw_source_retention,
              publication_eligible, evidence_strength, sensitivity, ingest_enablement
            )
            values (
              %s, %s, %s, %s, 'career_private', 'company_experience', 'subjective_impression',
              'company', 'Example Inc',
              'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
              'policy-v0', 'explicit_or_contextual', 'none', false,
              'single_observation', 'medium', 'closed_launch_structured_only'
            )
            """,
            (tenant_id, uuid.uuid4(), namespace_id, principal_id),
        )
