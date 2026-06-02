import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "private-use-notice-v0.schema.json"
NOTICE = ROOT / "fixtures" / "private-use-notice.closed-launch-draft.json"


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_closed_launch_private_use_notice_is_valid_and_disabled():
    notice = json.loads(NOTICE.read_text(encoding="utf-8"))
    errors = sorted(validator().iter_errors(notice), key=lambda error: error.path)
    assert errors == []
    assert notice["status"] == "draft_disabled"
    assert notice["collection_enabled"] is False
    assert notice["publication_enabled"] is False
    assert notice["data_leaves_local_workspace"] is False
    assert notice["acknowledgement_required_before_collection"] is True


def test_local_private_use_notice_names_forbidden_raw_inputs():
    notice = json.loads(NOTICE.read_text(encoding="utf-8"))
    forbidden = set(notice["forbidden_fields"])
    for field in [
        "raw transcript",
        "raw log",
        "full stack trace",
        "source file body",
        "absolute path",
        "private repository name",
        "secret",
        "token",
        "credential",
        "unredacted command output",
    ]:
        assert field in forbidden


def test_schema_rejects_enabled_private_publication():
    notice = json.loads(NOTICE.read_text(encoding="utf-8"))
    notice["publication_enabled"] = True
    errors = list(validator().iter_errors(notice))
    assert errors
