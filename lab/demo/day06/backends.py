"""
backends.py — Configurable vector store backends (the single swap point)
--------------------------------------------------------------------------
Concept: Module 6 — Vector databases, local vs. cloud

Two backends, one tiny interface — `upsert(...)` and `query(...)` — so
kb.py never needs to know which vector store it's talking to:

    MemoryBackend      — ChromaDB EphemeralClient, in-process, no setup.
                         Same engine as Day 05, good for local dev and tests.
    OpenSearchBackend  — AWS OpenSearch with the k-NN plugin, the
                         production-shaped option for a real deployment.

kb.get_backend() reads VECTOR_BACKEND ("memory" | "opensearch") and returns
one of these — exactly the SESSION_BACKEND pattern from Day 04's session.py,
applied to vector storage instead of session storage.
"""

import time
from typing import Any

import chromadb


class MemoryBackend:
    """In-process vector store backed by a ChromaDB EphemeralClient collection."""

    def __init__(self, collection_name: str):
        client = chromadb.EphemeralClient()
        self._collection = client.get_or_create_collection(name=collection_name)

    def upsert(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            {"id": doc_id, "text": text, "metadata": dict(meta), "score": 1.0 / (1.0 + distance)}
            for doc_id, text, meta, distance in zip(ids, documents, metadatas, distances)
        ]


class OpenSearchBackend:
    """
    Cloud vector store backed by an AWS OpenSearch k-NN index — either a
    managed OpenSearch *domain* or an OpenSearch *Serverless* collection.

    Authenticates with the standard AWS credential chain (environment
    variables, shared config, instance role, ...) via boto3 + OpenSearch's
    AWSV4SignerAuth — no separate username/password to manage. The two
    flavors share one wire protocol and k-NN mapping; the only thing that
    differs is the SigV4 service name used to sign requests:

        managed domain          → "es"    (VECTOR_BACKEND=opensearch)
        Serverless collection   → "aoss"  (VECTOR_BACKEND=opensearch-serverless)

    Pass `serverless=True` when `host` is a collection endpoint
    (`*.aoss.amazonaws.com`) rather than a domain endpoint
    (`*.es.amazonaws.com`) — see kb.get_backend().
    """

    def __init__(self, host: str, region: str, index_name: str, dimension: int, serverless: bool = False):
        import boto3
        from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, "aoss" if serverless else "es")
        self._client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            # The default 10s read timeout is too tight for indexing requests
            # carrying full embedding vectors, especially against a freshly
            # created (still "warming up") Serverless collection.
            timeout=60,
        )
        self._index = index_name
        # Serverless rejects the `refresh` request parameter outright (it
        # only offers near-real-time search) — managed domains support it
        # and we want it here so the index is searchable immediately after
        # the one-time startup load, before the first query runs.
        self._serverless = serverless
        self._ensure_index(dimension)

    def _ensure_index(self, dimension: int) -> None:
        mapping = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "text": {"type": "text"},
                    "embedding": {"type": "knn_vector", "dimension": dimension},
                    "source": {"type": "keyword"},
                    "page": {"type": "integer"},
                }
            },
        }
        exists = self._client.indices.exists(index=self._index)
        if self._serverless:
            # Serverless vector-search collections reject a caller-supplied
            # document _id outright (see upsert), so there's no way to
            # *upsert* a chunk by its deterministic id — re-running would
            # just pile up duplicates of every page. Dropping and recreating
            # the index on every startup keeps it exactly matching docs/ and
            # sidesteps the limitation entirely; for a handful of short PDFs,
            # re-embedding on each run is cheap enough for a demo.
            if exists:
                self._client.indices.delete(index=self._index)
            self._client.indices.create(index=self._index, body=mapping)
        elif not exists:
            self._client.indices.create(index=self._index, body=mapping)

    def upsert(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        for doc_id, text, embedding, meta in zip(ids, texts, embeddings, metadatas):
            # chunk_id always rides along as a regular field — it's the only
            # way to trace a Serverless hit back to its source chunk, since
            # Serverless assigns the _id itself (see _ensure_index).
            body = {"chunk_id": doc_id, "text": text, "embedding": embedding, **meta}
            if self._serverless:
                self._client.index(index=self._index, body=body)
            else:
                self._client.index(index=self._index, id=doc_id, body=body, refresh=True)

        if self._serverless:
            self._wait_until_searchable(expected=len(ids))

    def _wait_until_searchable(self, expected: int, timeout: float = 180.0, poll_interval: float = 5.0) -> None:
        """
        `refresh` isn't an option on Serverless — it's near-real-time only,
        and empirically that "near" can mean anywhere from ~10s to over a
        minute for a freshly created index (measured by hand against a live
        collection: 0 visible docs at 30s, 5/6 at 45s, 6/6 at 60s). A fixed
        sleep would either race the index on a slow day or waste time on a
        fast one, so poll `match_all` until the expected count actually shows
        up — that's exactly as long as the demo's one-time startup load needs
        to wait before the first query can rely on a complete index.

        The same propagation lag applies one level up, too: right after
        `_ensure_index` drops and recreates the index, the *search* path can
        still 404 with "no such index" for a while — the new index hasn't
        propagated to it yet, even though indexing requests already succeed
        against it. Treat that 404 the same as "0 documents visible so far"
        and keep polling rather than letting it bubble up as a hard failure.
        """
        from opensearchpy.exceptions import NotFoundError

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = self._client.search(index=self._index, body={"size": 0, "query": {"match_all": {}}})
            except NotFoundError:
                time.sleep(poll_interval)
                continue
            if response["hits"]["total"]["value"] >= expected:
                return
            time.sleep(poll_interval)

    def query(self, query_embedding: list[float], top_k: int) -> list[dict]:
        response = self._client.search(
            index=self._index,
            body={
                "size": top_k,
                "query": {"knn": {"embedding": {"vector": query_embedding, "k": top_k}}},
            },
        )
        return [
            {
                "id": hit["_source"].get("chunk_id", hit["_id"]),
                "text": hit["_source"]["text"],
                "metadata": {
                    k: v for k, v in hit["_source"].items()
                    if k not in ("chunk_id", "text", "embedding")
                },
                # OpenSearch k-NN scores are already similarities in (0, 1] — no conversion needed.
                "score": hit["_score"],
            }
            for hit in response["hits"]["hits"]
        ]
