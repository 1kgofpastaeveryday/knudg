import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.knudg_closed_api import public_exposure_contract


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "public-exposure-contract-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "public-exposure-contract.sample.json"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_public_exposure_contract_fixture_matches_schema():
    Draft202012Validator(load_json(SCHEMA)).validate(load_json(FIXTURE))


def test_public_exposure_contract_helper_keeps_public_b2b_dashboard_disabled():
    candidate_digest = "a" * 64
    payload_digest = "sha256:" + "b" * 64
    contract = public_exposure_contract(candidate_digest, payload_digest)

    Draft202012Validator(load_json(SCHEMA)).validate(contract)
    assert contract["contract_digest_binding"] == {
        "candidate_digest": candidate_digest,
        "payload_digest": payload_digest,
    }
    assert contract["public_candidate_conversion"] == {
        "objective_item": 9,
        "enabled": False,
        "serving_enabled": False,
        "stored_public_card": False,
        "required_gates": ["PR-003", "PR-005", "PR-006", "REVIEWER_PUBLISH"],
    }
    assert contract["b2b_respondent_portal"]["enabled"] is False
    assert contract["b2b_respondent_portal"]["b2b_delivery_enabled"] is False
    assert contract["b2b_respondent_portal"]["response_available"] is False
    assert contract["company_store_dashboard"]["enabled"] is False
    assert contract["company_store_dashboard"]["dashboard_enabled"] is False
    assert contract["company_store_dashboard"]["aggregate_signal_available"] is False
    assert contract["company_store_dashboard"]["required_gates"] == [
        "AGGREGATE_PRIVACY_THRESHOLD_POLICY",
        "AGGREGATE_SIGNAL_POLICY",
        "CORRECTION_TAKEDOWN_POLICY",
        "DASHBOARD_DISPLAY_POLICY",
        "DASHBOARD_EXPORT_DOWNLOAD_POLICY",
        "FAIR_REVIEW_PRESENTATION_POLICY",
        "MANIPULATION_RESISTANCE_POLICY",
        "MIN_SOURCE_COUNT_POLICY",
        "MODERATION_WORKFLOW",
        "NO_ESCROW_ARTIFACT_DISPLAY_TESTS",
        "NO_IDENTITY_LEAKAGE_TESTS",
        "NO_SINGLE_OBSERVATION_DISPLAY_TESTS",
        "NO_SUPPRESSION_SURFACE_TESTS",
        "PUBLIC_B2B_DISCLOSURE_POLICY",
    ]
    assert "escrow_key_material" in contract["forbidden_outputs"]["b2b_respondent_portal"]
    assert "respondent_visible_user_attribution" in contract["forbidden_outputs"]["b2b_respondent_portal"]
    assert "escrow_ciphertext" in contract["forbidden_outputs"]["company_store_dashboard"]
    assert "single_observation_detail" in contract["forbidden_outputs"]["company_store_dashboard"]
    assert "match_status" in contract["forbidden_outputs"]["company_store_dashboard"]
    serialized = json.dumps(contract, sort_keys=True)
    assert "raw_body" not in serialized
    assert "submitter_identity" in serialized
    assert "protected_fingerprint" in serialized


def test_public_exposure_contract_schema_rejects_enabled_public_candidate(tmp_path):
    contract = load_json(FIXTURE)
    contract["public_candidate_conversion"]["enabled"] = True
    path = tmp_path / "enabled-public-contract.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    errors = list(Draft202012Validator(load_json(SCHEMA)).iter_errors(load_json(path)))
    assert errors
    assert any(error.validator == "const" for error in errors)
