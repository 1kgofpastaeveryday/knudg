import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "company-store-dashboard-request-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "company-store-dashboard.blocked.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "company-store-dashboard.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_company_store_dashboard.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def validator():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_company_store_dashboard_fixture_matches_schema():
    data = load_fixture()
    validator().validate(data)
    assert data["objective_item"] == 13
    assert data["surface"] == "company_store_dashboard"
    assert data["status"] == "blocked"
    assert data["request_class"] == "preflight_only"
    assert data["dashboard_subject"]["subject_type"] == "company"
    assert data["dashboard_subject"]["domain"] == "public_aggregate_signal"
    assert data["aggregate_signal_request"]["aggregate_signal_available"] is False
    assert data["aggregate_signal_request"]["single_observation_display_enabled"] is False
    assert data["aggregate_signal_request"]["negative_review_suppression_enabled"] is False
    assert data["aggregate_privacy_contract"]["aggregation_mode"] == "aggregate_only_preflight"
    assert data["aggregate_privacy_contract"]["drilldown_to_source_allowed"] is False
    assert data["review_integrity_contract"]["favorability_neutral_processing_required"] is True
    assert data["review_integrity_contract"]["negative_review_suppression_allowed"] is False
    assert data["dashboard_display_contract"]["view_model_state"] == "model_only_not_served"
    assert data["dashboard_display_contract"]["single_observation_display_allowed"] is False
    assert data["dashboard_display_contract"]["escrow_artifact_display_allowed"] is False
    assert data["dashboard_delivery_contract"]["route_allocation"] == "none"
    assert data["dashboard_delivery_contract"]["export_download_enabled"] is False
    assert data["surface_enablement"]["dashboard_enabled"] is False
    assert data["result_contract"]["serves_dashboard"] is False


