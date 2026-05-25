import argparse
import hashlib
import json
from pathlib import Path


DIGEST_PROFILE = "sha256:jcs-rfc8785:v1"
PROJECTION_OWNED_FIELDS = {
    "card_id",
    "tenant_id",
    "namespace_id",
    "visibility",
    "visibility_view",
    "status",
    "current_version_id",
    "created_at",
    "updated_at",
    "quality_score",
    "card_schema_version",
}
TOP_LEVEL_FIELDS = {
    "outcome_type",
    "goal",
    "symptom",
    "environment",
    "context_fingerprint",
    "successful_path",
    "failed_paths",
    "known_unknowns",
    "scope_limits",
    "evidence_strength",
    "twist",
    "quality_state",
    "safety",
    "privacy",
    "provenance",
    "deprecation",
    "supersession",
    "contradictions",
    "embedding_refs",
}
SAFETY_FIELDS = {
    "safety_class",
    "review_state",
    "executable_advice",
    "mentions_urls",
    "mentions_packages",
    "mentions_repositories",
    "credential_risk",
    "billing_risk",
    "deletion_risk",
    "network_call_risk",
    "verification_state",
    "withheld_reason",
}
SAFE_INTEGER_MIN = -(2**53) + 1
SAFE_INTEGER_MAX = (2**53) - 1


class CardPayloadError(ValueError):
    pass


def _object_pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CardPayloadError(f"duplicate object key: {key}")
        result[key] = value
    return result


def load_json_without_duplicate_keys(raw_text: str):
    try:
        return json.loads(raw_text, object_pairs_hook=_object_pairs_no_duplicates)
    except json.JSONDecodeError as exc:
        raise CardPayloadError(f"invalid json: {exc.msg}") from exc


def _assert_portable_jcs_subset(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CardPayloadError("object key must be a string")
            if not key.isascii():
                raise CardPayloadError("object keys must be ASCII in the M0 portable JCS subset")
            _assert_portable_jcs_subset(child)
        return
    if isinstance(value, list):
        for child in value:
            _assert_portable_jcs_subset(child)
        return
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int):
        if value < SAFE_INTEGER_MIN or value > SAFE_INTEGER_MAX:
            raise CardPayloadError("integer is outside the I-JSON safe range")
        return
    if isinstance(value, float):
        raise CardPayloadError("floating-point JSON numbers need a full RFC 8785 serializer")
    raise CardPayloadError(f"unsupported JSON value type: {type(value).__name__}")


def reject_projection_owned_fields(payload):
    if not isinstance(payload, dict):
        raise CardPayloadError("payload must be a JSON object")
    present = sorted(PROJECTION_OWNED_FIELDS.intersection(payload))
    if present:
        raise CardPayloadError(f"projection-owned field in payload: {present[0]}")


