import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "experience-surface-activation-request-v0.schema.json"
FIXTURE = ROOT / "fixtures" / "experience-surface-activation.actual-storage.blocked.json"
GATES = ROOT / "fixtures" / "experience-surface-gates.draft.json"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run_validator(path, gates=GATES):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_experience_surface_activation.py"),
            "--input",
            str(path),
            "--gates",
            str(gates),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def accepted_gates():
    gates = load_json(GATES)
    gates["status"] = "accepted"
    for surface in gates["surfaces"]:
        surface["status"] = "accepted"
    return gates


def accepted_request():
    request = load_json(FIXTURE)
    for evidence in request["gate_evidence"]:
        evidence["status"] = "accepted"
    return request


def test_experience_surface_activation_fixture_matches_schema():
    schema = load_json(SCHEMA)
    Draft202012Validator(schema).validate(load_json(FIXTURE))


def test_actual_experience_storage_activation_preflight_blocks_current_draft_gates():
    code, payload = run_validator(FIXTURE)
    assert code == 3
    assert payload["status"] == "blocked"
    assert payload["activation_allowed"] is False
    assert payload["requested_surface"] == "actual_experience_storage"
    assert payload["command_effect"] == "preflight_only"
    assert payload["writes_real_data"] is False
    assert payload["creates_card"] is False
    assert payload["indexes"] is False
    assert payload["opens_public_surface"] is False
    assert payload["performs_identity_processing"] is False
    assert payload["stores_raw_detail"] is False
    assert payload["serves_dashboard"] is False
    assert payload["applied_enablement"]["real_data_ingest_enabled"] is False
    assert any("unaccepted gate evidence" in blocker for blocker in payload["blocking_gates"])
    assert "experience surface gate manifest is not accepted" in payload["blocking_gates"]


def test_experience_surface_activation_allows_only_when_manifest_and_evidence_are_accepted(tmp_path):
    gates_path = write_json(tmp_path, "accepted-gates.json", accepted_gates())
    request_path = write_json(tmp_path, "accepted-request.json", accepted_request())

    code, payload = run_validator(request_path, gates_path)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["activation_allowed"] is True
    assert payload["applied_enablement"]["real_data_ingest_enabled"] is False
    assert payload["writes_real_data"] is False


def test_experience_surface_activation_rejects_wrong_enablement_flag(tmp_path):
    request = accepted_request()
    request["requested_enablement"]["real_data_ingest_enabled"] = False
    request["requested_enablement"]["dashboard_enabled"] = True

    code, payload = run_validator(write_json(tmp_path, "wrong-flag.json", request), write_json(tmp_path, "accepted-gates.json", accepted_gates()))
    assert code == 3
    assert "actual_experience_storage requested wrong enablement flags" in payload["blocking_gates"]


def test_experience_surface_activation_blocks_forbidden_outputs(tmp_path):
    request = accepted_request()
    request["output_contract"]["requested_outputs"].append("submitter_identity")

    code, payload = run_validator(write_json(tmp_path, "forbidden-output.json", request), write_json(tmp_path, "accepted-gates.json", accepted_gates()))
    assert code == 3
    assert "actual_experience_storage requests forbidden outputs: submitter_identity" in payload["blocking_gates"]


def test_experience_surface_activation_blocks_forbidden_allowed_outputs(tmp_path):
    request = accepted_request()
    request["output_contract"]["allowed_outputs"].append("submitter_identity")

    code, payload = run_validator(write_json(tmp_path, "forbidden-allowed-output.json", request), write_json(tmp_path, "accepted-gates.json", accepted_gates()))
    assert code == 3
    assert "actual_experience_storage allows forbidden outputs: submitter_identity" in payload["blocking_gates"]


def test_experience_surface_activation_blocks_requested_outputs_not_allowed(tmp_path):
    request = accepted_request()
    request["output_contract"]["allowed_outputs"] = ["redacted_subject_name"]

    code, payload = run_validator(write_json(tmp_path, "requested-not-allowed.json", request), write_json(tmp_path, "accepted-gates.json", accepted_gates()))
    assert code == 3
    assert "actual_experience_storage requested outputs are not allowed: redacted_experience_summary" in payload["blocking_gates"]


def test_experience_surface_activation_schema_accepts_escrow_forbidden_output_vocab(tmp_path):
    request = accepted_request()
    request["output_contract"]["allowed_outputs"].append("escrow_ciphertext")

    code, payload = run_validator(write_json(tmp_path, "escrow-vocab.json", request), write_json(tmp_path, "accepted-gates.json", accepted_gates()))
    assert code == 3
    assert payload["status"] == "blocked"
    assert "actual_experience_storage allows globally forbidden outputs: escrow_ciphertext" in payload["blocking_gates"]


def test_experience_surface_activation_schema_errors_do_not_echo_raw_values(tmp_path):
    request = accepted_request()
    request["request_id"] = "bad request with spaces"

    code, payload = run_validator(write_json(tmp_path, "schema-error.json", request))
    assert code == 2
    assert payload["status"] == "rejected"
    assert "bad request with spaces" not in json.dumps(payload)
    assert payload["errors"][0]["validator"] == "pattern"


def test_experience_surface_activation_rejects_raw_markers_without_echo(tmp_path):
    request = accepted_request()
    request["gate_evidence"][0]["evidence_ref"] = "C:\\Users\\private\\token"

    code, payload = run_validator(write_json(tmp_path, "raw-marker.json", request))
    assert code == 2
    assert payload["status"] == "rejected"
    serialized = json.dumps(payload)
    assert "C:\\Users" not in serialized
    assert "token" not in serialized
