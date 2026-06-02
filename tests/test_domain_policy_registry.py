import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.knudg_domain_policy import (
    DOMAIN_KEYS,
    NON_INGEST_DOMAINS,
    TECHNICAL_DEFAULT_RETRIEVAL_DOMAINS,
    DomainPolicyError,
    normalize_retrieval_domains,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "domain-policy-registry-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "domain-policy-registry.draft.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_domain_policy_registry_fixture_validates():
    data = load_fixture()
    Draft202012Validator.check_schema(json.loads(SCHEMA.read_text(encoding="utf-8")))
    validator().validate(data)


def test_domain_policy_registry_matches_runtime_constants():
    data = load_fixture()
    assert tuple(data["domains"]) == DOMAIN_KEYS
    assert tuple(data["default_task_retrieval_domains"]) == TECHNICAL_DEFAULT_RETRIEVAL_DOMAINS
    for key, policy in data["domains"].items():
        assert policy["domain"] == key


def test_broader_domains_are_not_ingestable_yet():
    data = load_fixture()
    for domain in NON_INGEST_DOMAINS:
        policy = data["domains"][domain]
        assert policy["ingest_enablement"] != "closed_launch_structured_only"
    assert data["domains"]["career_private"]["public_eligible"] is False
    assert data["domains"]["place_service_experience"]["public_eligible"] is False


def test_retrieval_domain_normalization_is_technical_only_for_now():
    assert normalize_retrieval_domains(None) == ["technical_work"]
    assert normalize_retrieval_domains(["technical_work"]) == ["technical_work"]
    assert normalize_retrieval_domains(["technical_work", "technical_work"]) == ["technical_work"]

    for value in (["career_private"], ["technical_work", "career_private"], ["unknown_domain"], "technical_work"):
        with pytest.raises(DomainPolicyError):
            normalize_retrieval_domains(value)
