import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "trust-and-safety-audit-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "trust-and-safety-audit.draft.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "trust-and-safety-audit.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_trust_and_safety_audit.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def test_trust_and_safety_audit_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
    assert data["real_identity_processing_enabled"] is False
    assert data["operational_enablement"]["real_ban_operations_enabled"] is False
    assert data["operational_enablement"]["b2b_respondent_portal_enabled"] is False
    assert data["operational_enablement"]["company_store_dashboard_enabled"] is False
    assert "career_private" in data["covered_domains"]
    assert data["synthetic_audit_event_contract"]["case_id"].startswith("case:")
    assert data["synthetic_audit_event_contract"]["decision_digest"].startswith("sha256:")
    assert {event["event_type"] for event in data["synthetic_events"]} == set(data["event_types"])
    assert data["identity_controls"]["subject_rows"] == "none"


def test_trust_and_safety_audit_draft_validates_disabled():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {"status": "ok", "real_identity_processing_enabled": False}


def test_trust_and_safety_audit_blocks_missing_event_type(tmp_path):
    data = load_fixture()
    data["event_types"] = [item for item in data["event_types"] if item != "account_banned"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing event types: account_banned" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_missing_account_rate_limited_event_type(tmp_path):
    data = load_fixture()
    data["event_types"] = [item for item in data["event_types"] if item != "account_rate_limited"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing event types: account_rate_limited" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_missing_covered_domain(tmp_path):
    data = load_fixture()
    data["covered_domains"] = [item for item in data["covered_domains"] if item != "career_private"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing covered domains: career_private" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_missing_forbidden_disclosure(tmp_path):
    data = load_fixture()
    data["forbidden_disclosures"] = [item for item in data["forbidden_disclosures"] if item != "business_dashboard"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing forbidden disclosures: business_dashboard" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_missing_exact_future_surface_disclosure(tmp_path):
    data = load_fixture()
    data["forbidden_disclosures"] = [item for item in data["forbidden_disclosures"] if item != "b2b_respondent_portal"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing forbidden disclosures: b2b_respondent_portal" in payload["blocking_gates"]


def test_trust_and_safety_audit_rejects_real_identity_processing(tmp_path):
    data = load_fixture()
    data["real_identity_processing_enabled"] = True
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_trust_and_safety_audit_rejects_real_ban_operations(tmp_path):
    data = load_fixture()
    data["operational_enablement"]["real_ban_operations_enabled"] = True
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_trust_and_safety_audit_rejects_b2b_respondent_portal_enablement(tmp_path):
    data = load_fixture()
    data["operational_enablement"]["b2b_respondent_portal_enabled"] = True
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_trust_and_safety_audit_rejects_raw_email_in_synthetic_audit_event(tmp_path):
    data = load_fixture()
    data["synthetic_audit_event_contract"]["actor_id"] = "actor:user@example.com"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_trust_and_safety_audit_blocks_raw_marker_in_synthetic_audit_event(tmp_path):
    data = load_fixture()
    data["synthetic_audit_event_contract"]["subject_ref"] = "subject-ref:localhost"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "synthetic audit event contains raw markers: localhost" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_missing_synthetic_event(tmp_path):
    data = load_fixture()
    data["synthetic_events"] = [event for event in data["synthetic_events"] if event["event_type"] != "account_banned"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing synthetic events: account_banned" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_missing_account_rate_limited_synthetic_event(tmp_path):
    data = load_fixture()
    data["synthetic_events"] = [
        event for event in data["synthetic_events"] if event["event_type"] != "account_rate_limited"
    ]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing synthetic events: account_rate_limited" in payload["blocking_gates"]


def test_trust_and_safety_audit_blocks_raw_marker_in_synthetic_event(tmp_path):
    data = load_fixture()
    data["synthetic_events"][0]["subject_ref"] = "synthetic-subject:localhost"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "case_opened synthetic event contains raw markers: localhost" in payload["blocking_gates"]


@pytest.mark.parametrize("flag", [
    "real_ban_operations_enabled",
    "respondent_inquiry_enabled",
    "b2b_dashboard_enabled",
    "raw_detail_escrow_enabled",
    "public_candidate_publication_enabled",
    "public_candidate_conversion_enabled",
    "b2b_respondent_portal_enabled",
    "company_store_dashboard_enabled",
])
def test_trust_and_safety_audit_rejects_any_operational_enablement(tmp_path, flag):
    data = load_fixture()
    data["operational_enablement"][flag] = True
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_trust_and_safety_audit_schema_errors_do_not_echo_raw_values(tmp_path):
    data = load_fixture()
    data["covered_domains"] = ["raw-private-value-123"]
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


def test_trust_and_safety_audit_accepted_requires_no_blockers(tmp_path):
    data = load_fixture()
    data["status"] = "accepted"
    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "accepted trust-and-safety audit gate must not have blockers" in payload["blocking_gates"]