def validate_card_payload_v1(payload):
    reject_projection_owned_fields(payload)
    extra = sorted(set(payload).difference(TOP_LEVEL_FIELDS))
    if extra:
        raise CardPayloadError(f"unknown top-level field: {extra[0]}")
    required = {
        "outcome_type",
        "goal",
        "symptom",
        "environment",
        "context_fingerprint",
        "failed_paths",
        "known_unknowns",
        "scope_limits",
        "evidence_strength",
        "quality_state",
        "safety",
        "privacy",
        "provenance",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise CardPayloadError(f"missing required field: {missing[0]}")
    if payload["outcome_type"] not in {"solved", "failed_only", "inconclusive", "unknown_clarified"}:
        raise CardPayloadError("invalid outcome_type")
    if payload["evidence_strength"] not in {"single_session", "multi_session", "reproduced", "external_reference", "operator_judgment"}:
        raise CardPayloadError("invalid evidence_strength")
    if payload["quality_state"] not in {"unreviewed", "solved_once", "solved_many", "verified", "disputed"}:
        raise CardPayloadError("invalid quality_state")
    for text_field in ("goal", "symptom"):
        if not isinstance(payload[text_field], str) or not payload[text_field]:
            raise CardPayloadError(f"{text_field} must be a non-empty string")
    for object_field in ("environment", "context_fingerprint", "safety", "privacy", "provenance"):
        if not isinstance(payload[object_field], dict):
            raise CardPayloadError(f"{object_field} must be an object")
    if payload["privacy"].get("source_class") != "synthetic":
        raise CardPayloadError("privacy.source_class must be synthetic")
    if payload["provenance"].get("source_class") != "synthetic":
        raise CardPayloadError("provenance.source_class must be synthetic")
    for array_field in ("failed_paths", "known_unknowns", "scope_limits"):
        if not isinstance(payload[array_field], list):
            raise CardPayloadError(f"{array_field} must be an array")
        for item in payload[array_field]:
            if not isinstance(item, str) or not item:
                raise CardPayloadError(f"{array_field} items must be non-empty strings")
    if "successful_path" in payload and payload["successful_path"] is not None and not isinstance(payload["successful_path"], list):
        raise CardPayloadError("successful_path must be an array or null")
    if isinstance(payload.get("successful_path"), list):
        for item in payload["successful_path"]:
            if not isinstance(item, str) or not item:
                raise CardPayloadError("successful_path items must be non-empty strings")
    if payload["outcome_type"] == "solved" and not payload.get("successful_path"):
        raise CardPayloadError("solved payload requires a non-empty successful_path")
    if payload["outcome_type"] == "failed_only" and payload.get("successful_path"):
        raise CardPayloadError("failed_only payload cannot include a successful_path")
    if payload["outcome_type"] == "failed_only" and not payload["failed_paths"]:
        raise CardPayloadError("failed_only payload requires a non-empty failed_paths")
    if payload["outcome_type"] == "unknown_clarified" and not payload["known_unknowns"]:
        raise CardPayloadError("unknown_clarified payload requires a non-empty known_unknowns")

    safety = payload["safety"]
    safety_missing = sorted(SAFETY_FIELDS.difference(safety))
    if safety_missing:
        raise CardPayloadError(f"missing safety field: {safety_missing[0]}")
    safety_extra = sorted(set(safety).difference(SAFETY_FIELDS))
    if safety_extra:
        raise CardPayloadError(f"unknown safety field: {safety_extra[0]}")
    if safety["safety_class"] not in {"low", "medium", "high"}:
        raise CardPayloadError("invalid safety_class")
    if safety["review_state"] not in {"unreviewed", "quarantined", "cleared", "blocked"}:
        raise CardPayloadError("invalid review_state")
    if safety["verification_state"] not in {"unverified", "single_session", "reproduced", "external_reference"}:
        raise CardPayloadError("invalid verification_state")
    for bool_field in (
        "executable_advice",
        "mentions_urls",
        "mentions_packages",
        "mentions_repositories",
        "credential_risk",
        "billing_risk",
        "deletion_risk",
        "network_call_risk",
    ):
        if not isinstance(safety[bool_field], bool):
            raise CardPayloadError(f"{bool_field} must be boolean")
    if safety["withheld_reason"] is not None and not isinstance(safety["withheld_reason"], str):
        raise CardPayloadError("withheld_reason must be a string or null")
    if "twist" in payload and payload["twist"] is not None and not isinstance(payload["twist"], str):
        raise CardPayloadError("twist must be a string or null")
    for object_field in ("deprecation", "supersession"):
        if object_field in payload and not isinstance(payload[object_field], dict):
            raise CardPayloadError(f"{object_field} must be an object")
    if "contradictions" in payload:
        if not isinstance(payload["contradictions"], list):
            raise CardPayloadError("contradictions must be an array")
        for item in payload["contradictions"]:
            if not isinstance(item, str):
                raise CardPayloadError("contradictions items must be strings")
    if "embedding_refs" in payload:
        if not isinstance(payload["embedding_refs"], list):
            raise CardPayloadError("embedding_refs must be an array")
        for item in payload["embedding_refs"]:
            if not isinstance(item, dict):
                raise CardPayloadError("embedding_refs items must be objects")


def canonicalize(value) -> str:
    _assert_portable_jcs_subset(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_digest_hex(value) -> str:
    canonical = canonicalize(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_digest(value) -> str:
    return f"{DIGEST_PROFILE}:{canonical_digest_hex(value)}"


def parse_and_digest(raw_text: str):
    payload = load_json_without_duplicate_keys(raw_text)
    validate_card_payload_v1(payload)
    return payload, canonicalize(payload), canonical_digest(payload)


def main():
    parser = argparse.ArgumentParser(description="Validate and digest a Knudg card payload.")
    parser.add_argument("payload", type=Path)
    parser.add_argument("--canonical", action="store_true", help="Print canonical JSON instead of the digest.")
    args = parser.parse_args()
    _payload, canonical, digest = parse_and_digest(args.payload.read_text(encoding="utf-8"))
    print(canonical if args.canonical else digest)


if __name__ == "__main__":
    main()
