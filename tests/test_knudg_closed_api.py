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
PUBLIC_EXPOSURE_SCHEMA = ROOT / "schemas" / "public-exposure-contract-v0.schema.json"


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
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
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
    assert result["verdict"] == "needs_human_review"
    assert result["risk_reasons"] == ["llm_provider_unconfigured"]
    assert result["provider"] == "none"
    assert result["llm_called"] is False
    assert result["fail_closed"] is True
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
        assert timeout >= 1
        return MockNvidiaResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "verdict": "allow",
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

    assert result["verdict"] == "allow"
    assert result["risk_level"] == "low"
    assert result["provider"] == "nvidia"
    assert result["model"] == "z-ai/glm-5.1"
    assert result["llm_called"] is True
    assert result["fail_closed"] is False
    assert result["final_publication_completion_enabled"] is False


def test_final_filter_invalid_glm_response_needs_human_review(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    def mock_urlopen(request, timeout):
        return MockNvidiaResponse({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr(closed_api.urllib.request, "urlopen", mock_urlopen)

    result = closed_api.evaluate_final_filter({"candidate": sample_final_filter_candidate()})

    assert result["verdict"] == "needs_human_review"
    assert result["risk_reasons"] == ["llm_provider_error"]
    assert result["provider"] == "nvidia"
    assert result["llm_called"] is True


def test_closed_api_final_filter_route_requires_operator_and_fails_closed_without_key():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env.pop("KNUDG_OPERATOR_TOKEN", None)
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
        assert evaluated["verdict"] == "needs_human_review"
        assert evaluated["risk_reasons"] == ["llm_provider_unconfigured"]
        assert evaluated["public_publication_enabled"] is False
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
        raw_card["solution_summary"] = f"The rejected secret token {canary} lived under C:\\Users\\4\\private\\repo."
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
                    "explicit_query": f"raw secret token {canary} at C:\\Users\\4\\private",
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


def test_closed_api_publication_candidate_rejects_workspace_without_echoing_canary():
    env = {**os.environ}
    env.pop("DATABASE_URL", None)
    env["KNUDG_OPERATOR_TOKEN"] = "test-token"
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
        canary = "CANARY_CANDIDATE_WORKSPACE_DO_NOT_ECHO"
        status, rejected = post_private(
            f"{base_url}/v1/private/cards/11111111-1111-4111-8111-111111111111:publication-candidate",
            {"workspace": f"C:\\Users\\4\\private\\{canary}"},
            token="test-token",
        )
        assert status == 400
        assert rejected == {"status": "rejected"}
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
        with psycopg.connect(migrated_db, connect_timeout=3) as conn:
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
        assert "summary" not in found["result"]["cards"][0]

        status, candidate = post_private(
            f"{base_url}/v1/private/cards/{card_id}:publication-candidate",
            {"workspace": "closed-beta-test"},
        )
        assert status == 200
        assert candidate["status"] == "publication_candidate_ready"
        assert candidate["stored_public_card"] is False
        assert candidate["public_publication_enabled"] is False
        assert candidate["external_publication_enabled"] is False
        assert candidate["requires_human_approval"] is True
        assert candidate["candidate"]["schema_version"] == "closed-publication-candidate-v0"
        assert candidate["candidate"]["candidate_state"] == "publication_ready_candidate"
        assert candidate["candidate"]["redaction"]["state"] == "sanitized_public_fields_only"
        assert candidate["candidate"]["redaction"]["raw_body_excluded"] is True
        assert candidate["candidate"]["redaction"]["candidate_digest_binds_exact_artifact"] is True
        assert candidate["candidate"]["review"]["public_indexing_enabled"] is False
        assert candidate["candidate"]["artifact"]["title"] == card["title"]
        assert candidate["candidate"]["source"]["card_id"] == card_id
        surface_contracts = candidate["surface_contracts"]
        Draft202012Validator(json.loads(PUBLIC_EXPOSURE_SCHEMA.read_text(encoding="utf-8"))).validate(surface_contracts)
        assert surface_contracts["contract_digest_binding"]["candidate_digest"] == candidate["candidate_digest"]
        assert surface_contracts["contract_digest_binding"]["payload_digest"] == candidate["payload_digest"]
        assert surface_contracts["public_candidate_conversion"]["enabled"] is False
        assert surface_contracts["public_candidate_conversion"]["serving_enabled"] is False
        assert surface_contracts["public_candidate_conversion"]["stored_public_card"] is False
        assert surface_contracts["b2b_respondent_portal"]["enabled"] is False
        assert surface_contracts["b2b_respondent_portal"]["b2b_delivery_enabled"] is False
        assert surface_contracts["b2b_respondent_portal"]["response_available"] is False
        assert surface_contracts["company_store_dashboard"]["enabled"] is False
        assert surface_contracts["company_store_dashboard"]["dashboard_enabled"] is False
        assert surface_contracts["company_store_dashboard"]["aggregate_signal_available"] is False
        assert "submitter_identity" in surface_contracts["forbidden_outputs"]["public_candidate_conversion"]
        assert "protected_fingerprint" in surface_contracts["forbidden_outputs"]["company_store_dashboard"]

        status, viewed = post_private(
            f"{base_url}/v1/private/cards/{card_id}:view",
            {"workspace": "closed-beta-test"},
        )
        assert status == 200
        assert viewed["status"] == "private_card"
        assert viewed["card_id"] == card_id
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
        row = conn.execute(
            """
            select b.body_json, b.lifecycle_status as body_status,
              d.search_text, d.lifecycle_status as search_status
            from local_private_card_bodies b
            join local_private_search_documents d
              on d.tenant_id = b.tenant_id
             and d.card_id = b.card_id
             and d.card_version_id = b.card_version_id
            where b.card_id = %s
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
    assert row[0] == {}
    assert row[1] == "purged"
    assert row[2] == ""
    assert row[3] == "purged"
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
