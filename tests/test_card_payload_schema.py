import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.card_payload import (
    CardPayloadError,
    canonical_digest,
    canonicalize,
    load_json_without_duplicate_keys,
    parse_and_digest,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_payload():
    return {
        "outcome_type": "solved",
        "goal": "capture a solved setup path",
        "symptom": "a repeatable setup issue was resolved",
        "environment": {"agent_tool": "Codex", "os": "Windows"},
        "context_fingerprint": {"repo_shape": "pytest + postgres"},
        "successful_path": ["apply the documented migration"],
        "failed_paths": [],
        "known_unknowns": [],
        "scope_limits": ["local M0 validation only"],
        "evidence_strength": "single_session",
        "quality_state": "unreviewed",
        "safety": {
            "safety_class": "low",
            "review_state": "cleared",
            "executable_advice": False,
            "mentions_urls": False,
            "mentions_packages": False,
            "mentions_repositories": False,
            "credential_risk": False,
            "billing_risk": False,
            "deletion_risk": False,
            "network_call_risk": False,
            "verification_state": "single_session",
            "withheld_reason": None,
        },
        "privacy": {"contains_personal_data": False, "source_class": "synthetic"},
        "provenance": {"source": "test fixture", "source_class": "synthetic"},
    }


def schema_validator():
    schema = json.loads((ROOT / "schemas" / "card-payload-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_digest_vectors_are_stable():
    vectors = json.loads((ROOT / "schemas" / "card-payload-v1.digest-vectors.json").read_text(encoding="utf-8"))
    assert vectors["profile"] == "sha256:jcs-rfc8785:v1"
    for vector in vectors["vectors"]:
        payload = load_json_without_duplicate_keys(vector["raw"])
        assert canonicalize(payload) == vector["canonical"]
        assert canonical_digest(payload) == vector["digest"]
    for vector in vectors["negative_vectors"]:
        with pytest.raises(CardPayloadError, match=vector["error"]):
            parse_and_digest(vector["raw"])


def test_json_schema_artifact_accepts_and_rejects_core_payloads():
    validator = schema_validator()
    validator.validate(valid_payload())

    projection_owned = valid_payload()
    projection_owned["tenant_id"] = "00000000-0000-0000-0000-000000000000"
    assert list(validator.iter_errors(projection_owned))

    failed_only = valid_payload()
    failed_only["outcome_type"] = "failed_only"
    assert list(validator.iter_errors(failed_only))

    unknown = valid_payload()
    unknown["outcome_type"] = "unknown_clarified"
    unknown["successful_path"] = None
    unknown["known_unknowns"] = []
    assert list(validator.iter_errors(unknown))

    non_ascii_key = valid_payload()
    non_ascii_key["environment"]["\u30c4\u30fc\u30eb"] = "Codex"
    assert list(validator.iter_errors(non_ascii_key))

    nested_non_ascii_key = valid_payload()
    nested_non_ascii_key["environment"]["nested"] = {"\u30c4\u30fc\u30eb": "Codex"}
    assert list(validator.iter_errors(nested_non_ascii_key))

    bad_optional = valid_payload()
    bad_optional["twist"] = {"not": "text"}
    assert list(validator.iter_errors(bad_optional))

    non_synthetic = valid_payload()
    non_synthetic["privacy"]["source_class"] = "private_session"
    assert list(validator.iter_errors(non_synthetic))


def test_duplicate_keys_fail_before_jsonb_shape_is_possible():
    with pytest.raises(CardPayloadError, match="duplicate object key"):
        load_json_without_duplicate_keys('{"goal":"first","goal":"second"}')


def test_key_order_does_not_change_digest():
    a = '{"outcome_type":"solved","goal":"g","symptom":"s","environment":{},"context_fingerprint":{},"successful_path":["x"],"failed_paths":[],"known_unknowns":[],"scope_limits":[],"evidence_strength":"single_session","quality_state":"unreviewed","safety":{"safety_class":"low","review_state":"cleared","executable_advice":false,"mentions_urls":false,"mentions_packages":false,"mentions_repositories":false,"credential_risk":false,"billing_risk":false,"deletion_risk":false,"network_call_risk":false,"verification_state":"single_session","withheld_reason":null},"privacy":{"source_class":"synthetic"},"provenance":{"source_class":"synthetic"}}'
    b = '{"provenance":{"source_class":"synthetic"},"privacy":{"source_class":"synthetic"},"safety":{"withheld_reason":null,"verification_state":"single_session","network_call_risk":false,"deletion_risk":false,"billing_risk":false,"credential_risk":false,"mentions_repositories":false,"mentions_packages":false,"mentions_urls":false,"executable_advice":false,"review_state":"cleared","safety_class":"low"},"quality_state":"unreviewed","evidence_strength":"single_session","scope_limits":[],"known_unknowns":[],"failed_paths":[],"successful_path":["x"],"context_fingerprint":{},"environment":{},"symptom":"s","goal":"g","outcome_type":"solved"}'
    assert parse_and_digest(a)[2] == parse_and_digest(b)[2]


def test_schema_validation_rejects_projection_fields_and_bad_outcome_shape():
    payload = valid_payload()
    payload["tenant_id"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(CardPayloadError, match="projection-owned field"):
        parse_and_digest(json.dumps(payload))

    failed_only = valid_payload()
    failed_only["outcome_type"] = "failed_only"
    with pytest.raises(CardPayloadError, match="failed_only payload cannot include"):
        parse_and_digest(json.dumps(failed_only))

    solved_without_path = valid_payload()
    solved_without_path["successful_path"] = []
    with pytest.raises(CardPayloadError, match="solved payload requires"):
        parse_and_digest(json.dumps(solved_without_path))

    bad_step = valid_payload()
    bad_step["successful_path"] = [""]
    with pytest.raises(CardPayloadError, match="successful_path items"):
        parse_and_digest(json.dumps(bad_step))

    unknown = valid_payload()
    unknown["outcome_type"] = "unknown_clarified"
    unknown["successful_path"] = None
    unknown["known_unknowns"] = []
    with pytest.raises(CardPayloadError, match="unknown_clarified payload requires"):
        parse_and_digest(json.dumps(unknown))

    non_ascii_key = valid_payload()
    non_ascii_key["environment"]["\u30c4\u30fc\u30eb"] = "Codex"
    with pytest.raises(CardPayloadError, match="object keys must be ASCII"):
        parse_and_digest(json.dumps(non_ascii_key))

    extra_top_level = valid_payload()
    extra_top_level["extra"] = "not schema v1"
    with pytest.raises(CardPayloadError, match="unknown top-level field"):
        parse_and_digest(json.dumps(extra_top_level))

    extra_safety = valid_payload()
    extra_safety["safety"]["extra"] = True
    with pytest.raises(CardPayloadError, match="unknown safety field"):
        parse_and_digest(json.dumps(extra_safety))

    bad_withheld_reason = valid_payload()
    bad_withheld_reason["safety"]["withheld_reason"] = 3
    with pytest.raises(CardPayloadError, match="withheld_reason"):
        parse_and_digest(json.dumps(bad_withheld_reason))

    bad_twist = valid_payload()
    bad_twist["twist"] = {"not": "text"}
    with pytest.raises(CardPayloadError, match="twist"):
        parse_and_digest(json.dumps(bad_twist))

    bad_contradictions = valid_payload()
    bad_contradictions["contradictions"] = [{"not": "text"}]
    with pytest.raises(CardPayloadError, match="contradictions items"):
        parse_and_digest(json.dumps(bad_contradictions))

    non_synthetic = valid_payload()
    non_synthetic["provenance"]["source_class"] = "private_session"
    with pytest.raises(CardPayloadError, match="provenance.source_class"):
        parse_and_digest(json.dumps(non_synthetic))
