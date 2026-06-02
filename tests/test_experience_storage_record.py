import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "experience-storage-record-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "experience-storage-record.career-private.redacted.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "experience-storage-record.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_experience_storage_record.py"), "--input", str(path)],
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


def test_experience_storage_record_fixture_matches_schema_with_private_storage_enabled():
    data = load_fixture()
    validator().validate(data)
    assert data["domain"] == "career_private"
    assert data["subject"]["type"] == "company"
    assert data["subject"]["entity_name_public_allowed"] is True
    assert data["subject"]["private_person_refs"] == []
    assert data["storage_state"]["mode"] == "stored_private_redacted"
    assert data["storage_state"]["activation_required"] is False
    assert data["storage_state"]["database_write_enabled"] is True
    assert data["storage_state"]["record_visible_to_retrieval"] is False
    assert data["consent"]["private_retention_consent_proof"]["consent_id"] == "11111111-1111-4111-8111-111111111111"
    assert data["consent"]["private_retention_consent_proof"]["handoff_digest"].startswith("sha256:")
    assert data["source_controls"]["raw_source_retention"] == "none"
    assert data["source_controls"]["raw_detail_escrow_ref"] is None
    assert data["source_controls"]["raw_source_available_to_model"] is False
    assert data["surface_controls"]["retrieval_policy"] == "explicit_or_contextual"
    assert data["surface_controls"]["public_candidate_conversion_enabled"] is False
    assert data["surface_controls"]["b2b_delivery_enabled"] is False
    assert data["surface_controls"]["dashboard_enabled"] is False


def test_experience_storage_record_validator_accepts_redacted_fixture():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {
        "status": "ok",
        "domain": "career_private",
        "command_effect": "database_insert_ready",
        "database_write_enabled": True,
        "record_visible_to_retrieval": False,
    }


@pytest.mark.parametrize(
    "surface_flag",
    [
        "public_candidate_conversion_enabled",
        "public_serving_enabled",
        "b2b_delivery_enabled",
        "identity_processing_enabled",
        "raw_detail_escrow_enabled",
        "dashboard_enabled",
    ],
)
def test_experience_storage_record_rejects_future_surface_enablement(tmp_path, surface_flag):
    data = load_fixture()
    data["surface_controls"][surface_flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize(
    "redaction_flag",
    ["private_selection_status_present", "raw_quotes_present", "exact_dates_present", "private_person_present"],
)
def test_experience_storage_record_blocks_private_detail_flags(tmp_path, redaction_flag):
    data = load_fixture()
    data["redacted_experience"][redaction_flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_experience_storage_record_blocks_pre_storage_database_write_enablement(tmp_path):
    data = load_fixture()
    data["storage_state"]["mode"] = "contract_only_pre_storage"
    data["storage_state"]["activation_required"] = True
    data["storage_state"]["database_write_enabled"] = True
    data["consent"]["private_retention_consent_proof"] = None

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "experience storage record cannot enable database writes before activation" in payload["blocking_gates"]


def test_experience_storage_record_blocks_stored_record_without_private_retention_consent(tmp_path):
    data = load_fixture()
    data["consent"]["private_retention_consent_proof"] = None

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "stored private redacted records require private retention consent proof" in payload["blocking_gates"]


def test_experience_storage_record_rejects_private_person_refs(tmp_path):
    data = load_fixture()
    data["subject"]["private_person_refs"] = ["person:interviewer"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_experience_storage_record_blocks_missing_disallowed_detail_class(tmp_path):
    data = load_fixture()
    data["redacted_experience"]["disallowed_detail_classes"] = [
        item
        for item in data["redacted_experience"]["disallowed_detail_classes"]
        if item != "selection_status"
    ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing disallowed detail classes: selection_status" in payload["blocking_gates"]


def test_experience_storage_record_blocks_raw_marker_without_echo(tmp_path):
    data = load_fixture()
    data["redacted_experience"]["summary"] = "Candidate details included user@example.com"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "experience storage record contains raw markers" in payload["blocking_gates"]
    assert "user@example.com" not in json.dumps(payload)


def test_experience_storage_record_blocks_japanese_exact_date_without_echo(tmp_path):
    data = load_fixture()
    data["redacted_experience"]["summary"] = "The redacted record still includes 2026年6月1日 as an exact private date."

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "experience storage record contains raw markers" in payload["blocking_gates"]
    assert "2026年6月1日" not in json.dumps(payload, ensure_ascii=False)


def test_experience_storage_record_rejects_place_domain_with_company_subject(tmp_path):
    data = load_fixture()
    data["domain"] = "place_service_experience"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "place_service_experience records must use place or service subject" in payload["blocking_gates"]


def test_experience_storage_record_schema_errors_do_not_echo_raw_values(tmp_path):
    data = load_fixture()
    data["domain"] = "raw-private-value-123"

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"
