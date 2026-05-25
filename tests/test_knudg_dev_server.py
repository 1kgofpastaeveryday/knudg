import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tests.test_knudg_synthetic_retrieval import corpus_payload, request_payload


ROOT = Path(__file__).resolve().parents[1]


def read_startup_line(process, timeout_seconds=5):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        line = process.stdout.readline()
        if line:
            return json.loads(line)
    raise AssertionError("dev server did not print a startup line")


def run_knudgctl(*args, env=None):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudgctl.py"), *args],
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
    )
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def stop_process(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_dev_server_supports_knudgctl_local_dogfood_flow(tmp_path):
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_dev_server.py"),
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
        assert startup["status"] == "listening"
        server_url = startup["server_url"]
        config = tmp_path / "client-config.json"

        code, payload = run_knudgctl(
            "config",
            "set-server",
            "--profile",
            "local",
            "--server-url",
            server_url,
            "--config",
            str(config),
        )
        assert code == 0
        assert payload["server_url"] == server_url

        code, payload = run_knudgctl("server", "status", "--config", str(config))
        assert code == 0
        assert payload["status"] == "ok"
        assert payload["health"]["ready"]["components"]["postgres"] == "not_configured"
        assert payload["health"]["ready"]["components"]["migration"] == "not_configured"
        assert payload["health"]["ready"]["components"]["revocation_epoch"] == "not_configured"
        assert payload["health"]["ready"]["components"]["synthetic_retrieval"] == "ready"
        assert payload["health"]["ready"]["route_classes"]["search"] == "disabled"
        assert payload["health"]["ready"]["route_classes"]["synthetic-retrieval"] == "synthetic_only"
        assert payload["health"]["ready"]["route_classes"]["card-read"] == "disabled"
        assert payload["health"]["ready"]["route_classes"]["submit/write"] == "disabled"
        assert payload["health"]["ready"]["route_classes"]["worker-lane"] == "disabled"

        code, payload = run_knudgctl("server", "capabilities", "--config", str(config))
        assert code == 0
        assert payload["status"] == "ok"
        assert payload["deployment_type"] == "local"
        assert payload["capabilities_digest"].startswith("sha256:")

        status, retrieval = post_json(
            f"{server_url}/v1/synthetic-retrieval/search",
            {"request": request_payload(), "corpus": corpus_payload(), "min_score": 2},
        )
        assert status == 200
        assert retrieval["decision"] == "cards_found"
        assert retrieval["delivery_mode"] == "retrieval_panel"
        assert retrieval["cards"][0]["card_id"] == "card_001"
        assert "successful_path" not in json.dumps(retrieval)

        request_path = tmp_path / "synthetic-request.json"
        corpus_path = tmp_path / "synthetic-corpus.json"
        request_path.write_text(json.dumps(request_payload()), encoding="utf-8")
        corpus_path.write_text(json.dumps(corpus_payload()), encoding="utf-8")
        code, payload = run_knudgctl(
            "server",
            "synthetic-search",
            "--config",
            str(config),
            "--input",
            str(request_path),
            "--corpus",
            str(corpus_path),
        )
        assert code == 0
        assert payload["status"] == "ok"
        assert "server_url" not in payload
        assert payload["result"]["decision"] == "cards_found"
        assert payload["protected_data_serving_enabled"] is False
        assert "successful_path" not in json.dumps(payload)

        try:
            post_json(
                f"{server_url}/v1/synthetic-retrieval/search",
                {
                    "request": request_payload(),
                    "corpus": corpus_payload(source_class="private_session"),
                    "min_score": 2,
                },
            )
        except urllib.error.HTTPError as exc:
            rejected = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 400
            assert rejected["abstention_reason"] == "payload_rejected"
        else:
            raise AssertionError("non-synthetic corpus should be rejected")

        code, payload = run_knudgctl(
            "server",
            "capabilities",
            "--pin",
            "--allow-insecure-loopback",
            "--config",
            str(config),
        )
        assert code == 0
        assert payload["pin_state"] == "pinned"
    finally:
        stop_process(process)
