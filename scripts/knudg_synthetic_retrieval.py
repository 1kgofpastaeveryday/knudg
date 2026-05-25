#!/usr/bin/env python3
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.card_payload import CardPayloadError, validate_card_payload_v1
from scripts.knudg_writer import build_card_payload
from scripts.knudg_retrieval import RetrievalError, require_private_profile


SEARCHABLE_STATUSES = {"approved_private", "indexed_hot", "indexed_main"}
QUERY_FIELDS = {
    "goal_category",
    "sanitized_error_signature",
    "public_packages_claimed",
    "public_frameworks_tools_claimed",
    "language_runtime",
    "coarse_os",
    "repo_shape_category",
}

QUERY_VIEW_SPECS = [
    (
        "exact_identifiers",
        1.4,
        (
            "sanitized_error_signature",
            "public_packages_claimed",
            "public_frameworks_tools_claimed",
            "dependency_major_versions",
        ),
    ),
    (
        "sparse_keywords",
        1.0,
        (
            "goal_category",
            "sanitized_error_signature",
            "public_packages_claimed",
            "public_frameworks_tools_claimed",
            "language_runtime",
            "coarse_os",
            "dependency_major_versions",
            "repo_shape_category",
        ),
    ),
    (
        "semantic_summary",
        0.8,
        (
            "goal_category",
            "repo_shape_category",
            "public_frameworks_tools_claimed",
        ),
    ),
    (
        "hypothetical_relevant_card",
        0.7,
        (
            "goal_category",
            "sanitized_error_signature",
            "repo_shape_category",
        ),
    ),
    (
        "structured_filters",
        0.6,
        (
            "language_runtime",
            "coarse_os",
            "dependency_major_versions",
            "repo_shape_category",
        ),
    ),
]

QUALITY_ADJUSTMENTS = {
    "verified": 2,
    "solved_many": 2,
    "solved_once": 1,
    "unreviewed": 0,
    "disputed": -2,
}

OUTCOME_ADJUSTMENTS = {
    "solved": 1,
    "unknown_clarified": 0,
    "inconclusive": 0,
    "failed_only": -1,
}

RRF_K = 60


class SyntheticRetrievalError(ValueError):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def require_string(path, value):
    if not isinstance(value, str) or not value:
        raise SyntheticRetrievalError(f"{path}: expected non-empty string")


def require_string_list(path, value):
    if not isinstance(value, list) or not value:
        raise SyntheticRetrievalError(f"{path}: expected non-empty array")
    for item in value:
        require_string(f"{path}[]", item)
    return value


def require_wrapper(payload):
    if not isinstance(payload, dict):
        raise SyntheticRetrievalError("request: expected object")
    if payload.get("schema_version") != "synthetic-retrieval-v0":
        raise SyntheticRetrievalError("request.schema_version: invalid value")
    require_string("request.request_id", payload.get("request_id"))
    auth = payload.get("auth_context")
    if not isinstance(auth, dict):
        raise SyntheticRetrievalError("request.auth_context: expected object")
    require_string("request.auth_context.tenant_id", auth.get("tenant_id"))
    auth_namespaces = set(require_string_list("request.auth_context.namespace_ids", auth.get("namespace_ids")))
    revocation_epoch = auth.get("revocation_epoch", 0)
    if not isinstance(revocation_epoch, int) or revocation_epoch < 0:
        raise SyntheticRetrievalError("request.auth_context.revocation_epoch: expected non-negative integer")
    profile = require_private_profile(payload.get("search_profile"))
    requested_namespaces = set(profile["namespace_ids"])
    if not requested_namespaces <= auth_namespaces:
        raise SyntheticRetrievalError("request.search_profile.namespace_ids: not authorized by auth_context")
    return payload, auth, profile


