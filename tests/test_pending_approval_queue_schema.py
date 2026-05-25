import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "pending-approval-queue-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "pending-approval-queue.model-only.json"


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_pending_approval_queue_model_fixture_is_valid_and_disabled():
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))
    errors = sorted(validator().iter_errors(item), key=lambda error: error.path)
    assert errors == []
    assert item["state"] == "model_only"
    assert item["storage_enabled"] is False
    assert item["preview_ref"]["body_included"] is False


def test_pending_approval_queue_schema_rejects_body_fields():
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item["raw_transcript"] = "must not be here"
    assert list(validator().iter_errors(item))


def test_pending_approval_queue_model_only_cannot_enable_storage():
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item["storage_enabled"] = True
    assert list(validator().iter_errors(item))


def test_digest_only_preview_cannot_include_body():
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item["preview_ref"]["body_included"] = True
    assert list(validator().iter_errors(item))
