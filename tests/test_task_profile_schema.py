import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "task-profile-v0.schema.json"


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_valid(payload):
    errors = sorted(validator().iter_errors(payload), key=lambda error: error.path)
    assert errors == []


def assert_invalid(payload):
    assert list(validator().iter_errors(payload))


def minimal_profile():
    return {
        "schema_version": "task_profile.v0",
        "intent": "implement",
        "explicit_query": "wire task profile schema for current work retrieval",
        "repo_shape_category": "python-postgres",
        "retrieval_domains": ["technical_work"],
        "recent_event_kinds": ["task_start"],
    }


def rich_profile():
    profile = minimal_profile()
    profile.update(
        {
            "subsystems": ["retrieval", "summoned_roles"],
            "safe_file_refs": [
                "schemas/task-profile-v0.schema.json",
                "tests/test_task_profile_schema.py",
            ],
            "symbols": ["task_profile.v0", "SearchProfile", "writer.enqueue-next"],
            "error_fingerprints": ["pytest-schema-validation-failed"],
            "public_packages": ["pypi:jsonschema"],
            "public_frameworks_tools": ["pytest", "postgres"],
            "language_runtime": "python-3.12",
            "coarse_os": "windows",
            "dependency_major_versions": ["jsonschema:4", "pytest:9"],
            "risk_tags": ["privacy", "database"],
            "recent_event_kinds": ["task_start", "before_edit"],
        }
    )
    return profile


def test_accepts_minimal_task_profile():
    assert_valid(minimal_profile())


def test_accepts_rich_current_work_profile():
    assert_valid(rich_profile())


def test_rejects_unknown_fields_and_wrong_schema_version():
    profile = minimal_profile()
    profile["raw_log"] = "Traceback with private data"
    assert_invalid(profile)

    profile = minimal_profile()
    profile["schema_version"] = "search-profile-v0"
    assert_invalid(profile)


def test_rejects_raw_or_private_text_in_query():
    for query in [
        "look at C:\\Users\\4\\private\\repo",
        "debug https://github.com/private/repo",
        "fix token leak in logs",
        "line one\nline two",
    ]:
        profile = minimal_profile()
        profile["explicit_query"] = query
        assert_invalid(profile)


def test_rejects_private_or_absolute_file_refs():
    for file_ref in [
        "C:\\Users\\4\\repo\\app.py",
        "/home/user/repo/app.py",
        "../outside.py",
        "configs/secret.env",
        "docs\\architecture\\retrieval.md",
    ]:
        profile = rich_profile()
        profile["safe_file_refs"] = [file_ref]
        assert_invalid(profile)


def test_rejects_secrets_in_symbols_fingerprints_and_packages():
    profile = rich_profile()
    profile["symbols"] = ["api_key_loader"]
    assert_invalid(profile)

    profile = rich_profile()
    profile["error_fingerprints"] = ["token-leaked"]
    assert_invalid(profile)

    profile = rich_profile()
    profile["public_packages"] = ["pypi:secret-client"]
    assert_invalid(profile)


def test_rejects_invalid_enums_and_unbounded_lists():
    profile = minimal_profile()
    profile["intent"] = "remember"
    assert_invalid(profile)

    profile = minimal_profile()
    profile["recent_event_kinds"] = []
    assert_invalid(profile)

    profile = rich_profile()
    profile["risk_tags"] = ["privacy", "personal_memory"]
    assert_invalid(profile)

    profile = rich_profile()
    profile["symbols"] = [f"symbol_{index}" for index in range(41)]
    assert_invalid(profile)


def test_retrieval_domains_are_technical_only_for_now():
    profile = minimal_profile()
    profile["retrieval_domains"] = ["career_private"]
    assert_invalid(profile)

    profile = minimal_profile()
    profile["retrieval_domains"] = ["technical_work", "career_private"]
    assert_invalid(profile)