def require_corpus(corpus):
    if not isinstance(corpus, dict):
        raise SyntheticRetrievalError("corpus: expected object")
    if corpus.get("schema_version") != "synthetic-corpus-v0":
        raise SyntheticRetrievalError("corpus.schema_version: invalid value")
    cards = corpus.get("cards")
    if not isinstance(cards, list):
        raise SyntheticRetrievalError("corpus.cards: expected array")
    tombstones = corpus.get("revocation_tombstones", [])
    if not isinstance(tombstones, list):
        raise SyntheticRetrievalError("corpus.revocation_tombstones: expected array")
    for index, card in enumerate(cards):
        require_card(f"corpus.cards[{index}]", card)
    for index, tombstone in enumerate(tombstones):
        require_tombstone(f"corpus.revocation_tombstones[{index}]", tombstone)
    return cards, tombstones


def require_card(path, card):
    if not isinstance(card, dict):
        raise SyntheticRetrievalError(f"{path}: expected object")
    for field in ("tenant_id", "namespace_id", "card_id", "card_version_id", "status"):
        require_string(f"{path}.{field}", card.get(field))
    if card["status"] not in SEARCHABLE_STATUSES | {"revoked", "candidate_created", "pending_review", "awaiting_user_approval"}:
        raise SyntheticRetrievalError(f"{path}.status: invalid value")
    if card.get("source_class") != "synthetic":
        raise SyntheticRetrievalError(f"{path}.source_class: only synthetic cards are enabled")
    if not isinstance(card.get("payload"), dict):
        raise SyntheticRetrievalError(f"{path}.payload: expected object")
    try:
        validate_card_payload_v1(card["payload"])
    except CardPayloadError as exc:
        raise SyntheticRetrievalError(f"{path}.payload: {exc}") from exc


def require_synthetic_payload(path, payload):
    if not isinstance(payload, dict):
        raise SyntheticRetrievalError(f"{path}: expected object")
    try:
        validate_card_payload_v1(payload)
    except CardPayloadError as exc:
        raise SyntheticRetrievalError(f"{path}: {exc}") from exc
    privacy = payload.get("privacy") or {}
    provenance = payload.get("provenance") or {}
    if privacy.get("source_class") != "synthetic" or provenance.get("source_class") != "synthetic":
        raise SyntheticRetrievalError(f"{path}: only synthetic card payloads are enabled")
    return payload


def load_payload(path):
    value = load_json(path)
    if isinstance(value, dict) and "payload" in value and value.get("status") == "local_draft_only":
        value = value["payload"]
    return require_synthetic_payload(f"payload:{Path(path).name}", value)


def require_tombstone(path, tombstone):
    if not isinstance(tombstone, dict):
        raise SyntheticRetrievalError(f"{path}: expected object")
    for field in ("tenant_id", "subject_type", "subject_id"):
        require_string(f"{path}.{field}", tombstone.get(field))
    if tombstone["subject_type"] not in {"tenant", "namespace", "card", "card_version"}:
        raise SyntheticRetrievalError(f"{path}.subject_type: invalid value")
    epoch = tombstone.get("revocation_epoch")
    if not isinstance(epoch, int) or epoch < 0:
        raise SyntheticRetrievalError(f"{path}.revocation_epoch: expected non-negative integer")


def normalize_token(value):
    return re.sub(r"[^a-z0-9_.:+-]+", " ", value.lower()).strip()


def collect_query_terms(profile):
    terms = []
    for field in QUERY_FIELDS:
        value = profile.get(field)
        if isinstance(value, str):
            normalized = normalize_token(value)
            if normalized:
                terms.extend(normalized.split())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    normalized = normalize_token(item)
                    if normalized:
                        terms.extend(normalized.split())
    return sorted(set(term for term in terms if len(term) >= 2))


def collect_terms_from_fields(profile, fields):
    terms = []
    for field in fields:
        value = profile.get(field)
        if isinstance(value, str):
            normalized = normalize_token(value)
            if normalized:
                terms.extend(normalized.split())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    normalized = normalize_token(item)
                    if normalized:
                        terms.extend(normalized.split())
    return sorted(set(term for term in terms if len(term) >= 2))


