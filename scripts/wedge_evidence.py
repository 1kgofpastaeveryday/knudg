#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path


EVIDENCE_FIELDS = {
    "evidence_id",
    "evidence_type",
    "storage_location",
    "artifact_digest",
    "source_class",
    "consent_state",
    "retention_deadline",
    "owner",
    "allowed_repo_reference",
}

CANDIDATE_FIELDS = {
    "candidate_id",
    "source_class",
    "source_rights_state",
    "consent_artifact_id",
    "source_digest",
    "redacted_artifact_digest",
    "fallback_visibility",
    "outcome_type",
    "exact_error_signature",
    "tool_coordinates",
    "environment_bounds",
    "risk_band",
    "high_risk_flags",
    "redaction_minutes",
    "review_minutes",
    "reproduction_required",
    "reproduction_minutes",
    "reviewer_confidence",
    "useful_summary_eligible",
    "decision",
    "rejection_reason",
}

EVIDENCE_TYPES = {
    "prospect",
    "interview",
    "seed_candidate",
    "baseline_replay",
    "review_calibration",
    "decision_memo",
}
SOURCE_CLASSES = {"internal_dogfood", "design_partner", "public_issue_build_log", "synthetic_fixture"}
CONSENT_STATES = {"not_required_for_synthetic", "requested", "granted", "denied", "withdrawn", "expired"}
SOURCE_RIGHTS = {"clear", "unclear_private_only", "rejected"}
VISIBILITIES = {"synthetic", "single_workspace_private", "team_only", "public_candidate"}
OUTCOMES = {"solved", "failed_only", "inconclusive", "unknown_clarified"}
RISK_BANDS = {"low", "medium", "high"}
HIGH_RISK_FLAGS = {
    "executable",
    "dependency_change",
    "credential",
    "deletion",
    "network",
    "repo_migration",
    "ci_cd",
    "billing",
    "security_posture",
}
CONFIDENCE = {"low", "medium", "high"}
YES_NO = {"yes", "no"}
DECISIONS = {
    "accepted_private",
    "accepted_team",
    "accepted_public_candidate",
    "rejected",
    "abandoned",
}
REJECTION_REASONS = {
    "",
    "source_rights_rejected",
    "consent_denied",
    "consent_withdrawn",
    "consent_expired",
    "unsafe_after_redaction",
    "not_useful",
    "duplicate",
    "abandoned_no_artifact",
    "abandoned_reproduction_failed",
    "out_of_scope",
}

OPAQUE_ID_RE = re.compile(r"^(ev|cand|part|team|memo|cal|replay|registry|summary)_[A-Za-z0-9_-]{6,80}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/#-]{1,160}$")
RAW_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b[A-Z]:\\", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:password|secret|token|api[_-]?key|credential)\b", re.IGNORECASE),
    re.compile(r"\b(?:github\.com|gitlab\.com|bitbucket\.org)\b", re.IGNORECASE),
]


class EvidenceError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def reject_raw_string(path, value):
    if len(value) > 240:
        raise EvidenceError(f"{path}: string is too long for repo-safe evidence")
    for pattern in RAW_PATTERNS:
        if pattern.search(value):
            raise EvidenceError(f"{path}: raw/private-looking value is not allowed")


