import json
import subprocess
import sys
from pathlib import Path

from scripts.knudg_writer import build_card_payload


ROOT = Path(__file__).resolve().parents[1]
HYBRID_FIXTURE = ROOT / "fixtures" / "m3-retrieval-hybrid-fixtures.json"


def draft_payload(**overrides):
    payload = {
        "schema_version": "writer-draft-v0",
        "request_id": "draft_req_000001",
        "source_class": "synthetic",
        "outcome_type": "solved",
        "goal": "capture local server setup failure",
        "symptom": "knudg local profile had no server url",
        "environment": {"agent_tool": "Codex", "coarse_os": "windows"},
        "context_fingerprint": {"repo_shape": "python-node-local-plugin", "tool": "knudgctl"},
        "successful_path": ["set local profile to loopback server", "pin capabilities"],
        "failed_paths": [],
        "known_unknowns": [],
        "scope_limits": ["synthetic local dogfood only"],
        "risk_flags": [],
    }
    payload.update(overrides)
    return payload


def request_payload(namespace_ids=None):
    namespace_ids = namespace_ids or ["ns_local"]
    return {
        "schema_version": "synthetic-retrieval-v0",
        "request_id": "retrieval_req_000001",
        "auth_context": {
            "tenant_id": "tenant_local",
            "namespace_ids": ["ns_local"],
            "revocation_epoch": 0,
        },
        "search_profile": {
            "schema_version": "search-profile-v0",
            "request_id": "profile_req_000001",
            "tenant_scope": "private",
            "namespace_ids": namespace_ids,
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
        },
    }


def corpus_payload(**card_overrides):
    card = {
        "tenant_id": "tenant_local",
        "namespace_id": "ns_local",
        "card_id": "card_001",
        "card_version_id": "version_001",
        "status": "approved_private",
        "source_class": "synthetic",
        "payload": build_card_payload(draft_payload()),
    }
    card.update(card_overrides)
    return {"schema_version": "synthetic-corpus-v0", "cards": [card], "revocation_tombstones": []}


def card_payload(card_id, payload, **overrides):
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


def run_search(tmp_path, request, corpus, *extra_args):
    request_path = tmp_path / "request.json"
    corpus_path = tmp_path / "corpus.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_synthetic_retrieval.py"),
            "search",
            "--input",
            str(request_path),
            "--corpus",
            str(corpus_path),
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def run_build_corpus(tmp_path, payloads, *extra_args):
    paths = []
    for index, payload in enumerate(payloads, start=1):
        path = tmp_path / f"payload-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.extend(["--payload", str(path)])
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_synthetic_retrieval.py"),
            "build-corpus",
            *paths,
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def run_replay(*extra_args):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "knudg_synthetic_retrieval.py"),
            "replay",
            "--input",
            str(HYBRID_FIXTURE),
            *extra_args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.stdout
    return result.returncode, json.loads(result.stdout)


def test_synthetic_retrieval_returns_authorized_panel_card(tmp_path):
    code, payload = run_search(tmp_path, request_payload(), corpus_payload())
    assert code == 0
    assert payload["decision"] == "cards_found"
    assert payload["delivery_mode"] == "retrieval_panel"
    assert payload["served_from"] == "synthetic_corpus"
    assert len(payload["cards"]) == 1
    card = payload["cards"][0]
    assert card["card_id"] == "card_001"
    assert card["withheld"] is False
    assert "successful_path" not in json.dumps(card)
    assert "server" in card["matched_terms"]


def test_synthetic_retrieval_fuses_query_views_and_prefers_exact_identifier_match(tmp_path):
    exact_payload = build_card_payload(
        draft_payload(
            goal="repair knudgctl local server url missing",
            symptom="server url missing in local profile",
            context_fingerprint={"repo_shape": "python-node-local-plugin", "tool": "knudgctl"},
            quality_state="solved_once",
        )
    )
    semantic_payload = build_card_payload(
        draft_payload(
            goal="repair local server startup",
            symptom="loopback profile was confusing",
            context_fingerprint={"repo_shape": "python-node-local-plugin", "tool": "local-server"},
            quality_state="solved_once",
        )
    )
    corpus = {
        "schema_version": "synthetic-corpus-v0",
        "cards": [
            card_payload("card_semantic", semantic_payload),
            card_payload("card_exact", exact_payload),
        ],
        "revocation_tombstones": [],
    }

    code, payload = run_search(tmp_path, request_payload(), corpus)
    assert code == 0
    assert payload["decision"] == "cards_found"
    assert [card["card_id"] for card in payload["cards"]] == ["card_exact", "card_semantic"]
    exact = payload["cards"][0]
    assert exact["match_score"] >= payload["cards"][1]["match_score"]
    assert "server" in exact["matched_terms"]
    assert "knudgctl" in exact["matched_terms"]


def test_synthetic_retrieval_demotes_disputed_cards_below_abstention_threshold(tmp_path):
    disputed_payload = build_card_payload(
        draft_payload(
            goal="local server setup",
            symptom="server url missing",
            quality_state="disputed",
        )
    )
    corpus = {
        "schema_version": "synthetic-corpus-v0",
        "cards": [card_payload("card_disputed", disputed_payload)],
        "revocation_tombstones": [],
    }

    code, payload = run_search(tmp_path, request_payload(), corpus, "--min-score", "10")
    assert code == 0
    assert payload["decision"] == "no_suggestion"
    assert payload["cards"] == []


