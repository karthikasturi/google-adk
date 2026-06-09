"""
tests/test_kb.py — Unit tests for Day 06's PDF-backed semantic search
-------------------------------------------------------------------------
No network calls: kb.embed is patched with a stub that hands back
hand-picked vectors. Both the PDF-loading step and the vector backend run
for real — pypdf against the actual sample PDFs in docs/, and ChromaDB as
an in-memory EphemeralClient (the default MemoryBackend, same engine Day 05
uses) — only the embedding API call is stubbed. So loading, metadata,
indexing, and ranking/top_k are all checked end to end, offline and
deterministically.

Run with:  python -m pytest tests/ -v
"""

import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the day06 root importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

import kb
from kb import load_pdf_chunks, semantic_search

_CHUNKS = load_pdf_chunks()

# One unit vector per chunk, each at a slightly larger angle from the query
# vector. For unit vectors, L2 distance grows monotonically with the angle
# between them, so nearest-neighbour ranking is just "chunk order" —
# fully deterministic, with no ties to worry about.
_FAKE_QUERY_EMBEDDING = [1.0, 0.0]
_FAKE_CHUNK_EMBEDDINGS = [
    [math.cos(i * math.radians(10)), math.sin(i * math.radians(10))]
    for i in range(len(_CHUNKS))
]


def _stub_embed(texts):
    """Return the query embedding for a single-text batch, chunk embeddings otherwise."""
    if len(texts) == 1:
        return [_FAKE_QUERY_EMBEDDING]
    return _FAKE_CHUNK_EMBEDDINGS[: len(texts)]


@pytest.fixture(autouse=True)
def _reset_backend():
    """Each test gets a clean in-memory backend and a stubbed embed() — no API calls, no AWS."""
    kb._backend = None
    with patch.object(kb, "embed", side_effect=_stub_embed):
        yield
    kb._backend = None


class TestLoadPdfChunks:
    def test_loads_one_chunk_per_pdf_page(self):
        # Every sample PDF in docs/ is two pages of real, extractable text.
        assert len(_CHUNKS) == 2 * len(list(kb.DOCS_DIR.glob("*.pdf")))

    def test_each_chunk_carries_source_and_page_metadata(self):
        for chunk in _CHUNKS:
            assert set(chunk) == {"id", "text", "metadata"}
            assert set(chunk["metadata"]) == {"source", "page"}
            assert chunk["metadata"]["source"].endswith(".pdf")
            assert chunk["metadata"]["page"] >= 1
            assert chunk["text"].strip()

    def test_chunk_ids_are_unique_and_traceable(self):
        ids = [c["id"] for c in _CHUNKS]
        assert len(ids) == len(set(ids))
        for chunk in _CHUNKS:
            stem = chunk["metadata"]["source"].removesuffix(".pdf")
            assert chunk["id"] == f"{stem}-p{chunk['metadata']['page']}"


class TestSemanticSearch:
    def test_empty_query_returns_no_results(self):
        assert semantic_search("") == []
        assert semantic_search("   ") == []

    def test_returns_top_k_ranked_by_similarity(self):
        results = semantic_search("anything", top_k=2)

        assert len(results) == 2
        # By construction, the angle to the query strictly increases with
        # chunk index — so the expected nearest-neighbour order is just
        # chunk order, closest (highest score) first.
        assert results[0]["id"] == _CHUNKS[0]["id"]
        assert results[1]["id"] == _CHUNKS[1]["id"]
        assert results[0]["score"] > results[1]["score"]

    def test_top_k_limits_result_count(self):
        assert len(semantic_search("anything", top_k=1)) == 1
        assert len(semantic_search("anything", top_k=10)) == len(_CHUNKS)

    def test_each_result_carries_metadata_through_retrieval(self):
        result = semantic_search("anything", top_k=1)[0]
        assert set(result) == {"id", "text", "metadata", "score"}
        assert set(result["metadata"]) == {"source", "page"}
        assert isinstance(result["score"], float)
        assert 0.0 < result["score"] <= 1.0

    def test_backend_is_indexed_once_and_cached(self):
        with patch.object(kb, "embed", side_effect=_stub_embed) as mock_embed:
            kb._backend = None
            semantic_search("first query")
            semantic_search("second query")

        # One call embeds all chunks at index time; one call per query — the
        # backend is never rebuilt or re-embedded on later searches.
        chunk_batches = [c for c in mock_embed.call_args_list if len(c.args[0]) > 1]
        query_batches = [c for c in mock_embed.call_args_list if len(c.args[0]) == 1]
        assert len(chunk_batches) == 1
        assert len(query_batches) == 2