def walk_strings(path, value):
    if isinstance(value, str):
        reject_raw_string(path, value)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            walk_strings(f"{path}[{index}]", item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            walk_strings(f"{path}.{key}", item)


def require_fields(kind, record, allowed, required):
    extra = sorted(set(record) - allowed)
    if extra:
        raise EvidenceError(f"{kind}: unknown fields are not repo-safe ({len(extra)} field(s))")
    missing = sorted(required - set(record))
    if missing:
        raise EvidenceError(f"{kind}: missing required fields: {', '.join(missing)}")


def require_enum(path, value, allowed):
    if value not in allowed:
        raise EvidenceError(f"{path}: invalid value")


def require_opaque_id(path, value):
    if not isinstance(value, str) or not OPAQUE_ID_RE.fullmatch(value):
        raise EvidenceError(f"{path}: expected opaque id")


def require_digest(path, value):
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise EvidenceError(f"{path}: expected sha256 digest")


def require_safe_reference(path, value):
    if not isinstance(value, str) or not SAFE_REF_RE.fullmatch(value):
        raise EvidenceError(f"{path}: expected opaque safe reference")
    reject_raw_string(path, value)


def require_number(path, value, *, allow_not_applicable=False):
    if allow_not_applicable and value == "not_applicable":
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise EvidenceError(f"{path}: expected non-negative number")


def validate_evidence_record(index, record):
    require_fields(f"evidence_register[{index}]", record, EVIDENCE_FIELDS, EVIDENCE_FIELDS)
    require_opaque_id(f"evidence_register[{index}].evidence_id", record["evidence_id"])
    require_enum(f"evidence_register[{index}].evidence_type", record["evidence_type"], EVIDENCE_TYPES)
    require_safe_reference(f"evidence_register[{index}].storage_location", record["storage_location"])
    require_digest(f"evidence_register[{index}].artifact_digest", record["artifact_digest"])
    require_enum(f"evidence_register[{index}].source_class", record["source_class"], SOURCE_CLASSES)
    require_enum(f"evidence_register[{index}].consent_state", record["consent_state"], CONSENT_STATES)
    require_safe_reference(f"evidence_register[{index}].retention_deadline", record["retention_deadline"])
    require_safe_reference(f"evidence_register[{index}].owner", record["owner"])
    require_safe_reference(f"evidence_register[{index}].allowed_repo_reference", record["allowed_repo_reference"])
    walk_strings(f"evidence_register[{index}]", record)


def validate_candidate(index, record):
    require_fields(f"seed_candidates[{index}]", record, CANDIDATE_FIELDS, CANDIDATE_FIELDS)
    require_opaque_id(f"seed_candidates[{index}].candidate_id", record["candidate_id"])
    require_enum(f"seed_candidates[{index}].source_class", record["source_class"], SOURCE_CLASSES)
    require_enum(f"seed_candidates[{index}].source_rights_state", record["source_rights_state"], SOURCE_RIGHTS)
    if record["consent_artifact_id"] != "not_required_for_synthetic":
        require_opaque_id(f"seed_candidates[{index}].consent_artifact_id", record["consent_artifact_id"])
    require_digest(f"seed_candidates[{index}].source_digest", record["source_digest"])
    require_digest(f"seed_candidates[{index}].redacted_artifact_digest", record["redacted_artifact_digest"])
    require_enum(f"seed_candidates[{index}].fallback_visibility", record["fallback_visibility"], VISIBILITIES)
    require_enum(f"seed_candidates[{index}].outcome_type", record["outcome_type"], OUTCOMES)
    require_safe_reference(f"seed_candidates[{index}].exact_error_signature", record["exact_error_signature"])
    require_safe_reference(f"seed_candidates[{index}].tool_coordinates", record["tool_coordinates"])
    require_safe_reference(f"seed_candidates[{index}].environment_bounds", record["environment_bounds"])
    require_enum(f"seed_candidates[{index}].risk_band", record["risk_band"], RISK_BANDS)
    if not isinstance(record["high_risk_flags"], list):
        raise EvidenceError(f"seed_candidates[{index}].high_risk_flags: expected list")
    for flag in record["high_risk_flags"]:
        require_enum(f"seed_candidates[{index}].high_risk_flags", flag, HIGH_RISK_FLAGS)
    require_number(f"seed_candidates[{index}].redaction_minutes", record["redaction_minutes"])
    require_number(f"seed_candidates[{index}].review_minutes", record["review_minutes"])
    require_enum(f"seed_candidates[{index}].reproduction_required", record["reproduction_required"], YES_NO)
    require_number(
        f"seed_candidates[{index}].reproduction_minutes",
        record["reproduction_minutes"],
        allow_not_applicable=True,
    )
    require_enum(f"seed_candidates[{index}].reviewer_confidence", record["reviewer_confidence"], CONFIDENCE)
    require_enum(f"seed_candidates[{index}].useful_summary_eligible", record["useful_summary_eligible"], YES_NO)
    require_enum(f"seed_candidates[{index}].decision", record["decision"], DECISIONS)
    require_enum(f"seed_candidates[{index}].rejection_reason", record["rejection_reason"], REJECTION_REASONS)
    if record["decision"] in {"rejected", "abandoned"} and not record["rejection_reason"]:
        raise EvidenceError(f"seed_candidates[{index}].rejection_reason: required for rejected or abandoned candidates")
    if record["source_rights_state"] != "clear" and record["fallback_visibility"] == "public_candidate":
        raise EvidenceError(f"seed_candidates[{index}]: unclear rights cannot count as public_candidate")
    walk_strings(f"seed_candidates[{index}]", record)


def load_snapshot(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EvidenceError("snapshot: expected object")
    allowed = {"snapshot_id", "protocol_version", "evidence_register", "seed_candidates"}
    extra = sorted(set(data) - allowed)
    if extra:
        raise EvidenceError(f"snapshot: unknown fields are not repo-safe ({len(extra)} field(s))")
    require_opaque_id("snapshot.snapshot_id", data.get("snapshot_id"))
    require_safe_reference("snapshot.protocol_version", data.get("protocol_version"))
    evidence = data.get("evidence_register", [])
    candidates = data.get("seed_candidates", [])
    if not isinstance(evidence, list) or not isinstance(candidates, list):
        raise EvidenceError("snapshot: evidence_register and seed_candidates must be arrays")
    for index, record in enumerate(evidence):
        validate_evidence_record(index, record)
    for index, record in enumerate(candidates):
        validate_candidate(index, record)
    return data


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * pct + 99) // 100) - 1))
    return ordered[index]


def metric_summary(values):
    return {
        "median": statistics.median(values) if values else None,
        "p90": percentile(values, 90),
    }


def summarize(data):
    candidates = data["seed_candidates"]
    reproduction_values = [
        item["reproduction_minutes"]
        for item in candidates
        if item["reproduction_required"] == "yes" and item["reproduction_minutes"] != "not_applicable"
    ]
    return {
        "snapshot_id": data["snapshot_id"],
        "protocol_version": data["protocol_version"],
        "snapshot_digest": sha256_json(data),
        "evidence_count_by_type": dict(sorted(Counter(item["evidence_type"] for item in data["evidence_register"]).items())),
        "candidate_count": len(candidates),
        "candidate_count_by_source_class": dict(sorted(Counter(item["source_class"] for item in candidates).items())),
        "candidate_count_by_decision": dict(sorted(Counter(item["decision"] for item in candidates).items())),
        "candidate_count_by_risk_band": dict(sorted(Counter(item["risk_band"] for item in candidates).items())),
        "useful_summary_eligible_count": sum(1 for item in candidates if item["useful_summary_eligible"] == "yes"),
        "high_risk_count": sum(1 for item in candidates if item["risk_band"] == "high" or item["high_risk_flags"]),
        "source_rights_rejection_count": sum(1 for item in candidates if item["source_rights_state"] == "rejected"),
        "consent_count_by_state": dict(sorted(Counter(item["consent_state"] for item in data["evidence_register"]).items())),
        "redaction_minutes": metric_summary([item["redaction_minutes"] for item in candidates]),
        "review_minutes": metric_summary([item["review_minutes"] for item in candidates]),
        "reproduction_minutes": metric_summary(reproduction_values),
        "allowed_repo_reference": {
            "snapshot_id": data["snapshot_id"],
            "snapshot_digest": sha256_json(data),
        },
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Validate and summarize WEDGE-001 opaque evidence snapshots.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--input", required=True)
    summary = sub.add_parser("summary")
    summary.add_argument("--input", required=True)
    summary.add_argument("--output", required=True)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = load_snapshot(args.input)
        if args.command == "validate":
            print(json.dumps({"status": "ok", "snapshot_digest": sha256_json(data)}, sort_keys=True))
            return 0
        output = summarize(data)
        Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "ok", "summary_digest": sha256_json(output)}, sort_keys=True))
        return 0
    except (EvidenceError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
