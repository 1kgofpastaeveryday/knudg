import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.knudg_local_private import LocalPrivateCardError, validate_local_private_card_v0


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "candidate-payload-facets-v0.schema.json"
TECHNICAL_FIXTURE = ROOT / "fixtures" / "candidate-payload-facets.technical-work.sample.json"
CAREER_FIXTURE = ROOT / "fixtures" / "candidate-payload-facets.career-private.blocked.json"
LOCAL_CARD_FIXTURE = ROOT / "fixtures" / "local-private-card.sample.json"


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_payload_facets_accept_technical_work_fixture():
    data = load(TECHNICAL_FIXTURE)
    validator().validate(data)
    assert data["domain"] == "technical_work"
    assert data["retrieval_policy"] == "automatic_technical_only"
    assert data["source_policy"]["ingest_enablement"] == "closed_launch_structured_only"


def test_candidate_payload_facets_type_broader_domains_without_enabling_ingest():
    data = load(CAREER_FIXTURE)
    validator().validate(data)
    assert data["domain"] == "career_private"
    assert data["source_policy"]["ingest_enablement"] == "disabled_until_gate"
    assert data["source_policy"]["publication_eligible"] is False


def test_candidate_payload_facets_reject_enabled_career_ingest():
    data = load(CAREER_FIXTURE)
    data["source_policy"]["ingest_enablement"] = "closed_launch_structured_only"
    errors = list(validator().iter_errors(data))
    assert errors


def test_candidate_payload_facets_rejects_career_raw_source_retention():
    data = load(CAREER_FIXTURE)
    data["source_policy"]["raw_source_retention"] = "escrow_only"
    errors = list(validator().iter_errors(data))
    assert errors


def test_candidate_payload_facets_person_private_requires_null_name_and_no_aliases():
    data = load(CAREER_FIXTURE)
    data["subject"]["type"] = "person_private"
    data["subject"]["public_name"] = None
    data["subject"]["aliases"] = []
    validator().validate(data)

    data["subject"]["public_name"] = "Private Person"
    errors = list(validator().iter_errors(data))
    assert errors

    data["subject"]["public_name"] = None
    data["subject"]["aliases"] = ["private-person"]
    errors = list(validator().iter_errors(data))
    assert errors


def test_candidate_payload_facets_public_candidate_stays_non_public_until_published():
    data = load(CAREER_FIXTURE)
    data["domain"] = "public_experience_candidate"
    data["retrieval_policy"] = "never_public_until_published"
    data["source_policy"]["raw_source_retention"] = "none"
    data["source_policy"]["ingest_enablement"] = "disabled_until_gate"
    data["source_policy"]["publication_eligible"] = False
    validator().validate(data)

    data["source_policy"]["publication_eligible"] = True
    errors = list(validator().iter_errors(data))
    assert errors


def test_candidate_payload_facets_public_candidate_rejects_private_person_subject():
    data = load(CAREER_FIXTURE)
    data["domain"] = "public_experience_candidate"
    data["subject"]["type"] = "person_private"
    data["retrieval_policy"] = "never_public_until_published"
    data["source_policy"]["raw_source_retention"] = "none"
    data["source_policy"]["ingest_enablement"] = "disabled_until_gate"
    data["source_policy"]["publication_eligible"] = False

    errors = list(validator().iter_errors(data))
    assert errors


def test_candidate_payload_facets_public_aggregate_requires_reviewer_only_gate():
    data = load(CAREER_FIXTURE)
    data["domain"] = "public_aggregate_signal"
    data["subject"]["type"] = "aggregate_subject"
    data["claim_type"] = "aggregate_summary"
    data["retrieval_policy"] = "public_after_gates"
    data["source_policy"]["raw_source_retention"] = "none"
    data["source_policy"]["ingest_enablement"] = "reviewer_only_after_gate"
    data["source_policy"]["publication_eligible"] = True
    validator().validate(data)

    data["source_policy"]["ingest_enablement"] = "closed_launch_structured_only"
    errors = list(validator().iter_errors(data))
    assert errors


def test_candidate_payload_facets_public_aggregate_rejects_private_person_subject():
    data = load(CAREER_FIXTURE)
    data["domain"] = "public_aggregate_signal"
    data["subject"]["type"] = "person_private"
    data["claim_type"] = "aggregate_summary"
    data["retrieval_policy"] = "public_after_gates"
    data["source_policy"]["raw_source_retention"] = "none"
    data["source_policy"]["ingest_enablement"] = "reviewer_only_after_gate"
    data["source_policy"]["publication_eligible"] = True

    errors = list(validator().iter_errors(data))
    assert errors


def test_local_private_card_does_not_ingest_broader_domain_fields():
    data = load(LOCAL_CARD_FIXTURE)
    data["domain"] = "career_private"
    try:
        validate_local_private_card_v0(data)
    except LocalPrivateCardError:
        return
    raise AssertionError("local-private card accepted a broader-domain field")
