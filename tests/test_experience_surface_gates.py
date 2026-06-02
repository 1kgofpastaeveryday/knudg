import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "experience-surface-gates-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "experience-surface-gates.draft.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def write_json(tmp_path, value):
    path = tmp_path / "experience-surface-gates.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_experience_surface_gates.py"), "--input", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def test_experience_surface_gates_fixture_matches_schema():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = load_fixture()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)
    surfaces = {item["surface"]: item for item in data["surfaces"]}
    assert surfaces["actual_experience_storage"]["objective_item"] == 8
    assert surfaces["company_store_dashboard"]["enablement"]["dashboard_enabled"] is False


def test_experience_surface_gates_draft_validates_blocked():
    code, payload = run_validator(FIXTURE)
    assert code == 0
    assert payload == {"status": "ok", "surface_count": 6}


def test_experience_surface_gates_rejects_enabled_dashboard(tmp_path):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == "company_store_dashboard":
            surface["enablement"]["dashboard_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


@pytest.mark.parametrize("flag", [
    "real_data_ingest_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "identity_processing_enabled",
    "raw_detail_escrow_enabled",
    "dashboard_enabled",
])
def test_experience_surface_gates_rejects_any_enabled_flag(tmp_path, flag):
    data = load_fixture()
    data["surfaces"][0]["enablement"][flag] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_experience_surface_gates_blocks_missing_surface(tmp_path):
    data = load_fixture()
    data["surfaces"] = [item for item in data["surfaces"] if item["surface"] != "b2b_respondent_portal"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "missing surfaces: b2b_respondent_portal" in payload["blocking_gates"]


def test_experience_surface_gates_blocks_duplicate_surface_key(tmp_path):
    data = load_fixture()
    duplicate = dict(data["surfaces"][0])
    duplicate["status"] = "accepted"
    data["surfaces"].append(duplicate)

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "duplicate surfaces: actual_experience_storage" in payload["blocking_gates"]


def test_experience_surface_gates_blocks_missing_required_gate(tmp_path):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == "abuse_identity_ban_operations":
            surface["required_gates"] = [
                gate for gate in surface["required_gates"] if gate["gate"] != "APPEAL_RECOVERY_PATH"
            ]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert "abuse_identity_ban_operations missing gates: APPEAL_RECOVERY_PATH" in payload["blocking_gates"]


@pytest.mark.parametrize("surface_name,forbidden_output", [
    ("actual_experience_storage", "private_selection_status"),
    ("actual_experience_storage", "staff_identity"),
    ("public_candidate_conversion", "non_public_operational_detail"),
    ("b2b_respondent_portal", "raw_source_material"),
    ("b2b_respondent_portal", "source_metadata"),
    ("b2b_respondent_portal", "raw_moderation_evidence"),
    ("b2b_respondent_portal", "respondent_visible_user_attribution"),
    ("abuse_identity_ban_operations", "reidentification_hint"),
    ("abuse_identity_ban_operations", "raw_identity_values"),
    ("abuse_identity_ban_operations", "subject_row"),
    ("abuse_identity_ban_operations", "raw_source_material"),
    ("abuse_identity_ban_operations", "source_metadata"),
    ("abuse_identity_ban_operations", "raw_moderation_evidence"),
    ("abuse_identity_ban_operations", "match_status"),
    ("abuse_identity_ban_operations", "account_identifier"),
    ("abuse_identity_ban_operations", "private_selection_status"),
    ("raw_detail_escrow", "device_or_network_signal"),
    ("raw_detail_escrow", "protected_fingerprint"),
    ("raw_detail_escrow", "private_selection_status"),
    ("raw_detail_escrow", "staff_identity"),
    ("raw_detail_escrow", "source_metadata"),
    ("raw_detail_escrow", "raw_moderation_evidence"),
    ("raw_detail_escrow", "escrow_ciphertext"),
    ("raw_detail_escrow", "escrow_handle"),
    ("raw_detail_escrow", "escrow_key_material"),
    ("raw_detail_escrow", "reviewer_private_note"),
    ("raw_detail_escrow", "non_public_operational_detail"),
    ("company_store_dashboard", "device_or_network_signal"),
    ("company_store_dashboard", "source_metadata"),
    ("company_store_dashboard", "raw_moderation_evidence"),
    ("company_store_dashboard", "escrow_ciphertext"),
    ("company_store_dashboard", "escrow_handle"),
    ("company_store_dashboard", "escrow_key_material"),
    ("company_store_dashboard", "account_identifier"),
    ("company_store_dashboard", "match_status"),
    ("company_store_dashboard", "individual_claim"),
    ("company_store_dashboard", "single_observation_detail"),
    ("company_store_dashboard", "reviewer_private_note"),
    ("company_store_dashboard", "non_public_operational_detail"),
])
def test_experience_surface_gates_blocks_missing_fixture_forbidden_output(tmp_path, surface_name, forbidden_output):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == surface_name:
            surface["forbidden_outputs"] = [item for item in surface["forbidden_outputs"] if item != forbidden_output]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert f"{surface_name} missing forbidden outputs: {forbidden_output}" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "gate",
    [
        "AUTHORIZATION_ROLE_MODEL",
        "HIGH_RISK_REVIEW_POLICY",
        "IDEMPOTENCY_WRITE_BEFORE_EFFECT",
        "ANTI_ENUMERATION_CONTRACT",
        "IDENTITY_MINIMIZATION_POLICY",
        "AUDIT_DURABILITY",
        "NO_IDENTITY_DISCLOSURE_NEGATIVE_TESTS",
        "RAW_IDENTITY_RETENTION_PURGE_POLICY",
    ],
)
def test_experience_surface_gates_blocks_missing_abuse_identity_control_gate(tmp_path, gate):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == "abuse_identity_ban_operations":
            surface["required_gates"] = [item for item in surface["required_gates"] if item["gate"] != gate]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert f"abuse_identity_ban_operations missing gates: {gate}" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "gate",
    [
        "ESCROW_TTL_POLICY",
        "REVIEWER_ACCESS_POLICY",
        "NO_RAW_ECHO_NEGATIVE_TESTS",
        "KEY_PROFILE_ACCEPTED",
        "RAW_DETAIL_PURPOSE_BINDING",
        "CRYPTOGRAPHIC_ENVELOPE_PROFILE",
        "ACCESS_LEASE_POLICY",
        "RESTORE_BACKUP_PURGE_POLICY",
        "AUDIT_DIGEST_ONLY_POLICY",
    ],
)
def test_experience_surface_gates_blocks_missing_raw_detail_control_gate(tmp_path, gate):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == "raw_detail_escrow":
            surface["required_gates"] = [item for item in surface["required_gates"] if item["gate"] != gate]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert f"raw_detail_escrow missing gates: {gate}" in payload["blocking_gates"]


