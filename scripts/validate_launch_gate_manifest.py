#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "launch-gate-manifest.schema.json"
REQUIRED_GATES = {
    "PR-001",
    "PR-002",
    "PR-003",
    "PR-004",
    "PR-005",
    "PR-005A",
    "PR-006",
    "PR-007",
    "non_synthetic_body_persistence_gate",
}
PRODUCTION_DEPENDENCIES = {
    "PR-001": {"M1"},
    "PR-002": {"non_synthetic_body_persistence_gate"},
    "PR-003": {"M1", "M2"},
    "PR-004": {"production"},
    "PR-005": {"public-pilot"},
    "PR-005A": {"public-docs"},
    "PR-006": {"non_synthetic_body_persistence_gate"},
    "non_synthetic_body_persistence_gate": {"M1"},
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate_failures(data):
    failures = []
    seen = set()
    duplicates = []
    gates = {}
    for gate in data["gates"]:
        gate_id = gate["gate_id"]
        if gate_id in seen:
            duplicates.append(gate_id)
        seen.add(gate_id)
        gates[gate_id] = gate
    if duplicates:
        failures.append(f"duplicate gates: {', '.join(sorted(set(duplicates)))}")
    missing = sorted(REQUIRED_GATES - set(gates))
    if missing:
        failures.append(f"missing gates: {', '.join(missing)}")

    if data["status"] == "accepted":
        for gate in data["gates"]:
            if gate["status"] != "open":
                failures.append(f"{gate['gate_id']} is not open in accepted manifest")
            if not gate["evidence_refs"]:
                failures.append(f"{gate['gate_id']} lacks evidence refs in accepted manifest")
            if not gate["ci_result_refs"]:
                failures.append(f"{gate['gate_id']} lacks CI refs in accepted manifest")
            if gate["authority"]["accepted_revision"] is None:
                failures.append(f"{gate['gate_id']} lacks accepted authority revision")

    for gate_id, required_dependents in PRODUCTION_DEPENDENCIES.items():
        gate = gates.get(gate_id)
        if not gate:
            continue
        missing_dependents = sorted(required_dependents - set(gate["blocking_dependents"]))
        if missing_dependents:
            failures.append(f"{gate_id} missing blocking dependents: {', '.join(missing_dependents)}")

    body_gate = gates.get("non_synthetic_body_persistence_gate")
    if body_gate and body_gate["status"] == "open":
        for prerequisite in ["PR-001", "PR-002", "PR-003", "PR-004", "PR-006"]:
            if gates.get(prerequisite, {}).get("status") != "open":
                failures.append(f"non_synthetic_body_persistence_gate open while {prerequisite} is not open")

    for gate in data["gates"]:
        if gate["status"] == "open" and gate["public_safe_status_label"] != "open_evidence_current":
            failures.append(f"{gate['gate_id']} open gate must use open_evidence_current public label")
        if gate["status"] != "open" and gate["public_safe_status_label"] == "open_evidence_current":
            failures.append(f"{gate['gate_id']} closed gate cannot use open_evidence_current public label")
        if gate["status"] == "closed" and gate["review_expires_at"] is not None:
            failures.append(f"{gate['gate_id']} closed gate must not carry a review expiry")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate Knudg launch gate manifest fixtures.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        print(json.dumps({"status": "rejected", "errors": [error.message for error in errors]}, sort_keys=True))
        return 2
    failures = gate_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    open_gates = sorted(gate["gate_id"] for gate in data["gates"] if gate["status"] == "open")
    closed_gates = sorted(gate["gate_id"] for gate in data["gates"] if gate["status"] == "closed")
    print(json.dumps({"status": "ok", "open_gates": open_gates, "closed_gates": closed_gates}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
