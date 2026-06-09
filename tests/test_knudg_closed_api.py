import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from psycopg import sql
from jsonschema import Draft202012Validator

from scripts import knudg_closed_api as closed_api
from scripts.card_payload import canonical_digest_hex
from scripts.knudg_local_private import validate_local_private_card_v0


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"


def read_startup_line(process, timeout_seconds=5):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            return json.loads(line)
    raise AssertionError("closed API did not print a startup line")


def admin_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def db_url(name: str) -> str:
    parsed = urlparse(admin_url())
    return urlunparse(parsed._replace(path=f"/{name}"))


def maintenance_url() -> str:
    parsed = urlparse(admin_url())
    dbname = "postgres" if parsed.path not in ("", "/postgres") else "template1"
    return urlunparse(parsed._replace(path=f"/{dbname}"))


def api_role_url(url: str, password: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        parsed._replace(
            netloc=f"knudg_api_app:{password}@{parsed.hostname}:{parsed.port}",
        )
    )


def run_migrate(url: str, command: str = "up"):
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "migrate.py"), command],
        cwd=ROOT,
        env=env,
        check=True,
    )


def seed_closed_api_private_retention_proof(conn, tenant_id, namespace_id, principal_id, card_id, card_version_id):
    challenge_id = uuid.uuid4()
    handoff_id = uuid.uuid4()
    event_id = uuid.uuid4()
    consent_id = uuid.uuid4()
    event_stream_position = conn.execute("select nextval('event_stream_position_seq')").fetchone()[0]
    artifact_digest = conn.execute(
        "select payload_digest from card_versions where tenant_id = %s and id = %s",
        (tenant_id, card_version_id),
    ).fetchone()[0]
    policy_digest = "sha256:" + "b" * 64
    challenge_digest = "sha256:" + "e" * 64
    handoff_digest = "sha256:" + "f" * 64
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
          %s, 'closed-api-proof-event', 1, '{}'::jsonb, 'sha256:event-private-approved'
        )
        """,
        (tenant_id, card_id, event_id, event_stream_position, principal_id, card_version_id, uuid.uuid4()),
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
          %s, %s, 'closed-api-proof', now() + interval '5 minutes', %s
        )
        """,
        (
            tenant_id,
            challenge_id,
            principal_id,
            namespace_id,
            card_version_id,
            card_version_id,
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
          'closed-api-proof', now() + interval '5 minutes', %s
        )
        """,
        (
            tenant_id,
            handoff_id,
            challenge_id,
            principal_id,
            namespace_id,
            card_version_id,
            card_version_id,
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
            card_version_id,
            card_version_id,
            artifact_digest,
            policy_digest,
            challenge_id,
            challenge_digest,
            event_id,
        ),
    )
    return {
        "consent_id": str(consent_id),
        "handoff_id": str(handoff_id),
        "challenge_id": str(challenge_id),
        "card_id": str(card_id),
        "card_version_id": str(card_version_id),
        "artifact_digest": artifact_digest,
        "policy_version": "private-retention-v1",
        "policy_digest": policy_digest,
        "challenge_digest": challenge_digest,
        "handoff_digest": handoff_digest,
    }


@pytest.fixture(scope="module")
def migrated_db():
    name = f"knudg_closed_api_test_{uuid.uuid4().hex}"
    try:
        with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not reachable for closed API DB tests: {exc}")
    url = db_url(name)
    run_migrate(url, "up")
    yield url
    with psycopg.connect(maintenance_url(), autocommit=True, connect_timeout=3) as conn:
        conn.execute(
            "select pg_terminate_backend(pid) from pg_stat_activity where datname = %s",
            (name,),
        )
        conn.execute(sql.SQL("drop database if exists {}").format(sql.Identifier(name)))


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def post_json(url):
    request = urllib.request.Request(url, data=b"{}", headers={"content-type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    raise AssertionError("closed POST route should not return success")


def post_publish(url, payload, token=None, digest=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    if digest:
        headers["x-knudg-artifact-digest"] = digest
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def post_private(url, payload, token="test-token"):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class MockNvidiaResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, *args):
        return json.dumps(self.payload).encode("utf-8")


def sample_final_filter_candidate():
    return {
        "schema_version": "closed-publication-candidate-v0",
        "candidate_state": "publication_ready_candidate",
        "human_summary": {
            "content": "Use a bounded schema validator before storing reusable agent knowledge.",
            "redaction_summary": "No private identifiers or raw logs included.",
        },
        "source_policy": {
            "domain": "technical_work",
            "visibility": "private_candidate",
        },
    }


def test_final_filter_without_nvidia_key_fails_closed(monkeypatch):
    monkeypatch.delenv("KNUDG_NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NGC_API_KEY", raising=False)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["schema_version"] == "final-filter-result-v0"
    assert result["verdict"] == "hold"
    assert result["decision_label"] == "hold"
    assert result["risk_reasons"] == ["llm_provider_unconfigured"]
    assert result["provider"] == "none"
    assert result["llm_called"] is False
    assert result["fail_closed"] is True
    assert result["automated_repair_required"] is True
    assert result["hold_repair_policy"]["parallel_reviewer_count"] == 3
    assert result["public_publication_enabled"] is False


def test_final_filter_deterministic_secret_block_does_not_call_llm(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("deterministic preflight should not call NVIDIA")

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", fail_urlopen)
    candidate = sample_final_filter_candidate()
    candidate["human_summary"]["content"] = "Do not publish " + "sk-" + "abcdefghijklmnopqrstuvwxyz123456."

    result = closed_api.evaluate_final_filter({"candidate": candidate})

    assert result["verdict"] == "reject"
    assert result["risk_level"] == "critical"
    assert result["risk_reasons"] == ["secret"]
    assert result["provider"] == "rules"
    assert result["llm_called"] is False


def test_final_filter_uses_glm_5_1_and_validates_json(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("KNUDG_FINAL_FILTER_NVIDIA_MODEL", raising=False)

    def mock_urlopen(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        assert request.full_url == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert body["model"] == "z-ai/glm-5.1"
        assert body["temperature"] == 0
        assert body["stream"] is False
        assert body["guided_json"]["required"] == [
            "verdict",
            "risk_level",
            "risk_reasons",
            "required_redactions",
            "public_safe_summary",
            "operator_note",
        ]
        assert "response_format" not in body
        prompt = json.loads(body["messages"][1]["content"])
        assert "surface_contracts" not in prompt["policy_context"]
        assert prompt["policy_context"]["surface_contracts_present"] is False
        assert prompt["candidate"]["human_summary"]["content"] == sample_final_filter_candidate()["human_summary"]["content"]
        assert timeout >= 1
        return MockNvidiaResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "pass",
                                    "risk_level": "low",
                                    "risk_reasons": [],
                                    "required_redactions": [],
                                    "public_safe_summary": "Technical schema-validation guidance.",
                                    "operator_note": "Low-risk technical candidate.",
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["verdict"] == "pass"
    assert result["decision_label"] == "clear_ok"
    assert result["risk_level"] == "low"
    assert result["provider"] == "nvidia"
    assert result["model"] == "z-ai/glm-5.1"
    assert result["llm_called"] is True
    assert result["fail_closed"] is False
    assert result["final_publication_completion_enabled"] is False


def test_final_filter_accepts_compact_glm_pass_result(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    def mock_urlopen(request, timeout):
        return MockNvidiaResponse({"choices": [{"message": {"content": "```json\n{\"filter_result\":\"pass\"}\n```"}}]})

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["verdict"] == "pass"
    assert result["decision_label"] == "clear_ok"
    assert result["risk_level"] == "low"
    assert result["provider"] == "nvidia"
    assert result["llm_called"] is True


def test_final_filter_maps_legacy_allow_and_quarantine_labels_to_three_way_verdicts(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    responses = iter(
        [
            {"choices": [{"message": {"content": json.dumps({"verdict": "allow", "risk_level": "low"})}}]},
            {"choices": [{"message": {"content": json.dumps({"verdict": "quarantine", "risk_level": "high"})}}]},
        ]
    )

    def mock_urlopen(request, timeout):
        return MockNvidiaResponse(next(responses))

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    pass_result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})
    review_result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert pass_result["verdict"] == "pass"
    assert pass_result["decision_label"] == "clear_ok"
    assert pass_result["fail_closed"] is False
    assert review_result["verdict"] == "hold"
    assert review_result["decision_label"] == "hold"
    assert review_result["automated_repair_required"] is True
    assert review_result["hold_repair_policy"]["writer_input"] == "ng_points_only"


def test_final_filter_normalizes_verbose_model_reason_fields(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    def mock_urlopen(request, timeout):
        return MockNvidiaResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "hold",
                                    "risk_level": "medium",
                                    "risk_reasons": [
                                        "This candidate mentions public-candidate conversion and should receive manual policy review before any publication action."
                                    ],
                                    "required_redactions": [
                                        {
                                            "field": "candidate.operator_note",
                                            "reason": "x" * 250,
                                        }
                                    ],
                                    "public_safe_summary": "Technical schema-validation guidance.",
                                    "operator_note": "y" * 500,
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["verdict"] == "hold"
    assert result["decision_label"] == "hold"
    assert result["risk_reasons"] == ["this_candidate_mentions_public_candidate_conversion_and_should_receive_manual_po"]
    assert len(result["required_redactions"][0]["reason"]) == 200
    assert len(result["operator_note"]) == 300


def test_final_filter_invalid_glm_response_holds_for_repair_loop(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    def mock_urlopen(request, timeout):
        return MockNvidiaResponse({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["verdict"] == "hold"
    assert result["risk_reasons"] == ["llm_provider_error"]
    assert result["provider"] == "nvidia"
    assert result["llm_called"] is True
    assert result["automated_repair_required"] is True


def test_final_filter_polls_pending_nvidia_result(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("KNUDG_NVIDIA_STATUS_BASE_URL", "https://integrate.api.nvidia.com/v1/status")
    calls = []

    def mock_urlopen(request, timeout):
        calls.append(request.full_url)
        if request.get_method() == "POST":
            return MockNvidiaResponse({"requestId": "11111111-1111-4111-8111-111111111111"}, status=202)
        return MockNvidiaResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "pass",
                                    "risk_level": "low",
                                    "risk_reasons": [],
                                    "required_redactions": [],
                                    "public_safe_summary": "Technical schema-validation guidance.",
                                    "operator_note": "Low-risk technical candidate.",
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)
    monkeypatch.setattr(closed_api.time, "sleep", lambda seconds: None)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["verdict"] == "pass"
    assert calls == [
        "https://integrate.api.nvidia.com/v1/chat/completions",
        "https://integrate.api.nvidia.com/v1/status/11111111-1111-4111-8111-111111111111",
    ]


def test_final_filter_queue_is_idempotent_and_worker_completes(migrated_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_db)
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("KNUDG_FINAL_FILTER_QUEUE_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY", "2")

    class NoopLimiter:
        def acquire(self):
            return None

    def mock_urlopen(request, timeout):
        return MockNvidiaResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "pass",
                                    "risk_level": "low",
                                    "risk_reasons": [],
                                    "required_redactions": [],
                                    "public_safe_summary": "Technical schema-validation guidance.",
                                    "operator_note": "Low-risk technical candidate.",
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(closed_api, "nvidia_start_rate_limiter", lambda: NoopLimiter())
    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    policy_context = {
        "check_stage": "publication_candidate_final_filter",
        "visibility_target": "public_candidate",
        "ad_or_spam_assessment_required": True,
    }
    first = closed_api.enqueue_or_evaluate_final_filter(sample_final_filter_candidate(), policy_context)
    replay = closed_api.enqueue_or_evaluate_final_filter(sample_final_filter_candidate(), policy_context)

    assert first["verdict"] == "hold"
    assert first["queued"] is True
    assert first["queue_status"] == "queued"
    assert first["max_queries_per_minute"] == 40.0
    assert replay["final_filter_job_id"] == first["final_filter_job_id"]

    row = closed_api.claim_final_filter_job()
    assert str(row["id"]) == first["final_filter_job_id"]
    closed_api.process_final_filter_job(row)
    completed = closed_api.read_final_filter_job(first["final_filter_job_id"])

    assert completed["verdict"] == "pass"
    assert completed["queued"] is False
    assert completed["queue_status"] == "succeeded"
    assert completed["llm_called"] is True
    with psycopg.connect(migrated_db, connect_timeout=3) as conn:
        stored = conn.execute("select status, attempts from final_filter_jobs where id = %s", (first["final_filter_job_id"],)).fetchone()
    assert stored == ("succeeded", 1)


def test_final_filter_queue_stats_do_not_select_body_columns(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.example/knudg")
    monkeypatch.setenv("KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY", "37")
    captured_queries = []

    class FakeCursor:
        def execute(self, query):
            captured_queries.append(query)
            return self

        def fetchone(self):
            return {
                "total_jobs": 1500,
                "queued_jobs": 31,
                "ready_queued_jobs": 30,
                "delayed_queued_jobs": 1,
                "leased_jobs": 6,
                "expired_leases": 2,
                "succeeded_jobs": 1463,
                "dead_jobs": 0,
                "attempted_jobs": 1469,
                "attempts_total": 1488,
                "max_attempts_seen": 3,
                "oldest_queued_age_seconds": 900,
                "oldest_ready_queued_age_seconds": 800,
                "oldest_expired_lease_age_seconds": 60,
                "newest_succeeded_age_seconds": 4,
            }

    class FakeConnection:
        def __enter__(self):
            return FakeCursor()

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_connect(url, row_factory=None, connect_timeout=None):
        assert url == "postgresql://db.example/knudg"
        assert row_factory is not None
        assert connect_timeout == 3
        return FakeConnection()

    monkeypatch.setattr(psycopg, "connect", fake_connect)

    stats = closed_api.final_filter_queue_stats()

    select_sql = captured_queries[0].lower().split("from final_filter_jobs", maxsplit=1)[0]
    assert "candidate_json" not in select_sql
    assert "result_json" not in select_sql
    assert stats["total_jobs"] == 1500
    assert stats["active_depth"] == 37
    assert stats["status_counts"] == {"queued": 31, "leased": 6, "succeeded": 1463, "dead": 0}
    assert stats["ready_queued_jobs"] == 30
    assert stats["delayed_queued_jobs"] == 1
    assert stats["expired_leases"] == 2
    assert stats["candidate_bodies_included"] is False
    assert stats["result_bodies_included"] is False
    assert stats["configuration"]["worker_concurrency"] == 37


def test_final_filter_queue_stats_are_aggregate_only(migrated_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", migrated_db)
    monkeypatch.setenv("KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY", "7")
    canary = "CANARY_FINAL_FILTER_STATS_DO_NOT_ECHO"

    def digest(label):
        return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()

    candidate = {"human_summary": {"content": canary}, "label": "stats fixture"}
    policy_context = {"visibility_target": "public_candidate"}
    result = {"operator_note": canary, "verdict": "pass"}
    rows = [
        ("queued-ready", "queued", 0, "now() - interval '5 minutes'", "null", "null", "null"),
        ("queued-delayed", "queued", 1, "now() + interval '2 minutes'", "null", "null", "null"),
        ("leased-active", "leased", 1, "now() - interval '4 minutes'", "now() + interval '2 minutes'", "null", "null"),
        ("leased-expired", "leased", 2, "now() - interval '6 minutes'", "now() - interval '1 minute'", "null", "null"),
        ("succeeded", "succeeded", 1, "now() - interval '7 minutes'", "null", "now() - interval '10 seconds'", "%s::jsonb"),
        ("dead", "dead", 3, "now() - interval '8 minutes'", "null", "null", "null"),
    ]

    with psycopg.connect(migrated_db, connect_timeout=3) as conn:
        conn.execute("truncate final_filter_jobs")
        for label, status, attempts, available_at, leased_until, completed_at, result_sql in rows:
            conn.execute(
                f"""
                insert into final_filter_jobs(
                  id, request_digest, status, candidate_json, policy_context_json, result_json,
                  attempts, available_at, leased_until, completed_at
                )
                values (
                  %s, %s, %s, %s::jsonb, %s::jsonb, {result_sql},
                  %s, {available_at}, {leased_until}, {completed_at}
                )
                """,
                (
                    str(uuid.uuid4()),
                    digest(label),
                    status,
                    json.dumps(candidate),
                    json.dumps(policy_context),
                    json.dumps(result),
                    attempts,
                )
                if result_sql != "null"
                else (
                    str(uuid.uuid4()),
                    digest(label),
                    status,
                    json.dumps(candidate),
                    json.dumps(policy_context),
                    attempts,
                ),
            )

    stats = closed_api.final_filter_queue_stats()

    assert stats["schema_version"] == "final-filter-queue-stats-v0"
    assert stats["total_jobs"] == 6
    assert stats["active_depth"] == 4
    assert stats["status_counts"] == {"queued": 2, "leased": 2, "succeeded": 1, "dead": 1}
    assert stats["ready_queued_jobs"] == 1
    assert stats["delayed_queued_jobs"] == 1
    assert stats["expired_leases"] == 1
    assert stats["attempted_jobs"] == 5
    assert stats["attempts_total"] == 8
    assert stats["max_attempts_seen"] == 3
    assert stats["configuration"]["worker_concurrency"] == 7
    assert stats["candidate_bodies_included"] is False
    assert stats["result_bodies_included"] is False
    serialized = json.dumps(stats)
    assert canary not in serialized
    assert "candidate_json" not in serialized
    assert "result_json" not in serialized
    assert stats["age_seconds"]["oldest_queued"] is not None
    assert stats["age_seconds"]["oldest_ready_queued"] is not None
    assert stats["age_seconds"]["oldest_expired_lease"] is not None
    assert stats["age_seconds"]["newest_succeeded"] is not None


def test_closed_api_final_filter_queue_stats_endpoint_requires_auth_and_hides_bodies(migrated_db):
    canary = "CANARY_FINAL_FILTER_STATS_ENDPOINT_DO_NOT_ECHO"
    with psycopg.connect(migrated_db, connect_timeout=3) as conn:
        conn.execute("truncate final_filter_jobs")
        conn.execute(
            """
            insert into final_filter_jobs(
              id, request_digest, status, candidate_json, policy_context_json, attempts, available_at
            )
            values (%s, %s, 'queued', %s::jsonb, %s::jsonb, 0, now() - interval '3 minutes')
            """,
            (
                str(uuid.uuid4()),
                "sha256:" + hashlib.sha256(b"endpoint-stats").hexdigest(),
                json.dumps({"human_summary": {"content": canary}}),
                json.dumps({"visibility_target": "public_candidate"}),
            ),
        )

    env = {**os.environ}
    env["DATABASE_URL"] = migrated_db
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    env.pop("KNUDG_NVIDIA_API_KEY", None)
    env.pop("NVIDIA_API_KEY", None)
    env.pop("NGC_API_KEY", None)
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"

        status, unauthorized = post_private(f"{base_url}/v1/private/final-filter/jobs:stats", {}, token=None)
        assert status == 401
        assert unauthorized["status"] == "unauthorized"

        status, payload = post_private(f"{base_url}/v1/private/final-filter/jobs:stats", {}, token="test-token")
        assert status == 200
        assert payload["status"] == "final_filter_queue_stats"
        assert payload["stats"]["total_jobs"] == 1
        assert payload["stats"]["status_counts"]["queued"] == 1
        assert payload["stats"]["ready_queued_jobs"] == 1
        assert payload["stats"]["candidate_bodies_included"] is False
        assert payload["stats"]["result_bodies_included"] is False
    finally:
        stop_process(process)

    serialized = json.dumps(payload)
    assert canary not in serialized
    assert "candidate_json" not in serialized
    assert "result_json" not in serialized
    assert canary not in process.stdout.read()
    assert canary not in process.stderr.read()


def test_final_filter_rpm_is_capped_at_nvidia_limit(monkeypatch):
    monkeypatch.setenv("KNUDG_FINAL_FILTER_NVIDIA_RPM", "200")

    assert closed_api.final_filter_nvidia_rpm() == 40.0


def test_final_filter_timeout_defaults_to_ten_minutes_and_derives_queue_width(monkeypatch):
    monkeypatch.delenv("KNUDG_FINAL_FILTER_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("KNUDG_FINAL_FILTER_NVIDIA_RPM", raising=False)
    monkeypatch.delenv("KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY", raising=False)

    assert closed_api.nvidia_final_filter_timeout_seconds() == 600.0
    assert closed_api.final_filter_queue_worker_concurrency() == 400


def test_final_filter_timeout_and_queue_width_are_capped(monkeypatch):
    monkeypatch.setenv("KNUDG_FINAL_FILTER_TIMEOUT_SECONDS", "1200")
    monkeypatch.setenv("KNUDG_FINAL_FILTER_QUEUE_WORKER_CONCURRENCY", "999")

    assert closed_api.nvidia_final_filter_timeout_seconds() == 600.0
    assert closed_api.final_filter_queue_worker_concurrency() == 480


def test_local_private_merge_candidates_recommend_existing_update(monkeypatch):
    card = validate_local_private_card_v0(json.loads((ROOT / "fixtures" / "local-private-card.sample.json").read_text(encoding="utf-8")))

    def mock_search(task_profile, *, workspace_id, limit, min_score, latency_budget_ms):
        assert task_profile["schema_version"] == "task_profile.v0"
        assert "retrieval_domains" not in task_profile
        assert workspace_id == "closed-beta-test"
        assert limit == 3
        assert min_score == 2
        return {
            "decision": "cards_found",
            "served_from": "closed_private_exact_fts",
            "cards": [
                {
                    "card_id": "11111111-1111-4111-8111-111111111111",
                    "card_version_id": "22222222-2222-4222-8222-222222222222",
                    "match_score": 4,
                }
            ],
        }

    monkeypatch.setattr(closed_api, "search_private_cards", mock_search)

    result = closed_api.local_private_merge_candidates(card, "closed-beta-test")

    assert result["schema_version"] == "local-private-merge-candidates-v0"
    assert result["recommended_action"] == "update_existing"
    assert result["cards"][0]["card_id"] == "11111111-1111-4111-8111-111111111111"


def test_publish_merge_request_requires_explicit_update_or_create_new():
    implicit_update = closed_api.normalize_publish_merge_request(
        {"target_card_id": "11111111-1111-4111-8111-111111111111"}
    )
    create_new = closed_api.normalize_publish_merge_request({"decision": "create_new", "reason": "not the same logical card"})

    assert implicit_update["decision"] == "update_existing"
    assert implicit_update["target_card_id"] == "11111111-1111-4111-8111-111111111111"
    assert create_new["decision"] == "create_new"
    assert create_new["target_card_id"] is None
    with pytest.raises(ValueError):
        closed_api.normalize_publish_merge_request({"decision": "update_existing"})
    with pytest.raises(ValueError):
        closed_api.normalize_publish_merge_request({"decision": "create_new", "target_card_id": "11111111-1111-4111-8111-111111111111"})


def test_closed_api_final_filter_route_requires_operator_and_fails_closed_without_key():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env.pop("KNUDG_OPERATOR_TOKEN", None)
    env.pop("KNUDG_DISTRIBUTION_TOKEN", None)
    env.pop("KNUDG_ADDITIONAL_OPERATOR_TOKENS", None)
    env.pop("KNUDG_NVIDIA_API_KEY", None)
    env.pop("NVIDIA_API_KEY", None)
    env.pop("NGC_API_KEY", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"

        status, unauthorized = post_private(
            f"{base_url}/v1/private/final-filter:evaluate",
            {"candidate": sample_final_filter_candidate()},
            token=None,
        )
        assert status == 401
        assert unauthorized["status"] == "unauthorized"

        status, evaluated = post_private(
            f"{base_url}/v1/private/final-filter:evaluate",
            {"candidate": sample_final_filter_candidate()},
            token="test-token",
        )
        assert status == 200
        assert evaluated["status"] == "final_filter_evaluated"
        assert evaluated["verdict"] == "hold"
        assert evaluated["risk_reasons"] == ["llm_provider_unconfigured"]
        assert evaluated["public_publication_enabled"] is False
    finally:
        stop_process(process)


def test_closed_api_rejects_distribution_token_without_primary_operator_token():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env.pop("KNUDG_OPERATOR_TOKEN", None)
    env.pop("KNUDG_ADDITIONAL_OPERATOR_TOKENS", None)
    env.pop("KNUDG_NVIDIA_API_KEY", None)
    env.pop("NVIDIA_API_KEY", None)
    env.pop("NGC_API_KEY", None)
    env["KNUDG_DISTRIBUTION_TOKEN"] = "distribution-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"

        status, forbidden = post_private(
            f"{base_url}/v1/private/final-filter:evaluate",
            {"candidate": sample_final_filter_candidate()},
            token="wrong-token",
        )
        assert status == 503
        assert forbidden["status"] == "forbidden"
        assert forbidden["detail"] == "operator token is not configured"

        status, evaluated = post_private(
            f"{base_url}/v1/private/final-filter:evaluate",
            {"candidate": sample_final_filter_candidate()},
            token="distribution-token",
        )
        assert status == 503
        assert evaluated["status"] == "forbidden"
        assert evaluated["detail"] == "operator token is not configured"
    finally:
        stop_process(process)


def test_closed_api_rejects_distribution_token_for_private_routes_when_operator_token_exists():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env.pop("KNUDG_ADDITIONAL_OPERATOR_TOKENS", None)
    env.pop("KNUDG_NVIDIA_API_KEY", None)
    env.pop("NVIDIA_API_KEY", None)
    env.pop("NGC_API_KEY", None)
    env["KNUDG_OPERATOR_TOKEN"] = "operator-token"
    env["KNUDG_DISTRIBUTION_TOKEN"] = "distribution-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"

        status, forbidden = post_private(
            f"{base_url}/v1/private/final-filter:evaluate",
            {"candidate": sample_final_filter_candidate()},
            token="distribution-token",
        )
        assert status == 403
        assert forbidden["status"] == "forbidden"

        status, evaluated = post_private(
            f"{base_url}/v1/private/final-filter:evaluate",
            {"candidate": sample_final_filter_candidate()},
            token="operator-token",
        )
        assert status == 200
        assert evaluated["status"] == "final_filter_evaluated"
        assert evaluated["verdict"] == "hold"
    finally:
        stop_process(process)


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_closed_api_fails_closed_without_database():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env.pop("KNUDG_OPERATOR_TOKEN", None)
    env.pop("KNUDG_DISTRIBUTION_TOKEN", None)
    env.pop("KNUDG_ADDITIONAL_OPERATOR_TOKENS", None)
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        assert startup["status"] == "listening"
        base_url = f"http://127.0.0.1:{startup['port']}"

        status, live = get_json(f"{base_url}/health/live")
        assert status == 200
        assert live["launch_state"] == "closed"
        assert live["route_classes"]["search"] == "disabled"
        assert live["route_classes"]["submit/write"] == "disabled"

        try:
            get_json(f"{base_url}/health/ready")
        except urllib.error.HTTPError as exc:
            ready = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 503
        else:
            raise AssertionError("ready should fail when DATABASE_URL is absent")
        assert ready["components"]["postgres"] == "not_configured"

        status, capabilities = get_json(f"{base_url}/capabilities")
        assert status == 200
        assert capabilities["deployment_type"] == "greencloud_closed_launch"
        assert capabilities["features"]["search"] is False
        assert capabilities["features"]["publication"] is False
        assert capabilities["features"]["write"] is False

        status, closed = post_json(f"{base_url}/v1/search")
        assert status == 404
        assert closed["status"] == "closed"
    finally:
        stop_process(process)


def test_closed_api_unknown_get_route_does_not_echo_path_query_or_access_log_canary():
    canary = "CANARY_DO_NOT_ECHO_ROUTE"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        try:
            get_json(f"{base_url}/v1/unknown/{canary}?raw=C:%5CUsers%5C4%5Cprivate%5Crepo")
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 404
        else:
            raise AssertionError("unknown route should return 404")
        assert body == {"status": "not_found"}
    finally:
        stop_process(process)
    stderr = process.stderr.read()
    assert canary not in json.dumps(body)
    assert canary not in stderr
    assert "Users" not in json.dumps(body)
    assert "private" not in stderr


def test_closed_api_structured_access_log_tracks_source_and_activity_without_token_or_body():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env.pop("KNUDG_OPERATOR_TOKEN", None)
    env.pop("KNUDG_ADDITIONAL_OPERATOR_TOKENS", None)
    env.pop("KNUDG_NVIDIA_API_KEY", None)
    env.pop("NVIDIA_API_KEY", None)
    env.pop("NGC_API_KEY", None)
    env["KNUDG_OPERATOR_TOKEN"] = "operator-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        request = urllib.request.Request(
            f"{base_url}/v1/private/final-filter:evaluate",
            data=json.dumps({"candidate": sample_final_filter_candidate()}).encode("utf-8"),
            headers={
                "authorization": "Bearer operator-token",
                "content-type": "application/json",
                "origin": "http://127.0.0.1:8790",
                "user-agent": "knudg-test-agent/1.0",
                "x-forwarded-for": "203.0.113.10",
                "x-forwarded-host": "api.knudg.com",
                "x-forwarded-proto": "https",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert response.headers["x-knudg-request-id"]
            response.read()
    finally:
        stop_process(process)

    stderr = process.stderr.read()
    events = [json.loads(line) for line in stderr.splitlines() if line.strip()]
    access = next(event for event in events if event.get("event") == "http_access")

    assert access["route"] == "private_final_filter_evaluate"
    assert access["status"] == 200
    assert access["auth_token_class"] == "primary"
    assert access["authorization_present"] is True
    assert access["forwarded_for"] == "203.0.113.10"
    assert access["forwarded_host"] == "api.knudg.com"
    assert access["forwarded_proto"] == "https"
    assert access["origin_host"] == "127.0.0.1"
    assert access["user_agent_digest"].startswith("sha256:")
    assert "operator-token" not in stderr
    assert "Bearer" not in stderr
    assert "Technical schema-validation guidance" not in stderr


def test_closed_api_private_publish_requires_token_and_digest_before_storage():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    env["KNUDG_PRIVATE_TENANT_ID"] = "11111111-1111-4111-8111-111111111111"
    env["KNUDG_PRIVATE_NAMESPACE_ID"] = "22222222-2222-4222-8222-222222222222"
    env["KNUDG_PRIVATE_PRINCIPAL_ID"] = "33333333-3333-4333-8333-333333333333"
    env["KNUDG_PRIVATE_TENANT_ID"] = "11111111-1111-4111-8111-111111111111"
    env["KNUDG_PRIVATE_NAMESPACE_ID"] = "22222222-2222-4222-8222-222222222222"
    env["KNUDG_PRIVATE_PRINCIPAL_ID"] = "33333333-3333-4333-8333-333333333333"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        card = validate_local_private_card_v0(json.loads((ROOT / "fixtures" / "local-private-card.sample.json").read_text(encoding="utf-8")))
        digest = canonical_digest_hex(card)

        status, capabilities = get_json(f"{base_url}/capabilities")
        assert status == 200
        assert capabilities["features"]["operator_private_publish"] is True
        assert capabilities["features"]["operator_private_trusted_completion"] is True
        assert capabilities["features"]["publication"] is False

        status, unauthorized = post_publish(f"{base_url}/v1/private/cards:publish", {"card": card})
        assert status == 401
        assert unauthorized["status"] == "unauthorized"

        status, approval = post_publish(f"{base_url}/v1/private/cards:publish", {"card": card}, token="test-token")
        assert status == 409
        assert approval["status"] == "approval_required"
        assert approval["artifact_digest"] == digest
        assert approval["stored"] is False
        assert approval["public_publication_enabled"] is False

        status, unavailable = post_publish(
            f"{base_url}/v1/private/cards:publish",
            {"card": card},
            token="test-token",
            digest=digest,
        )
        assert status == 503
        assert unavailable["status"] == "unavailable"
        assert unavailable["stored"] is False
    finally:
        stop_process(process)


def test_closed_api_private_publish_rejects_raw_card_without_echoing_canary():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        canary = "CANARY_DO_NOT_ECHO_789"
        raw_card = validate_local_private_card_v0(
            json.loads((ROOT / "fixtures" / "local-private-card.sample.json").read_text(encoding="utf-8"))
        )
        raw_card["solution_summary"] = f"The rejected secret token {canary} lived under C:\\Users\\redacted\\private\\repo."
        status, rejected = post_publish(f"{base_url}/v1/private/cards:publish", {"card": raw_card}, token="test-token")
        assert status == 400
        assert rejected == {"status": "rejected", "stored": False, "reject_class": "local_private_card"}
    finally:
        stop_process(process)
    serialized = json.dumps(rejected)
    assert canary not in serialized
    assert "Users" not in serialized
    assert canary not in process.stdout.read()
    assert canary not in process.stderr.read()


def test_closed_api_private_search_rejects_raw_profile_without_echoing_canary():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        canary = "CANARY_SEARCH_PROFILE_DO_NOT_ECHO"
        status, rejected = post_private(
            f"{base_url}/v1/private/search",
            {
                "workspace": "closed-beta-test",
                "task_profile": {
                    "schema_version": "task_profile.v0",
                    "intent": "debug",
                    "explicit_query": f"raw secret token {canary} at C:\\Users\\redacted\\private",
                    "repo_shape_category": "pytest-postgres",
                    "public_packages": ["psycopg"],
                    "error_fingerprints": [canary],
                    "coarse_os": "windows",
                    "recent_event_kinds": ["task_start"],
                },
            },
            token="test-token",
        )
        assert status == 400
        assert rejected == {"status": "rejected", "reject_class": "task_profile"}
    finally:
        stop_process(process)
    serialized = json.dumps(rejected)
    assert canary not in serialized
    assert "Users" not in serialized
    assert canary not in process.stdout.read()
    assert canary not in process.stderr.read()


def test_closed_api_private_search_rejects_non_technical_retrieval_domain_without_echoing():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        status, rejected = post_private(
            f"{base_url}/v1/private/search",
            {
                "workspace": "closed-beta-test",
                "task_profile": {
                    "schema_version": "task_profile.v0",
                    "intent": "debug",
                    "explicit_query": "agent facing orchestration",
                    "repo_shape_category": "python-cli",
                    "retrieval_domains": ["career_private"],
                    "recent_event_kinds": ["task_start"],
                },
            },
            token="test-token",
        )
        assert status == 400
        assert rejected == {"status": "rejected", "reject_class": "task_profile"}
    finally:
        stop_process(process)


def test_closed_api_redacted_experience_storage_rejects_raw_record_without_echoing_canary():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        canary = "CANARY_EXPERIENCE_RECORD_DO_NOT_ECHO"
        record = json.loads((ROOT / "fixtures" / "experience-storage-record.career-private.redacted.json").read_text(encoding="utf-8"))
        record["redacted_experience"]["summary"] = f"Raw marker {canary} user@example.com should be rejected."
        status, rejected = post_private(
            f"{base_url}/v1/private/experience-records:store",
            {"workspace": "closed-beta-test", "record": record},
            token="test-token",
        )
        assert status == 400
        assert rejected == {"status": "rejected", "stored": False, "reject_class": "redacted_experience_record"}
    finally:
        stop_process(process)
    serialized = json.dumps(rejected)
    assert canary not in serialized
    assert canary not in process.stdout.read()
    assert canary not in process.stderr.read()


def test_closed_api_private_retention_completion_requires_confirmations_without_echoing_canary():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        canary = "CANARY_COMPLETION_DO_NOT_ECHO"
        status, rejected = post_private(
            f"{base_url}/v1/private/approval-handoffs/11111111-1111-4111-8111-111111111111:complete-private-retention",
            {
                "workspace": "closed-beta-test",
                "idempotency_key": f"bad-{canary}",
                "comprehension_confirmed": False,
                "private_retention_scope_confirmed": True,
                "no_publication_confirmed": True,
            },
            token="test-token",
        )
        assert status == 400
        assert rejected == {"status": "rejected", "reject_class": "private_retention_completion"}
    finally:
        stop_process(process)
    serialized = json.dumps(rejected)
    assert canary not in serialized
    assert canary not in process.stdout.read()
    assert canary not in process.stderr.read()


def test_closed_api_private_search_revoke_purge_loop(migrated_db):
    tenant_id = "11111111-1111-4111-8111-111111111111"
    namespace_id = "22222222-2222-4222-8222-222222222222"
    principal_id = "33333333-3333-4333-8333-333333333333"
    api_password = "knudg_api_app_test"
    api_url = api_role_url(migrated_db, api_password)
    with psycopg.connect(migrated_db, autocommit=True, connect_timeout=3) as conn:
        conn.execute(sql.SQL("alter role knudg_api_app login password {}").format(sql.Literal(api_password)))
        conn.execute(
            """
            insert into knudg_private.closed_api_runtime_bindings(
              tenant_id, namespace_id, principal_id, tenant_slug, namespace_key
            )
            values (%s, %s, %s, 'knudg-closed-private', 'closed-private')
            on conflict (tenant_id, namespace_id, principal_id) do update
            set tenant_slug = excluded.tenant_slug,
                namespace_key = excluded.namespace_key,
                enabled = true,
                updated_at = now()
            """,
            (tenant_id, namespace_id, principal_id),
        )

    env = {**os.environ}
    env["DATABASE_URL"] = api_url
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
    env["KNUDG_PRIVATE_TENANT_ID"] = tenant_id
    env["KNUDG_PRIVATE_NAMESPACE_ID"] = namespace_id
    env["KNUDG_PRIVATE_PRINCIPAL_ID"] = principal_id
    env.pop("KNUDG_NVIDIA_API_KEY", None)
    env.pop("NVIDIA_API_KEY", None)
    env.pop("NGC_API_KEY", None)
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        card = validate_local_private_card_v0(json.loads((ROOT / "fixtures" / "local-private-card.sample.json").read_text(encoding="utf-8")))
        digest = canonical_digest_hex(card)
        task_profile = json.loads((ROOT / "fixtures" / "local-private-task-profile.sample.json").read_text(encoding="utf-8"))
        experience_record = json.loads((ROOT / "fixtures" / "experience-storage-record.career-private.redacted.json").read_text(encoding="utf-8"))

        status, ready = get_json(f"{base_url}/health/ready")
        assert status == 200
        assert ready["status"] == "ready"

        status, published = post_publish(
            f"{base_url}/v1/private/cards:publish",
            {"workspace": "closed-beta-test", "card": card},
            token="test-token",
            digest=digest,
        )
        assert status == 201
        assert published["status"] == "private_published"
        card_id = published["card_id"]
        first_version_id = published["card_version_id"]

        updated_card = dict(card)
        updated_card["title"] = "Psycopg migration capture path update"
        updated_card["solution_summary"] = (
            card["solution_summary"]
            + " Later attempts should update this same logical Knudg when the old note was not directly usable."
        )
        updated_card["lessons"] = [
            *card["lessons"],
            "Use merge update when a similar Knudg was relevant but not directly usable.",
        ]
        updated_digest = canonical_digest_hex(updated_card)
        status, merge_approval = post_publish(
            f"{base_url}/v1/private/cards:publish",
            {"workspace": "closed-beta-test", "card": updated_card},
            token="test-token",
        )
        assert status == 409
        assert merge_approval["status"] == "approval_required"
        assert merge_approval["merge_candidates"]["recommended_action"] == "update_existing"
        assert merge_approval["merge_candidates"]["cards"][0]["card_id"] == card_id

        status, merge_required = post_publish(
            f"{base_url}/v1/private/cards:publish",
            {"workspace": "closed-beta-test", "card": updated_card},
            token="test-token",
            digest=updated_digest,
        )
        assert status == 409
        assert merge_required["status"] == "merge_required"
        assert merge_required["stored"] is False

        status, updated = post_publish(
            f"{base_url}/v1/private/cards:publish",
            {
                "workspace": "closed-beta-test",
                "card": updated_card,
                "merge": {
                    "decision": "update_existing",
                    "target_card_id": card_id,
                    "reason": "same logical Knudg needed updated applicability limits",
                },
            },
            token="test-token",
            digest=updated_digest,
        )
        assert status == 200
        assert updated["status"] == "private_card_updated"
        assert updated["stored"] is True
        assert updated["card_id"] == card_id
        assert updated["previous_card_version_id"] == first_version_id
        assert updated["card_version_id"] != first_version_id
        assert updated["version_number"] == 2
        assert updated["merge_update"]["result"] == "version_created"
        assert updated["merge_update"]["created_new_card"] is False
        published = updated
        card = updated_card

        with psycopg.connect(migrated_db, connect_timeout=3) as conn:
            assert conn.execute("select count(*) from experience_cards").fetchone()[0] == 1
            assert conn.execute("select count(*) from card_versions where card_id = %s", (card_id,)).fetchone()[0] == 2
            assert conn.execute(
                "select count(*) from card_edges where source_card_version_id = %s and target_card_version_id = %s and edge_type = 'supersedes'",
                (published["card_version_id"], first_version_id),
            ).fetchone()[0] == 1
            assert conn.execute(
                "select lifecycle_status from local_private_search_documents where card_version_id = %s",
                (first_version_id,),
            ).fetchone()[0] == "revoked"
            consent_proof = seed_closed_api_private_retention_proof(
                conn,
                tenant_id,
                namespace_id,
                principal_id,
                published["card_id"],
                published["card_version_id"],
            )
        experience_record["consent"]["private_retention_consent_proof"] = consent_proof
        experience_record["source_controls"]["source_digest"] = "sha256:" + consent_proof["artifact_digest"].removeprefix("sha256:")

        status, stored_experience = post_private(
            f"{base_url}/v1/private/experience-records:store",
            {"workspace": "closed-beta-test", "record": experience_record},
        )
        assert status == 201
        assert stored_experience["status"] == "redacted_experience_stored"
        assert stored_experience["stored"] is True
        assert stored_experience["private_retention_proof_bound"] is True
        assert stored_experience["domain"] == "career_private"
        assert stored_experience["subject_public_name"] == "Example Company"
        assert stored_experience["record_visible_to_retrieval"] is False
        assert stored_experience["public_candidate_conversion_enabled"] is False
        assert stored_experience["public_serving_enabled"] is False
        assert stored_experience["b2b_delivery_enabled"] is False
        assert stored_experience["dashboard_enabled"] is False

        status, revoked_experience = post_private(
            f"{base_url}/v1/private/experience-records/{stored_experience['record_id']}:revoke",
            {"workspace": "closed-beta-test", "reason": "closed beta experience revoke"},
        )
        assert status == 200
        assert revoked_experience["status"] == "redacted_experience_revoked"
        assert revoked_experience["revoked"] is True
        assert revoked_experience["lifecycle_status"] == "revoked"
        assert revoked_experience["publication_enabled"] is False

        status, found = post_private(
            f"{base_url}/v1/private/search",
            {"workspace": "closed-beta-test", "task_profile": task_profile, "limit": 3, "min_score": 1},
        )
        assert status == 200
        assert found["result"]["decision"] == "cards_found"
        assert found["result"]["served_from"] == "closed_private_exact_fts"
        assert found["result"]["cards"][0]["card_id"] == card_id
        assert found["result"]["cards"][0]["card_version_id"] == published["card_version_id"]
        assert "summary" not in found["result"]["cards"][0]

        status, viewed = post_private(
            f"{base_url}/v1/private/cards/{card_id}:view",
            {"workspace": "closed-beta-test"},
        )
        assert status == 200
        assert viewed["status"] == "private_card"
        assert viewed["card_id"] == card_id
        assert viewed["card_version_id"] == published["card_version_id"]
        assert viewed["card"] == card
        assert viewed["publication_enabled"] is False

        status, revoked = post_private(
            f"{base_url}/v1/private/cards/{card_id}:revoke",
            {"workspace": "closed-beta-test", "reason": "closed beta revoke"},
        )
        assert status == 200
        assert revoked["status"] == "revoked"
        assert revoked["revoked"] is True

        status, hidden = post_private(
            f"{base_url}/v1/private/search",
            {"workspace": "closed-beta-test", "task_profile": task_profile},
        )
        assert status == 200
        assert hidden["result"]["decision"] == "no_suggestion"

        status, purged = post_private(
            f"{base_url}/v1/private/cards/{card_id}:purge",
            {"workspace": "closed-beta-test", "reason": "closed beta purge"},
        )
        assert status == 200
        assert purged["status"] == "purged"
        assert purged["purged"] is True
    finally:
        stop_process(process)
    with psycopg.connect(api_url, connect_timeout=3) as conn:
        assert conn.execute("select current_user").fetchone()[0] == "knudg_api_app"
        assert conn.execute("select count(*) from schema_migrations").fetchone()[0] >= 9
        assert conn.execute(
            "select has_table_privilege('knudg_api_app', 'local_private_card_bodies', 'select')"
        ).fetchone()[0] is False
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_private_publish(uuid, uuid, uuid, text, text, text, jsonb, jsonb)',
              'execute'
            )
            """
        ).fetchone()[0] is False
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_search(text, text[], text, integer)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_merge_update(text, uuid, jsonb, jsonb, jsonb)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_private_merge_update(uuid, uuid[], uuid, text, uuid, jsonb, jsonb, jsonb)',
              'execute'
            )
            """
        ).fetchone()[0] is False
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_publication_candidate(text, uuid)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_card_view(text, uuid)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_store_redacted_experience(text, jsonb)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_complete_private_retention(text, uuid, text, text, uuid, text, text, text, boolean, boolean, boolean)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_revoke_redacted_experience(text, uuid, text)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        assert conn.execute(
            """
            select has_function_privilege(
              'knudg_api_app',
              'knudg_closed_api_purge_redacted_experience(text, uuid, text)',
              'execute'
            )
            """
        ).fetchone()[0] is True
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("select * from local_private_card_bodies limit 1").fetchone()
        conn.rollback()

    with psycopg.connect(migrated_db, connect_timeout=3) as conn:
        rows = conn.execute(
            """
            select b.body_json, b.lifecycle_status as body_status,
              d.search_text, d.lifecycle_status as search_status
            from local_private_card_bodies b
            join local_private_search_documents d
              on d.tenant_id = b.tenant_id
             and d.card_id = b.card_id
             and d.card_version_id = b.card_version_id
            where b.card_id = %s
            order by b.created_at, b.card_version_id
            """,
            (card_id,),
        ).fetchall()
        purge_event_row = conn.execute(
            """
            select event_json
            from local_private_value_events
            where card_id = %s and event_name = 'purge_completed'
            order by created_at desc
            limit 1
            """,
            (card_id,),
        ).fetchone()
        event_row = conn.execute(
            """
            select event_json
            from local_private_value_events
            where card_id = %s and event_name = 'publication_candidate_prepared'
            order by created_at desc
            limit 1
            """,
            (card_id,),
        ).fetchone()
        experience_row = conn.execute(
            """
            select domain, subject_type, subject_public_name, record_visible_to_retrieval,
              lifecycle_status, public_candidate_conversion_enabled, public_serving_enabled, b2b_delivery_enabled,
              dashboard_enabled, private_retention_consent_id, private_retention_handoff_id
            from redacted_private_experience_records
            where id = %s
            """,
            (stored_experience["record_id"],),
        ).fetchone()
    assert len(rows) == 2
    assert all(row[0] == {} for row in rows)
    assert all(row[1] == "purged" for row in rows)
    assert all(row[2] == "" for row in rows)
    assert all(row[3] == "purged" for row in rows)
    assert purge_event_row[0]["search_versions_purged"] == 2
    assert purge_event_row[0]["body_versions_purged"] == 2
    assert event_row[0]["candidate_digest"] == candidate["candidate_digest"]
    assert event_row[0]["public_publication_enabled"] is False
    assert experience_row == (
        "career_private",
        "company",
        "Example Company",
        False,
        "revoked",
        False,
        False,
        False,
        False,
        uuid.UUID(consent_proof["consent_id"]),
        uuid.UUID(consent_proof["handoff_id"]),
    )


def test_closed_api_allows_deployment_type_override():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_DEPLOYMENT_TYPE"] = "greencloud_closed_launch"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        status, capabilities = get_json(f"{base_url}/capabilities")
        assert status == 200
        assert capabilities["deployment_type"] == "greencloud_closed_launch"
    finally:
        stop_process(process)


def test_closed_api_capabilities_reports_http_origin_for_loopback_host_without_forwarded_proto():
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        base_url = f"http://127.0.0.1:{startup['port']}"
        status, capabilities = get_json(f"{base_url}/capabilities")
        assert status == 200
        assert capabilities["capability_resource_origin"] == base_url
    finally:
        stop_process(process)


def test_closed_api_capabilities_uses_plain_http_host_without_forwarded_proto():
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        request = urllib.request.Request(
            f"http://127.0.0.1:{startup['port']}/capabilities",
            headers={"host": "api.knudg.com"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            capabilities = json.loads(response.read().decode("utf-8"))
        assert capabilities["capability_resource_origin"] == "http://api.knudg.com"
    finally:
        stop_process(process)


def test_closed_api_cors_allows_local_operator_frontend_preflight():
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_closed_api.py"),
            "--port",
            "0",
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        startup = read_startup_line(process)
        request = urllib.request.Request(
            f"http://127.0.0.1:{startup['port']}/v1/private/search",
            headers={
                "origin": "http://127.0.0.1:8790",
                "access-control-request-method": "POST",
                "access-control-request-headers": "authorization, content-type",
            },
            method="OPTIONS",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 204
            assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8790"
            assert "Authorization" in response.headers["access-control-allow-headers"]
    finally:
        stop_process(process)