def build_query_views(profile):
    views = []
    for name, weight, fields in QUERY_VIEW_SPECS:
        terms = collect_terms_from_fields(profile, fields)
        if terms:
            views.append({"name": name, "weight": weight, "terms": terms})
    return views


def collect_text(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.extend(collect_text(item))
        return parts
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(key)
            parts.extend(collect_text(item))
        return parts
    return []


def tombstone_matches(tombstone, card):
    if tombstone["tenant_id"] != card["tenant_id"]:
        return False
    subject_type = tombstone["subject_type"]
    subject_id = tombstone["subject_id"]
    return (
        (subject_type == "tenant" and subject_id == card["tenant_id"])
        or (subject_type == "namespace" and subject_id == card["namespace_id"])
        or (subject_type == "card" and subject_id == card["card_id"])
        or (subject_type == "card_version" and subject_id == card["card_version_id"])
    )


def is_authorized_and_visible(card, auth, profile, tombstones):
    if card["tenant_id"] != auth["tenant_id"]:
        return False
    if card["namespace_id"] not in profile["namespace_ids"]:
        return False
    if card["status"] not in SEARCHABLE_STATUSES:
        return False
    if any(tombstone_matches(tombstone, card) for tombstone in tombstones):
        return False
    return True


def score_card(card, terms):
    haystack = normalize_token(" ".join(collect_text(card["payload"])))
    matched = [term for term in terms if term in haystack]
    payload = card["payload"]
    outcome_bonus = OUTCOME_ADJUSTMENTS.get(payload["outcome_type"], 0)
    quality_bonus = QUALITY_ADJUSTMENTS.get(payload["quality_state"], 0)
    return len(matched) + outcome_bonus + quality_bonus, matched


def score_card_for_view(card, terms):
    haystack = normalize_token(" ".join(collect_text(card["payload"])))
    matched = [term for term in terms if term in haystack]
    return len(matched), matched


def fused_results(cards, query_views):
    by_card = {}
    for view in query_views:
        ranked = []
        for card in cards:
            score, matched_terms = score_card_for_view(card, view["terms"])
            if score > 0:
                ranked.append((score, matched_terms, card))
        ranked.sort(key=lambda item: (-item[0], item[2]["card_id"]))
        for rank, (view_score, matched_terms, card) in enumerate(ranked, start=1):
            key = (card["card_id"], card["card_version_id"])
            entry = by_card.setdefault(
                key,
                {
                    "card": card,
                    "fusion_score": 0.0,
                    "matched_terms": set(),
                    "query_views": [],
                },
            )
            entry["fusion_score"] += view["weight"] / (RRF_K + rank)
            entry["matched_terms"].update(matched_terms)
            entry["query_views"].append(
                {
                    "name": view["name"],
                    "rank": rank,
                    "matched_terms": matched_terms[:8],
                }
            )
    results = []
    for entry in by_card.values():
        card = entry["card"]
        threshold_score, _matched = score_card(card, sorted(entry["matched_terms"]))
        results.append(
            {
                "card": card,
                "threshold_score": threshold_score,
                "fusion_score": entry["fusion_score"],
                "matched_terms": sorted(entry["matched_terms"]),
                "query_views": entry["query_views"],
            }
        )
    results.sort(key=lambda item: (-item["fusion_score"], -item["threshold_score"], item["card"]["card_id"]))
    return results


def panel_card(card, score, matched_terms):
    payload = card["payload"]
    safety = payload["safety"]
    high_risk = safety["safety_class"] == "high" and safety["review_state"] != "cleared"
    return {
        "card_id": card["card_id"],
        "card_version_id": card["card_version_id"],
        "namespace_id": card["namespace_id"],
        "outcome_type": payload["outcome_type"],
        "quality_state": payload["quality_state"],
        "evidence_strength": payload["evidence_strength"],
        "safety_class": safety["safety_class"],
        "withheld": high_risk,
        "freshness": "synthetic",
        "match_score": score,
        "matched_terms": matched_terms[:8],
        "summary": {
            "goal": payload["goal"],
            "symptom": payload["symptom"],
        },
        "provenance": {
            "source": payload["provenance"].get("source", "synthetic corpus"),
            "source_class": "synthetic",
        },
    }


def no_suggestion(reason, latency_budget_ms=None):
    return {
        "decision": "no_suggestion",
        "delivery_mode": "no_suggestion",
        "abstention_reason": reason,
        "served_from": "synthetic_corpus",
        "latency_budget_ms": latency_budget_ms,
        "cards": [],
    }


def replay_draft_payload(**overrides):
    payload = {
        "schema_version": "writer-draft-v0",
        "request_id": "replay_draft_000001",
        "source_class": "synthetic",
        "outcome_type": "solved",
        "goal": "repair knudgctl local server url missing",
        "symptom": "server url missing in local profile",
        "environment": {"agent_tool": "Codex", "coarse_os": "windows"},
        "context_fingerprint": {"repo_shape": "python-node-local-plugin", "tool": "knudgctl"},
        "successful_path": ["set local profile to loopback server", "pin capabilities"],
        "failed_paths": [],
        "known_unknowns": [],
        "scope_limits": ["synthetic replay only"],
        "risk_flags": [],
    }
    payload.update(overrides)
    return payload


def replay_request(**profile_overrides):
    profile = {
        "schema_version": "search-profile-v0",
        "request_id": "replay_profile_000001",
        "tenant_scope": "private",
        "namespace_ids": ["ns_local"],
        "delivery_mode_requested": "retrieval_panel",
        "goal_category": "local server setup",
        "sanitized_error_signature": "server url missing",
        "public_packages_claimed": ["knudgctl"],
        "public_frameworks_tools_claimed": ["Codex"],
        "language_runtime": "python-3.12",
        "coarse_os": "windows",
        "dependency_major_versions": [],
        "repo_shape_category": "python-node-local-plugin",
        "risk_flags_claimed": [],
        "latency_budget_ms": 250,
        "privacy_budget_class_claimed": "private_team",
    }
    profile.update(profile_overrides)
    return {
        "schema_version": "synthetic-retrieval-v0",
        "request_id": "replay_req_000001",
        "auth_context": {
            "tenant_id": "tenant_local",
            "namespace_ids": ["ns_local"],
            "revocation_epoch": 0,
        },
        "search_profile": profile,
    }


def replay_card(card_id, payload, **overrides):
    card = {
        "tenant_id": "tenant_local",
        "namespace_id": "ns_local",
        "card_id": card_id,
        "card_version_id": f"{card_id}_version",
        "status": "approved_private",
        "source_class": "synthetic",
        "payload": payload,
    }
    card.update(overrides)
    return card


def replay_case_material(case_id):
    if case_id == "exact_identifier_preferred":
        exact_payload = build_card_payload(
            replay_draft_payload(
                goal="repair knudgctl local server url missing",
                symptom="server url missing in local profile",
                context_fingerprint={"repo_shape": "python-node-local-plugin", "tool": "knudgctl"},
                quality_state="solved_once",
            )
        )
        semantic_payload = build_card_payload(
            replay_draft_payload(
                request_id="replay_draft_000002",
                goal="repair local server startup",
                symptom="loopback profile was confusing",
                context_fingerprint={"repo_shape": "python-node-local-plugin", "tool": "local-server"},
                quality_state="solved_once",
            )
        )
        return {
            "request": replay_request(),
            "corpus": {
                "schema_version": "synthetic-corpus-v0",
                "cards": [
                    replay_card("card_semantic", semantic_payload),
                    replay_card("card_exact", exact_payload),
                ],
                "revocation_tombstones": [],
            },
            "min_score": 2,
            "relevant_cards": ["card_exact"],
            "expected_decision": "cards_found",
        }
    if case_id == "disputed_card_abstains_when_below_threshold":
        disputed_payload = build_card_payload(
            replay_draft_payload(
                goal="local server setup",
                symptom="server url missing",
                quality_state="disputed",
            )
        )
        return {
            "request": replay_request(),
            "corpus": {
                "schema_version": "synthetic-corpus-v0",
                "cards": [replay_card("card_disputed", disputed_payload)],
                "revocation_tombstones": [],
            },
            "min_score": 10,
            "relevant_cards": [],
            "expected_decision": "no_suggestion",
        }
    raise SyntheticRetrievalError(f"replay case is not implemented: {case_id}")


def dcg_at_k(ranked_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    score = 0.0
    for index, card_id in enumerate(ranked_ids[:k], start=1):
        if card_id in relevant:
            score += 1.0 / math.log2(index + 1)
    return score


def ndcg_at_k(ranked_ids, relevant_ids, k):
    if not relevant_ids:
        return 1.0
    ideal_relevant = list(relevant_ids)[:k]
    ideal = dcg_at_k(ideal_relevant, relevant_ids, k)
    if ideal == 0:
        return 0.0
    return dcg_at_k(ranked_ids, relevant_ids, k) / ideal


def metric_average(values, *, empty_value=1.0):
    if not values:
        return empty_value
    return sum(values) / len(values)


def replay_fixture(fixture):
    if not isinstance(fixture, dict) or fixture.get("schema_version") != "m3-retrieval-hybrid-fixtures-v0":
        raise SyntheticRetrievalError("replay fixture schema_version is invalid")
    if fixture.get("fixture_class") != "synthetic":
        raise SyntheticRetrievalError("only synthetic replay fixtures are enabled")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SyntheticRetrievalError("replay fixture requires cases")

    case_reports = []
    exact_recall_values = []
    hybrid_recall_values = []
    ndcg_values = []
    abstention_values = []
    harmful_count = 0
    suggestion_count = 0

    for case in cases:
        case_id = case.get("case_id")
        require_string("case.case_id", case_id)
        material = replay_case_material(case_id)
        result = search_synthetic(material["request"], material["corpus"], material["min_score"])
        ranked_ids = [card["card_id"] for card in result.get("cards", [])]
        relevant_ids = material["relevant_cards"]
        expected_decision = case.get("expected_decision") or material["expected_decision"]

        if relevant_ids:
            exact_recall_values.append(1.0 if any(card_id in ranked_ids[:3] for card_id in relevant_ids) else 0.0)
            hybrid_recall_values.append(1.0 if any(card_id in ranked_ids[:10] for card_id in relevant_ids) else 0.0)
            ndcg_values.append(ndcg_at_k(ranked_ids, relevant_ids, 10))
        else:
            ndcg_values.append(1.0 if result["decision"] == expected_decision else 0.0)

        if expected_decision == "no_suggestion":
            abstention_values.append(1.0 if result["decision"] == "no_suggestion" else 0.0)
            if result["decision"] != "no_suggestion":
                harmful_count += 1
        if result.get("cards"):
            suggestion_count += len(result["cards"])
            harmful_count += sum(1 for card in result["cards"] if card.get("withheld"))

        case_reports.append(
            {
                "case_id": case_id,
                "decision": result["decision"],
                "expected_decision": expected_decision,
                "ranked_card_ids": ranked_ids[:10],
                "relevant_card_ids": relevant_ids,
                "exact_identifier_hit_at_3": bool(relevant_ids and any(card_id in ranked_ids[:3] for card_id in relevant_ids)),
                "hybrid_hit_at_10": bool(relevant_ids and any(card_id in ranked_ids[:10] for card_id in relevant_ids)),
                "ndcg_at_10": ndcg_values[-1],
            }
        )

    metric_values = {
        "exact_identifier_recall_at_3": metric_average(exact_recall_values),
        "hybrid_recall_at_10": metric_average(hybrid_recall_values),
        "ndcg_at_10": metric_average(ndcg_values),
        "abstention_accuracy": metric_average(abstention_values),
        "stale_or_harmful_suggestion_rate": harmful_count / suggestion_count if suggestion_count else 0.0,
    }
    floors = fixture.get("offline_metric_floors", {})
    floor_results = {}
    for key, value in metric_values.items():
        floor = floors.get(key)
        if floor is None:
            passed = True
        elif key == "stale_or_harmful_suggestion_rate":
            passed = value <= floor
        else:
            passed = value >= floor
        floor_results[key] = {"value": value, "floor": floor, "passed": passed}
    return {
        "schema_version": "retrieval-replay-report-v0",
        "fixture_schema_version": fixture["schema_version"],
        "fixture_class": "synthetic",
        "fusion": fixture.get("fusion"),
        "case_count": len(cases),
        "metrics": metric_values,
        "floors": floor_results,
        "passed": all(item["passed"] for item in floor_results.values()),
        "cases": case_reports,
    }


def search_synthetic(request, corpus, min_score):
    _wrapper, auth, profile = require_wrapper(request)
    cards, tombstones = require_corpus(corpus)
    query_views = build_query_views(profile)
    terms = sorted({term for view in query_views for term in view["terms"]})
    if not terms:
        return no_suggestion("low_confidence", profile.get("latency_budget_ms"))
    authorized_cards = []
    for card in cards:
        if not is_authorized_and_visible(card, auth, profile, tombstones):
            continue
        authorized_cards.append(card)
    results = [
        result
        for result in fused_results(authorized_cards, query_views)
        if result["threshold_score"] >= min_score
    ]
    if not results:
        return no_suggestion("no_authorized_match", profile.get("latency_budget_ms"))
    return {
        "decision": "cards_found",
        "delivery_mode": "retrieval_panel",
        "served_from": "synthetic_corpus",
        "latency_budget_ms": profile.get("latency_budget_ms"),
        "cards": [
            panel_card(
                result["card"],
                result["threshold_score"],
                result["matched_terms"],
            )
            for result in results[:3]
        ],
    }


def build_corpus_from_payloads(payload_paths, tenant_id, namespace_id, status):
    cards = []
    for index, path in enumerate(payload_paths, start=1):
        payload = load_payload(path)
        suffix = f"{index:03d}"
        cards.append(
            {
                "tenant_id": tenant_id,
                "namespace_id": namespace_id,
                "card_id": f"card_{suffix}",
                "card_version_id": f"version_{suffix}",
                "status": status,
                "source_class": "synthetic",
                "payload": payload,
            }
        )
    return {"schema_version": "synthetic-corpus-v0", "cards": cards, "revocation_tombstones": []}


def build_parser():
    parser = argparse.ArgumentParser(description="Knudg synthetic exact/FTS-style retrieval harness.")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("--input", required=True)
    search.add_argument("--corpus", required=True)
    search.add_argument("--min-score", type=int, default=2)
    corpus = sub.add_parser("build-corpus")
    corpus.add_argument("--payload", action="append", required=True, help="Synthetic card payload or writer draft result JSON. Repeat for multiple cards.")
    corpus.add_argument("--tenant-id", default="tenant_local")
    corpus.add_argument("--namespace-id", default="ns_local")
    corpus.add_argument("--status", choices=sorted(SEARCHABLE_STATUSES), default="approved_private")
    replay = sub.add_parser("replay")
    replay.add_argument("--input", required=True)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            if args.min_score < 1:
                raise SyntheticRetrievalError("--min-score must be positive")
            emit(search_synthetic(load_json(args.input), load_json(args.corpus), args.min_score))
        elif args.command == "build-corpus":
            emit(build_corpus_from_payloads(args.payload, args.tenant_id, args.namespace_id, args.status))
        elif args.command == "replay":
            emit(replay_fixture(load_json(args.input)))
        return 0
    except (SyntheticRetrievalError, RetrievalError, json.JSONDecodeError) as exc:
        emit({"decision": "no_suggestion", "delivery_mode": "no_suggestion", "abstention_reason": "payload_rejected", "served_from": "synthetic_corpus", "error": str(exc), "cards": []})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
