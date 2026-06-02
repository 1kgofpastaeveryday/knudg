import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.knudg_local_private import (
    LocalPrivateCardError,
    canonicalize_local_private_card,
    local_private_card_digest,
    parse_and_digest,
    validate_local_private_card_v0,
)
from scripts.knudgctl import local_private_projection_payload, local_private_search_text


ROOT = Path(__file__).resolve().parents[1]


def local_card(**overrides):
    payload = {
        "source_class": "local_private_dogfood",
        "title": "Pytest local capture fix",
        "human_summary": {
            "content": "Local capture cards need a small structured input before storage.",
            "redaction_summary": "Removed private paths, hostnames, usernames, env values, and raw logs.",
        },
        "problem_summary": "Local capture validation needed a bounded structured card input.",
        "solution_summary": "Added a small local helper that normalizes fields, validates public references, and computes a canonical digest.",
        "public_packages": ["pytest", "jsonschema"],
        "environment_tags": ["windows", "python", "local-postgres"],
        "public_reference_urls": ["https://docs.python.org/3/library/json.html"],
        "command_labels": ["pytest test run", "npm dependency install failure"],
        "error_fingerprints": ["ModuleNotFoundError missing jsonschema"],
        "lessons": ["Keep local card input structured and bounded."],
    }
    payload.update(overrides)
    return payload


def test_accepts_local_private_payload_and_returns_canonical_digest():
    payload = local_card(problem_summary="Local\tcapture\nvalidation needed a bounded structured card input.")

    sanitized, canonical, digest = parse_and_digest(json.dumps(payload))

    assert sanitized["source_class"] == "local_private_dogfood"
    assert sanitized["human_summary"]["content"] == "Local capture cards need a small structured input before storage."
    assert sanitized["problem_summary"] == "Local capture validation needed a bounded structured card input."
    assert json.loads(canonical) == sanitized
    assert digest == local_private_card_digest(payload)
    assert canonical == canonicalize_local_private_card(payload)
    assert digest.startswith("sha256:jcs-rfc8785:v1:")


def test_projection_payload_marks_local_private_without_body_text():
    payload = local_card()
    body_digest = local_private_card_digest(payload).rsplit(":", 1)[-1]

    projection = local_private_projection_payload(payload, body_digest)
    serialized = json.dumps(projection, sort_keys=True)

    assert projection["source_class"] == "local_private_dogfood"
    assert projection["visibility"] == "local_private"
    assert projection["sharing_state"] == "not_shared"
    assert projection["publication_state"] == "never_publishable"
    assert projection["privacy"]["source_class"] == "local_private_dogfood"
    assert projection["privacy"]["body_digest"] == body_digest
    assert projection["provenance"]["source_class"] == "local_private_dogfood"
    assert payload["title"] not in serialized
    assert payload["human_summary"]["content"] not in serialized
    assert payload["problem_summary"] not in serialized
    assert payload["solution_summary"] not in serialized


def test_human_summary_is_stored_but_not_indexed_for_agent_search():
    payload = local_card(
        human_summary={
            "content": "HUMANONLY review copy should remain outside the agent search text.",
            "redaction_summary": "Removed private paths, hostnames, usernames, env values, and raw logs.",
        }
    )
    sanitized = validate_local_private_card_v0(payload)

    assert sanitized["human_summary"]["content"].startswith("HUMANONLY")
    assert "HUMANONLY" not in local_private_search_text(sanitized)


@pytest.mark.parametrize(
    "payload",
    [
        local_card(problem_summary="The failing checkout lived under C:\\Users\\alice\\private\\repo during setup."),
        local_card(solution_summary="The value included token sk-canarycanarycanary and must be rejected."),
        local_card(human_summary={"content": "The path C:\\Users\\alice\\private\\repo was visible.", "redaction_summary": "Removed private paths."}),
        local_card(public_reference_urls=["https://buildbox.local/runbook"]),
        local_card(command_labels=["python -m pytest tests/test_knudg_local_private.py"]),
        local_card(error_fingerprints=['Traceback (most recent call last): File "x.py", line 10']),
        local_card(title="Cross C:", problem_summary="\\Users\\alice\\private\\repo was split across fields."),
    ],
)
def test_rejects_private_or_raw_content(payload):
    with pytest.raises(LocalPrivateCardError):
        validate_local_private_card_v0(payload)


def test_rejects_cross_field_secret_reconstruction():
    payload = local_card(title="Split sk-", problem_summary="canarycanarycanary value was spread across fields.")

    with pytest.raises(LocalPrivateCardError) as excinfo:
        validate_local_private_card_v0(payload)

    assert excinfo.value.reject_class == "secret_or_token"


def test_exception_messages_do_not_echo_rejected_canary_text():
    canary = "CANARY_DO_NOT_ECHO_123"
    payload = local_card(solution_summary=f"The rejected secret token {canary} must not be echoed.")

    with pytest.raises(LocalPrivateCardError) as excinfo:
        validate_local_private_card_v0(payload)

    message = str(excinfo.value)
    assert canary not in message
    assert "secret token" not in message


def test_cli_rejection_json_does_not_echo_body(tmp_path):
    canary = "CANARY_DO_NOT_ECHO_456"
    path = tmp_path / "card.json"
    path.write_text(json.dumps(local_card(solution_summary=f"The rejected token {canary} is private.")), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudg_local_private.py"), "--input", str(path), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert canary not in result.stdout
    assert canary not in result.stderr
    assert json.loads(result.stdout) == {"ok": False, "reject_class": "secret_or_token", "status": "rejected"}
