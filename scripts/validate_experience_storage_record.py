#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "experience-storage-record-v0.schema.json"
REQUIRED_DISALLOWED_DETAIL_CLASSES = {
    "selection_status",
    "private_message",
    "private_person_identity",
    "exact_timestamp",
    "raw_source_material",
    "protected_identity_signal",
    "device_or_network_signal",
}
FALSE_SURFACE_FLAGS = {
    "public_candidate_conversion_enabled",
    "public_serving_enabled",
    "b2b_delivery_enabled",
    "identity_processing_enabled",
    "raw_detail_escrow_enabled",
    "dashboard_enabled",
}
FALSE_REDACTION_FLAGS = {
    "private_selection_status_present",
    "raw_quotes_present",
    "exact_dates_present",
    "private_person_present",
}
RAW_MARKERS = (
    re.compile(r"@", re.IGNORECASE),
    re.compile(r"\bhttps?://", re.IGNORECASE),
    re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1)\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\\\\[A-Za-z0-9_.-]+\\"),
    re.compile(r"\b20\d{2}-\d{2}-\d{2}\b"),
    re.compile(r"\b20\d{2}[/-]\d{1,2}[/-]\d{1,2}\b"),
    re.compile(r"20\d{2}年\d{1,2}月\d{1,2}日"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"\b0\d{1,4}[- ]\d{1,4}[- ]\d{3,4}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential|private[_ -]?key)\b", re.IGNORECASE),
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sanitized_schema_errors(errors):
    return [{"path": "/".join(str(item) for item in error.path), "validator": error.validator} for error in errors]


def contains_raw_marker(data):
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return any(pattern.search(text) for pattern in RAW_MARKERS)


def gate_failures(data):
    failures = []
    if data["domain"] == "career_private" and data["subject"]["type"] != "company":
        failures.append("career_private records must use company subject")
    if data["domain"] == "place_service_experience" and data["subject"]["type"] not in {"place", "service"}:
        failures.append("place_service_experience records must use place or service subject")

    missing_detail_classes = sorted(
        REQUIRED_DISALLOWED_DETAIL_CLASSES - set(data["redacted_experience"]["disallowed_detail_classes"])
    )
    if missing_detail_classes:
        failures.append(f"missing disallowed detail classes: {', '.join(missing_detail_classes)}")

    enabled_redaction_flags = sorted(
        flag for flag in FALSE_REDACTION_FLAGS if data["redacted_experience"][flag]
    )
    if enabled_redaction_flags:
        failures.append(f"redacted experience contains private detail flags: {', '.join(enabled_redaction_flags)}")

    enabled_surface_flags = sorted(flag for flag in FALSE_SURFACE_FLAGS if data["surface_controls"][flag])
    if enabled_surface_flags:
        failures.append(f"experience storage record enables future surfaces: {', '.join(enabled_surface_flags)}")

    if data["storage_state"]["mode"] == "stored_private_redacted":
        if data["storage_state"]["activation_required"]:
            failures.append("stored private redacted records must not require activation")
        if not data["storage_state"]["database_write_enabled"]:
            failures.append("stored private redacted records must enable database writes")
        if data["consent"]["private_retention_consent_proof"] is None:
            failures.append("stored private redacted records require private retention consent proof")
    else:
        if not data["storage_state"]["activation_required"]:
            failures.append("pre-storage records must require activation")
        if data["storage_state"]["database_write_enabled"]:
            failures.append("experience storage record cannot enable database writes before activation")
        if data["consent"]["private_retention_consent_proof"] is not None:
            failures.append("pre-storage records cannot include private retention consent proof")
    if data["storage_state"]["record_visible_to_retrieval"]:
        failures.append("experience storage record cannot be retrieval-visible before activation")
    if data["source_controls"]["raw_source_retention"] != "none" or data["source_controls"]["raw_detail_escrow_ref"] is not None:
        failures.append("experience storage record cannot retain raw source or raw escrow refs")
    if data["source_controls"]["raw_source_available_to_model"]:
        failures.append("experience storage record cannot expose raw source to model input")
    if contains_raw_marker(data):
        failures.append("experience storage record contains raw markers")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate redacted private experience storage record contract.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    schema = load_json(SCHEMA_PATH)
    data = load_json(args.input)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda error: list(error.path))
    if errors:
        print(json.dumps({"status": "rejected", "errors": sanitized_schema_errors(errors)}, sort_keys=True))
        return 2
    failures = gate_failures(data)
    if failures:
        print(json.dumps({"status": "blocked", "blocking_gates": failures}, sort_keys=True))
        return 3
    print(
        json.dumps(
            {
                "status": "ok",
                "domain": data["domain"],
                "command_effect": (
                    "database_insert_ready"
                    if data["storage_state"]["mode"] == "stored_private_redacted"
                    else "contract_only"
                ),
                "database_write_enabled": data["storage_state"]["database_write_enabled"],
                "record_visible_to_retrieval": data["storage_state"]["record_visible_to_retrieval"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
