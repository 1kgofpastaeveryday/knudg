import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import knudg_closed_api as api


def test_embedding_text_for_card_uses_human_fields_only():
    card = {
        "title": "Psycopg migration capture path",
        "human_summary": {"content": "Store the sanitized card", "redaction_summary": "removed paths"},
        "problem_summary": "connection timeout on publish",
        "solution_summary": "use a pooled connection",
        "public_packages": ["psycopg", "postgres"],
        "environment_tags": ["windows"],
        "command_labels": ["pytest run"],
        "error_fingerprints": ["ERR_TIMEOUT"],
        "lessons": ["pin the pool size"],
    }
    text = api.embedding_text_for_card(card)
    assert "Psycopg migration capture path" in text
    assert "connection timeout on publish" in text
    assert "use a pooled connection" in text
    assert "psycopg postgres" in text
    assert "pin the pool size" in text
    # redaction_summary is metadata, not part of the semantic text
    assert "removed paths" not in text


def test_embedding_text_for_card_handles_missing_fields():
    assert api.embedding_text_for_card({}) == ""
    assert api.embedding_text_for_card("not a dict") == ""
    assert api.embedding_text_for_card({"title": "only title"}) == "only title"


def test_embed_text_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("KNUDG_EMBEDDING_ENABLED", "0")
    assert api.embed_text("some text") is None


def test_embed_text_empty_returns_none(monkeypatch):
    monkeypatch.setenv("KNUDG_EMBEDDING_ENABLED", "1")
    assert api.embed_text("") is None
    assert api.embed_text("   ") is None


def test_embedding_to_pgvector_format():
    assert api.embedding_to_pgvector([0.5, -1.0, 2.0]) == "[0.5,-1.0,2.0]"


def test_merge_search_rows_dedupes_sums_and_orders():
    fts = [{"card_id": "a", "card_version_id": "a1", "match_score": 2, "coarse_match_reason": ["pytest"]}]
    vector = [
        {"card_id": "a", "card_version_id": "a1", "match_score": 7, "coarse_match_reason": ["semantic_similarity"]},
        {"card_id": "b", "card_version_id": "b1", "match_score": 6, "coarse_match_reason": ["semantic_similarity"]},
    ]
    merged = api.merge_search_rows(fts, vector)
    by_id = {row["card_id"]: row for row in merged}
    # found by both FTS and vector: scores summed, reasons unioned
    assert by_id["a"]["match_score"] == 9
    assert by_id["a"]["coarse_match_reason"] == ["pytest", "semantic_similarity"]
    # vector-only card retained
    assert by_id["b"]["match_score"] == 6
    # ordered by combined score descending
    assert [row["card_id"] for row in merged] == ["a", "b"]


def test_merge_search_rows_fts_only_and_empty():
    assert api.merge_search_rows([], []) == []
    fts = [{"card_id": "x", "card_version_id": "x1", "match_score": 3, "coarse_match_reason": ["term"]}]
    merged = api.merge_search_rows(fts, [])
    assert len(merged) == 1
    assert merged[0]["match_score"] == 3
