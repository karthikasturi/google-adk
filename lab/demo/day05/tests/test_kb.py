"""
tests/test_kb.py — Unit tests for Day 05's semantic search
-------------------------------------------------------------
No network calls: kb.embed is patched with a stub that hands back
hand-picked vectors. ChromaDB itself runs for real (as an in-memory
EphemeralClient, same as kb.py uses) — only the embedding API call is
stubbed — so indexing and the ranking/top_k logic in semantic_search are
checked end to end, offline and deterministically.

Run with:  python -m pytest tests/ -v
"""

import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the day05 root importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

import kb
from kb import semantic_search

# One unit vector per document, each at a slightly larger angle from the query
# vector. For unit vectors, L2 distance grows monotonically with the angle
# between them, so ChromaDB's nearest-neighbour ranking is just "doc order"
# — fully deterministic, with no ties to worry about.
_FAKE_QUERY_EMBEDDING = [1.0, 0.0]
_FAKE_DOC_EMBEDDINGS = [
    [math.cos(i * math.radians(10)), math.sin(i * math.radians(10))]
    for i in range(len(kb.DOCUMENTS))
]


def _stub_embed(texts):
    """Return the query embedding for a single-text batch, doc embeddings otherwise."""
    if len(texts) == 1:
        return [_FAKE_QUERY_EMBEDDING]
    return _FAKE_DOC_EMBEDDINGS[: len(texts)]


@pytest.fixture(autouse=True)
def _reset_collection():
    """Each test gets a clean ChromaDB collection and a stubbed embed() — no API calls."""
    kb._collection = None
    with patch.object(kb, "embed", side_effect=_stub_embed):
        yield
    kb._collection = None


class TestSemanticSearch:
    def test_empty_query_returns_no_results(self):
        assert semantic_search("") == []
        assert semantic_search("   ") == []

    def test_returns_top_k_ranked_by_similarity(self):
        results = semantic_search("anything", top_k=2)

        assert len(results) == 2
        # By construction, the angle to the query strictly increases with
        # document index — so the expected nearest-neighbour order is just
        # doc order, closest (highest score) first.
        assert results[0]["id"] == kb.DOCUMENTS[0]["id"]
        assert results[1]["id"] == kb.DOCUMENTS[1]["id"]
        assert results[0]["score"] > results[1]["score"]

    def test_top_k_limits_result_count(self):
        assert len(semantic_search("anything", top_k=1)) == 1
        assert len(semantic_search("anything", top_k=10)) == len(kb.DOCUMENTS)

    def test_each_result_has_expected_shape(self):
        result = semantic_search("anything", top_k=1)[0]
        assert set(result) == {"id", "text", "score"}
        assert isinstance(result["score"], float)
        assert 0.0 < result["score"] <= 1.0

    def test_collection_is_indexed_once_and_cached(self):
        with patch.object(kb, "embed", side_effect=_stub_embed) as mock_embed:
            kb._collection = None
            semantic_search("first query")
            semantic_search("second query")

        # One call embeds all documents at index time; one call per query —
        # the collection is never rebuilt or re-embedded on later searches.
        doc_batches = [c for c in mock_embed.call_args_list if len(c.args[0]) > 1]
        query_batches = [c for c in mock_embed.call_args_list if len(c.args[0]) == 1]
        assert len(doc_batches) == 1
        assert len(query_batches) == 2