def test_company_store_dashboard_preflight_blocks_fixture():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload["status"] == "blocked"
    assert payload["dashboard_allowed"] is False
    assert payload["objective_item"] == 13
    assert payload["surface"] == "company_store_dashboard"
    assert payload["command_effect"] == "preflight_only"
    assert payload["aggregate_privacy_contract_bound"] is True
    assert payload["review_integrity_contract_bound"] is True
    assert payload["dashboard_display_contract_bound"] is True
    assert payload["dashboard_delivery_contract_bound"] is True
    assert payload["serves_dashboard"] is False
    assert payload["creates_dashboard_view"] is False
    assert payload["queries_aggregate_signal"] is False
    assert payload["shows_single_observation"] is False
    assert payload["suppresses_negative_reviews"] is False
    assert payload["suppresses_or_hides_reviews"] is False
    assert payload["opens_public_surface"] is False
    assert payload["delivers_to_b2b"] is False
    assert payload["opens_respondent_portal"] is False
    assert payload["performs_identity_processing"] is False
    assert payload["stores_raw_detail"] is False
    assert payload["makes_retrievable"] is False
    assert payload["exports_dashboard_data"] is False
    assert payload["writes_audit_event"] is False
    assert payload["required_gates"] == [
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
    assert "aggregate signal is not available" in payload["blocking_gates"]
    assert "minimum group size is not met" in payload["blocking_gates"]
    assert "company/store dashboard surface is disabled" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "flag",
    [
        "dashboard_enabled",
        "dashboard_serving_enabled",
        "aggregate_signal_query_enabled",
        "single_observation_display_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "respondent_portal_enabled",
        "identity_processing_enabled",
        "raw_detail_escrow_enabled",
        "retrieval_enabled",
        "export_enabled",
        "ranking_enabled",
    ],
)
def test_company_store_dashboard_rejects_surface_enablement(tmp_path, flag):
    data = load_fixture()
    data["surface_enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "serves_dashboard",
        "creates_dashboard_view",
        "queries_aggregate_signal",
        "shows_single_observation",
        "suppresses_negative_reviews",
        "suppresses_or_hides_reviews",
        "opens_public_surface",
        "delivers_to_b2b",
        "opens_respondent_portal",
        "performs_identity_processing",
        "stores_raw_detail",
        "makes_retrievable",
        "exports_dashboard_data",
        "writes_audit_event",
    ],
)
def test_company_store_dashboard_rejects_blocked_result_effects(tmp_path, flag):
    data = load_fixture()
    data["result_contract"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "aggregate_signal_available",
        "minimum_group_size_met",
        "single_observation_display_enabled",
        "negative_review_suppression_enabled",
        "review_suppression_surface_enabled",
        "manipulation_response_controls_enabled",
        "manipulation_review_enabled",
        "freshness_policy_accepted",
        "stale_signal_expiry_accepted",
    ],
)
def test_company_store_dashboard_rejects_aggregate_signal_readiness(tmp_path, flag):
    data = load_fixture()
    data["aggregate_signal_request"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "flag",
    [
        "public_b2b_disclosure_policy_accepted",
        "respondent_inquiry_policy_accepted",
        "no_identity_leakage_tests_passed",
        "correction_takedown_workflow_accepted",
    ],
)
def test_company_store_dashboard_rejects_completed_disclosure_policy(tmp_path, flag):
    data = load_fixture()
    data["disclosure_policy"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["aggregate_privacy_contract", "minimum_source_count_policy_accepted"], True),
        (["aggregate_privacy_contract", "drilldown_to_source_allowed"], True),
        (["aggregate_privacy_contract", "segment_breakdown_allowed"], True),
        (["aggregate_privacy_contract", "cell_suppression_required"], False),
        (["review_integrity_contract", "favorability_neutral_processing_required"], False),
        (["review_integrity_contract", "negative_review_suppression_allowed"], True),
        (["review_integrity_contract", "respondent_self_service_suppression_allowed"], True),
        (["review_integrity_contract", "manipulation_response_controls_allowed"], True),
        (["dashboard_display_contract", "single_observation_display_allowed"], True),
        (["dashboard_display_contract", "raw_detail_display_allowed"], True),
        (["dashboard_display_contract", "identity_state_display_allowed"], True),
        (["dashboard_display_contract", "escrow_artifact_display_allowed"], True),
        (["dashboard_display_contract", "ranking_or_sorting_enabled"], True),
        (["dashboard_delivery_contract", "access_token_issued"], True),
        (["dashboard_delivery_contract", "api_serving_enabled"], True),
        (["dashboard_delivery_contract", "export_download_enabled"], True),
        (["dashboard_delivery_contract", "dashboard_snapshot_enabled"], True),
    ],
)
def test_company_store_dashboard_rejects_control_contract_weakening(tmp_path, path, value):
    data = load_fixture()
    target = data
    for item in path[:-1]:
        target = target[item]
    target[path[-1]] = value

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_company_store_dashboard_blocks_missing_required_gate(tmp_path):
    data = load_fixture()
    data["required_gates"] = [item for item in data["required_gates"] if item != "MIN_SOURCE_COUNT_POLICY"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing required gates: MIN_SOURCE_COUNT_POLICY" in payload["blocking_gates"]


def test_company_store_dashboard_blocks_missing_blocked_until_gate(tmp_path):
    data = load_fixture()
    data["blocked_until"] = [item for item in data["blocked_until"] if item["gate"] != "NO_ESCROW_ARTIFACT_DISPLAY_TESTS"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing blocked_until gates: NO_ESCROW_ARTIFACT_DISPLAY_TESTS" in payload["blocking_gates"]


def test_company_store_dashboard_blocks_missing_forbidden_output(tmp_path):
    data = load_fixture()
    data["forbidden_outputs"] = [item for item in data["forbidden_outputs"] if item != "escrow_key_material"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing forbidden outputs: escrow_key_material" in payload["blocking_gates"]


def test_company_store_dashboard_blocks_missing_withheld_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["withheld_outputs"] = [
        item for item in data["output_contract"]["withheld_outputs"] if item != "escrow_ciphertext"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "missing withheld outputs: escrow_ciphertext" in payload["blocking_gates"]


def test_company_store_dashboard_rejects_requested_forbidden_output(tmp_path):
    data = load_fixture()
    data["output_contract"]["requested_outputs"].append("raw_source_material")

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_company_store_dashboard_rejects_active_status(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_company_store_dashboard_rejects_schema_errors_without_echo(tmp_path):
    data = load_fixture()
    data["dashboard_subject"]["subject_type"] = "raw-private-subject"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-subject" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


def test_company_store_dashboard_blocks_raw_marker_without_echo(tmp_path):
    data = load_fixture()
    data["blocked_until"][0]["reason"] = "contact user@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 0
    assert "company/store dashboard request contains raw markers" in payload["blocking_gates"]
    assert "user@example.com" not in json.dumps(payload)