def test_hybrid_fixture_documents_query_views_and_metric_floors():
    fixture = json.loads(HYBRID_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == "m3-retrieval-hybrid-fixtures-v0"
    assert fixture["fixture_class"] == "synthetic"
    assert fixture["fusion"] == "rrf_v0"
    assert fixture["query_view_names"] == [
        "exact_identifiers",
        "sparse_keywords",
        "semantic_summary",
        "hypothetical_relevant_card",
        "structured_filters",
    ]
    assert fixture["offline_metric_floors"]["exact_identifier_recall_at_3"] == 1.0
    assert fixture["offline_metric_floors"]["stale_or_harmful_suggestion_rate"] == 0.0
    assert "raw_transcript" in fixture["forbidden_data_classes"]


def test_replay_reports_retrieval_quality_metrics():
    code, report = run_replay()
    assert code == 0
    assert report["schema_version"] == "retrieval-replay-report-v0"
    assert report["fixture_schema_version"] == "m3-retrieval-hybrid-fixtures-v0"
    assert report["fixture_class"] == "synthetic"
    assert report["passed"] is True
    assert report["metrics"]["exact_identifier_recall_at_3"] == 1.0
    assert report["metrics"]["hybrid_recall_at_10"] == 1.0
    assert report["metrics"]["ndcg_at_10"] >= 0.8
    assert report["metrics"]["abstention_accuracy"] == 1.0
    assert report["metrics"]["stale_or_harmful_suggestion_rate"] == 0.0
    assert {case["case_id"] for case in report["cases"]} == {
        "exact_identifier_preferred",
        "disputed_card_abstains_when_below_threshold",
    }
    assert "successful_path" not in json.dumps(report)
    assert "payload_json" not in json.dumps(report)


def test_build_corpus_from_synthetic_payload_and_writer_result(tmp_path):
    payload = build_card_payload(draft_payload())
    writer_result = {"ok": True, "status": "local_draft_only", "payload": payload}
    code, corpus = run_build_corpus(tmp_path, [payload, writer_result], "--tenant-id", "tenant_local", "--namespace-id", "ns_local")
    assert code == 0
    assert corpus["schema_version"] == "synthetic-corpus-v0"
    assert len(corpus["cards"]) == 2
    assert corpus["cards"][0]["card_id"] == "card_001"
    assert corpus["cards"][1]["card_version_id"] == "version_002"
    assert all(card["source_class"] == "synthetic" for card in corpus["cards"])

    code, result = run_search(tmp_path, request_payload(), corpus)
    assert code == 0
    assert result["decision"] == "cards_found"
    assert len(result["cards"]) == 2


def test_build_corpus_rejects_non_synthetic_payload(tmp_path):
    payload = build_card_payload(draft_payload())
    payload["privacy"]["source_class"] = "private_session"
    code, result = run_build_corpus(tmp_path, [payload])
    assert code == 2
    assert result["decision"] == "no_suggestion"
    assert result["abstention_reason"] == "payload_rejected"
    assert "private_session" not in json.dumps(result)


def test_synthetic_retrieval_filters_before_scoring_by_auth_namespace_and_tenant(tmp_path):
    code, payload = run_search(tmp_path, request_payload(namespace_ids=["ns_other"]), corpus_payload())
    assert code == 2
    assert payload["abstention_reason"] == "payload_rejected"

    code, payload = run_search(tmp_path, request_payload(), corpus_payload(tenant_id="tenant_other"))
    assert code == 0
    assert payload["decision"] == "no_suggestion"
    assert payload["cards"] == []


def test_synthetic_retrieval_applies_revocation_tombstones(tmp_path):
    corpus = corpus_payload()
    corpus["revocation_tombstones"] = [
        {
            "tenant_id": "tenant_local",
            "subject_type": "card",
            "subject_id": "card_001",
            "revocation_epoch": 1,
        }
    ]
    code, payload = run_search(tmp_path, request_payload(), corpus)
    assert code == 0
    assert payload["decision"] == "no_suggestion"
    assert payload["cards"] == []


def test_synthetic_retrieval_rejects_raw_profile_and_non_synthetic_corpus(tmp_path):
    request = request_payload()
    request["search_profile"]["raw_log"] = "Traceback with private details"
    code, payload = run_search(tmp_path, request, corpus_payload())
    assert code == 2
    assert payload["abstention_reason"] == "payload_rejected"
    assert "Traceback" not in json.dumps(payload)

    code, payload = run_search(tmp_path, request_payload(), corpus_payload(source_class="private_session"))
    assert code == 2
    assert payload["abstention_reason"] == "payload_rejected"


def test_synthetic_retrieval_marks_high_risk_uncleared_cards_withheld(tmp_path):
    risky_payload = build_card_payload(draft_payload(risk_flags=["executable_advice"]))
    code, payload = run_search(tmp_path, request_payload(), corpus_payload(payload=risky_payload), "--min-score", "1")
    assert code == 0
    assert payload["decision"] == "cards_found"
    assert payload["cards"][0]["safety_class"] == "high"
    assert payload["cards"][0]["withheld"] is True
