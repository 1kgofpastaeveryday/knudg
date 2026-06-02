import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


GATE_ARTIFACTS = [
    {
        "name": "m3:gates",
        "schema": "schemas/m3-retrieval-gates.schema.json",
        "fixture": "fixtures/m3-retrieval-gates.draft.json",
        "validator": "scripts/validate_m3_gates.py",
    },
    {
        "name": "review:gates",
        "schema": "schemas/review-ops-gates.schema.json",
        "fixture": "fixtures/review-ops-gates.draft.json",
        "validator": "scripts/validate_review_ops_gates.py",
    },
    {
        "name": "circuit:gates",
        "schema": "schemas/circuit-gates.schema.json",
        "fixture": "fixtures/circuit-gates.draft.json",
        "validator": "scripts/validate_circuit_gates.py",
    },
    {
        "name": "runbook:manifest",
        "schema": "schemas/runbook-command-manifest.schema.json",
        "fixture": "fixtures/runbook-command-manifest.draft.json",
        "validator": "scripts/validate_runbook_manifest.py",
    },
    {
        "name": "launch:gates",
        "schema": "schemas/launch-gate-manifest.schema.json",
        "fixture": "fixtures/launch-gate-manifest.draft.json",
        "validator": "scripts/validate_launch_gate_manifest.py",
    },
    {
        "name": "intake:gates",
        "schema": "schemas/intake-safety-gate.schema.json",
        "fixture": "fixtures/intake-safety-gate.draft.json",
        "validator": "scripts/validate_intake_safety_gate.py",
    },
    {
        "name": "auth:gates",
        "schema": "schemas/auth-verifier-gate.schema.json",
        "fixture": "fixtures/auth-verifier-gate.draft.json",
        "validator": "scripts/validate_auth_verifier_gate.py",
    },
    {
        "name": "consent:gates",
        "schema": "schemas/consent-revocation-gate.schema.json",
        "fixture": "fixtures/consent-revocation-gate.draft.json",
        "validator": "scripts/validate_consent_revocation_gate.py",
    },
    {
        "name": "tns:audit",
        "schema": "schemas/trust-and-safety-audit-v0.schema.json",
        "fixture": "fixtures/trust-and-safety-audit.draft.json",
        "validator": "scripts/validate_trust_and_safety_audit.py",
    },
    {
        "name": "experience:surfaces",
        "schema": "schemas/experience-surface-gates-v0.schema.json",
        "fixture": "fixtures/experience-surface-gates.draft.json",
        "validator": "scripts/validate_experience_surface_gates.py",
    },
    {
        "name": "public:candidate-conversion",
        "schema": "schemas/public-candidate-conversion-request-v0.schema.json",
        "fixture": "fixtures/public-candidate-conversion.blocked.json",
        "validator": "scripts/validate_public_candidate_conversion.py",
    },
    {
        "name": "b2b:respondent-portal",
        "schema": "schemas/b2b-respondent-portal-request-v0.schema.json",
        "fixture": "fixtures/b2b-respondent-portal.blocked.json",
        "validator": "scripts/validate_b2b_respondent_portal.py",
    },
    {
        "name": "abuse:identity",
        "schema": "schemas/abuse-identity-lane-v0.schema.json",
        "fixture": "fixtures/abuse-identity-lane.draft.json",
        "validator": "scripts/validate_abuse_identity_lane.py",
    },
    {
        "name": "abuse:identity-enforcement",
        "schema": "schemas/abuse-identity-enforcement-request-v0.schema.json",
        "fixture": "fixtures/abuse-identity-enforcement.blocked.json",
        "validator": "scripts/validate_abuse_identity_enforcement.py",
    },
    {
        "name": "raw:detail-escrow",
        "schema": "schemas/raw-detail-escrow-request-v0.schema.json",
        "fixture": "fixtures/raw-detail-escrow.blocked.json",
        "validator": "scripts/validate_raw_detail_escrow.py",
    },
    {
        "name": "dashboard:company-store",
        "schema": "schemas/company-store-dashboard-request-v0.schema.json",
        "fixture": "fixtures/company-store-dashboard.blocked.json",
        "validator": "scripts/validate_company_store_dashboard.py",
    },
]


FUTURE_SURFACE_TEST_SCRIPTS = {
    "experience:activation": ["tests/test_experience_surface_activation.py"],
    "experience:storage": [
        "tests/test_experience_storage_record.py",
        "tests/test_redacted_experience_storage_migration.py",
    ],
    "public:exposure": ["tests/test_public_exposure_contract.py"],
    "candidate:facets": ["tests/test_candidate_payload_facets.py"],
}

FUTURE_SURFACE_ONLY_TESTS = [
    "tests/test_public_candidate_conversion.py",
    "tests/test_b2b_respondent_portal.py",
    "tests/test_abuse_identity_enforcement.py",
    "tests/test_raw_detail_escrow.py",
    "tests/test_company_store_dashboard.py",
    "tests/test_abuse_identity_lane_schema.py",
]


def test_gate_fixtures_have_schema_validator_and_npm_script():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    for item in GATE_ARTIFACTS:
        assert (ROOT / item["schema"]).exists(), item
        assert (ROOT / item["fixture"]).exists(), item
        assert (ROOT / item["validator"]).exists(), item
        assert item["name"] in scripts
        assert item["validator"] in scripts[item["name"]]
        assert item["fixture"] in scripts[item["name"]]


def test_gates_all_script_includes_all_gate_scripts():
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    gates_all = scripts["gates:all"]
    for item in GATE_ARTIFACTS:
        assert f"npm run {item['name']}" in gates_all
    for name in FUTURE_SURFACE_TEST_SCRIPTS:
        assert f"npm run {name}" in gates_all
    assert "npm run wedge:evidence -- validate --input fixtures/wedge-evidence.sample.json" in gates_all


def test_future_surface_package_scripts_cover_expected_tests():
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    future_surface = scripts["future-surface:leaks"]
    for name, expected_tests in FUTURE_SURFACE_TEST_SCRIPTS.items():
        assert name in scripts
        for expected_test in expected_tests:
            assert expected_test in scripts[name]
            assert expected_test in future_surface
    for expected_test in FUTURE_SURFACE_ONLY_TESTS:
        assert expected_test in future_surface


def test_all_gate_validators_pass():
    for item in GATE_ARTIFACTS:
        result = subprocess.run(
            [sys.executable, str(ROOT / item["validator"]), "--input", str(ROOT / item["fixture"])],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_wedge_sample_fixture_validates():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "wedge_evidence.py"), "validate", "--input", str(ROOT / "fixtures" / "wedge-evidence.sample.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
