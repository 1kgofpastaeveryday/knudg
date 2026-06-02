import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


def validator():
    schema = json.loads((ROOT / "schemas" / "retrieval-panel-v0.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_valid(payload):
    errors = sorted(validator().iter_errors(payload), key=lambda error: error.path)
    assert errors == []


def test_cards_found_response_matches_panel_schema():
    assert_valid(
        {
            "decision": "cards_found",
            "delivery_mode": "retrieval_panel",
            "served_from": "closed_private_exact_fts",
            "latency_budget_ms": 250,
            "cards": [
                {
                    "card_id": "card_001",
                    "card_version_id": "version_001",
                    "namespace_id": "ns_closed",
                    "outcome_type": "solved",
                    "quality_state": "unreviewed",
                    "evidence_strength": "single_session",
                    "withheld": False,
                    "digest": "sha256:abc",
                    "local_only_status": "local_private",
                    "freshness_bucket": "local_private_current",
                    "match_score": 2,
                    "coarse_match_reason": ["profile"],
                    "handoff_ref": "local-card:card_001:version_001",
                    "provenance": {
                        "source": "closed private exact/FTS",
                        "source_class": "local_private_dogfood",
                    },
                }
            ],
        }
    )


def test_no_suggestion_response_matches_panel_schema():
    assert_valid(
        {
            "decision": "no_suggestion",
            "delivery_mode": "no_suggestion",
            "served_from": "closed_private_exact_fts",
            "latency_budget_ms": 250,
            "cards": [],
            "abstention_reason": "no_authorized_match",
        }
    )


def test_panel_schema_rejects_body_like_fields():
    payload = {
        "decision": "cards_found",
        "delivery_mode": "retrieval_panel",
        "served_from": "synthetic_corpus",
        "latency_budget_ms": 250,
        "cards": [
            {
                "card_id": "card_001",
                "card_version_id": "version_001",
                "namespace_id": "ns_local",
                "outcome_type": "solved",
                "quality_state": "unreviewed",
                "evidence_strength": "single_session",
                "withheld": False,
                "digest": "sha256:abc",
                "local_only_status": "local_private",
                "freshness_bucket": "local_private_current",
                "match_score": 2,
                "coarse_match_reason": ["server"],
                "handoff_ref": "local-card:card_001:version_001",
                "provenance": {"source": "closed private exact/FTS", "source_class": "local_private_dogfood"},
                "successful_path": ["do not expose full body here"],
            }
        ],
    }
    errors = list(validator().iter_errors(payload))
    assert errors