@pytest.mark.parametrize(
    "gate",
    [
        "MIN_SOURCE_COUNT_POLICY",
        "MANIPULATION_RESISTANCE_POLICY",
        "NO_SINGLE_OBSERVATION_DISPLAY_TESTS",
        "NO_SUPPRESSION_SURFACE_TESTS",
        "CORRECTION_TAKEDOWN_POLICY",
        "AGGREGATE_PRIVACY_THRESHOLD_POLICY",
        "FAIR_REVIEW_PRESENTATION_POLICY",
        "DASHBOARD_DISPLAY_POLICY",
        "NO_ESCROW_ARTIFACT_DISPLAY_TESTS",
        "DASHBOARD_EXPORT_DOWNLOAD_POLICY",
    ],
)
def test_experience_surface_gates_blocks_missing_company_dashboard_control_gate(tmp_path, gate):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == "company_store_dashboard":
            surface["required_gates"] = [item for item in surface["required_gates"] if item["gate"] != gate]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 3
    assert f"company_store_dashboard missing gates: {gate}" in payload["blocking_gates"]


def test_experience_surface_gates_rejects_abuse_identity_processing_enablement(tmp_path):
    data = load_fixture()
    for surface in data["surfaces"]:
        if surface["surface"] == "abuse_identity_ban_operations":
            surface["enablement"]["identity_processing_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"


def test_experience_surface_gates_schema_errors_do_not_echo_raw_values(tmp_path):
    data = load_fixture()
    data["surfaces"][0]["forbidden_outputs"] = ["raw-private-value-123"]

    code, payload = run_validator(write_json(tmp_path, data))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "raw-private-value-123" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "enum"


@pytest.mark.parametrize(
    "objective_item,fixture_name,validator_script",
    [
        (9, "public-candidate-conversion.blocked.json", "validate_public_candidate_conversion.py"),
        (10, "b2b-respondent-portal.blocked.json", "validate_b2b_respondent_portal.py"),
        (11, "abuse-identity-enforcement.blocked.json", "validate_abuse_identity_enforcement.py"),
        (12, "raw-detail-escrow.blocked.json", "validate_raw_detail_escrow.py"),
        (13, "company-store-dashboard.blocked.json", "validate_company_store_dashboard.py"),
    ],
)
def test_future_public_b2b_identity_raw_dashboard_surfaces_remain_blocked_preflight(objective_item, fixture_name, validator_script):
    fixture_path = ROOT / "fixtures" / fixture_name
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert data["request_class"] == "preflight_only"
    assert data["objective_item"] == objective_item
    assert data["status"] == "blocked"
    assert data["required_gates"]
    assert data["blocked_until"]

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / validator_script), "--input", str(fixture_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["objective_item"] == objective_item
    assert payload["command_effect"] == "preflight_only"
    for flag in [
        "opens_public_surface",
        "delivers_to_b2b",
        "serves_dashboard",
        "stores_raw_detail",
        "performs_identity_processing",
        "creates_public_card",
        "opens_portal",
        "creates_dashboard_view",
        "creates_encrypted_blob",
        "enforces_ban",
    ]:
        if flag in payload:
            assert payload[flag] is False
