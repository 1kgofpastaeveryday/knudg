import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from scripts.card_payload import canonical_digest_hex
from scripts.knudg_local_private import validate_local_private_card_v0


ROOT = Path(__file__).resolve().parents[1]


def read_startup_line(process, timeout_seconds=5):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            return json.loads(line)
    raise AssertionError("closed API did not print a startup line")


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
        assert capabilities["deployment_type"] == "azure_closed_launch"
        assert capabilities["features"]["search"] is False
        assert capabilities["features"]["publication"] is False
        assert capabilities["features"]["write"] is False

        status, closed = post_json(f"{base_url}/v1/search")
        assert status == 404
        assert closed["status"] == "closed"
    finally:
        stop_process(process)


def test_closed_api_private_publish_requires_token_and_digest_before_storage():
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
        card = validate_local_private_card_v0(json.loads((ROOT / "fixtures" / "local-private-card.sample.json").read_text(encoding="utf-8")))
        digest = canonical_digest_hex(card)

        status, capabilities = get_json(f"{base_url}/capabilities")
        assert status == 200
        assert capabilities["features"]["operator_private_publish"] is True
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
