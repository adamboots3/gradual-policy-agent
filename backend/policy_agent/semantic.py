"""Versioned embedding cache and reciprocal-rank hybrid retrieval."""

import hashlib
import json

import numpy as np

from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError, create_embeddings
from policy_agent.retrieval import corpus_status, search
from policy_agent.storage import connect


def fingerprint(settings: Settings) -> str:
    value = [
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_base_url.rstrip("/"),
        "title-heading-content-v1",
    ]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def input_text(row: dict) -> str:
    return f"{row['title']}\n{row['heading']}\n{row['content']}"


def normalize(values) -> np.ndarray:
    try:
        matrix = np.asarray(values, dtype=np.float64)
    except (ValueError, TypeError) as exc:
        raise ConfigurationError("Embedding vectors must be numeric and rectangular.") from exc
    if matrix.ndim != 2 or not matrix.size or not np.isfinite(matrix).all():
        raise ConfigurationError("Embedding vectors must be finite, nonempty and rectangular.")
    # Scale first to avoid overflow for large finite vectors.
    scale = np.max(np.abs(matrix), axis=1, keepdims=True)
    if (scale == 0).any():
        raise ConfigurationError("Embedding vectors must have nonzero norm.")
    matrix = matrix / scale
    lengths = np.linalg.norm(matrix, axis=1, keepdims=True)
    if (lengths == 0).any():
        raise ConfigurationError("Embedding vectors must have nonzero norm.")
    return matrix / lengths


def build_embeddings(settings: Settings, embedder=None, batch_size: int | None = None) -> dict:
    batch_size = settings.embedding_batch_size if batch_size is None else batch_size
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    embedder = embedder if embedder is not None else create_embeddings(settings)
    with connect(settings.database) as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM chunks ORDER BY chunk_id")]
        corpus = db.execute("SELECT value FROM metadata WHERE key='corpus'").fetchone()
        old = db.execute("SELECT value FROM metadata WHERE key='embeddings'").fetchone()
        cached = {r["chunk_id"]: dict(r) for r in db.execute("SELECT * FROM embeddings")}
    if not rows or not corpus:
        raise ConfigurationError("Index the policy corpus before building embeddings.")
    identity = fingerprint(settings)
    if not old or json.loads(old[0])["fingerprint"] != identity:
        cached = {}
    payloads = [input_text(row) for row in rows]
    hashes = [hashlib.sha256(text.encode()).hexdigest() for text in payloads]
    vectors = [None] * len(rows)
    pending = []
    for i, row in enumerate(rows):
        previous = cached.get(row["chunk_id"])
        if previous and previous["input_hash"] == hashes[i]:
            vectors[i] = json.loads(previous["vector"])
        else:
            pending.append(i)
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        output = embedder.embed_documents([payloads[i] for i in batch])
        if len(output) != len(batch):
            raise ConfigurationError("Embedding provider returned an incorrect batch length.")
        for index, vector in zip(batch, output, strict=True):
            vectors[index] = vector
    matrix = normalize(vectors)
    manifest = {
        "fingerprint": identity,
        "dimensions": matrix.shape[1],
        "chunks": len(rows),
        "corpus": json.loads(corpus[0]),
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
    }
    with connect(settings.database) as db:
        # Reserve the write transaction before checking concurrent corpus replacement.
        db.execute("BEGIN IMMEDIATE")
        current = db.execute("SELECT value FROM metadata WHERE key='corpus'").fetchone()
        current_ids = [r[0] for r in db.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id")]
        if not current or current[0] != corpus[0] or current_ids != [r["chunk_id"] for r in rows]:
            raise ConfigurationError("Corpus changed during embedding. Retry the build.")
        db.execute("DELETE FROM embeddings")
        db.executemany(
            "INSERT INTO embeddings VALUES (?,?,?)",
            [
                (row["chunk_id"], digest, json.dumps(vector.tolist()))
                for row, digest, vector in zip(rows, hashes, matrix, strict=True)
            ],
        )
        db.execute(
            "INSERT OR REPLACE INTO metadata VALUES ('embeddings',?)", (json.dumps(manifest),)
        )
    return {**manifest, "embedded_now": len(pending)}


class Retriever:
    def __init__(self, settings: Settings, embedder_factory=create_embeddings):
        self.settings = settings
        self.embedder_factory = embedder_factory

    def search_with_context(self, query: str) -> list[dict]:
        """Add bounded neighboring sections, preserving each source's citation identity."""
        seeds = self.search(query)
        evidence = {row["chunk_id"]: row for row in seeds}
        with connect(self.settings.database) as db:
            for seed in seeds[:3]:
                # A following section often contains a rule qualified in the preceding
                # section. Both directions help avoid answering from isolated fragments.
                for direction, order in ((">", "ASC"), ("<", "DESC")):
                    row = db.execute(
                        f"SELECT * FROM chunks WHERE path=? AND start_line {direction} ? "
                        f"ORDER BY start_line {order} LIMIT 1",
                        (seed["path"], seed["start_line"]),
                    ).fetchone()
                    if row and row["chunk_id"] not in evidence:
                        evidence[row["chunk_id"]] = {**dict(row), "retrieval_context": True}
                    if len(evidence) >= len(seeds) + 4:
                        return list(evidence.values())
        return list(evidence.values())

    def search(self, query: str, limit: int = 6) -> list[dict]:
        limit = max(1, min(limit, 20))
        if self.settings.retrieval_mode == "keyword":
            return search(self.settings.database, query, limit)
        with connect(self.settings.database) as db:
            raw = db.execute("SELECT value FROM metadata WHERE key='embeddings'").fetchone()
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT c.*, e.vector, e.input_hash FROM chunks c "
                    "JOIN embeddings e ON e.chunk_id=c.chunk_id ORDER BY c.chunk_id"
                )
            ]
        if not raw:
            raise ConfigurationError(
                "Hybrid mode requires an embedding index. Run policy-agent embed."
            )
        meta = json.loads(raw[0])
        if meta["fingerprint"] != fingerprint(self.settings):
            raise ConfigurationError(
                "Embedding configuration changed. Rebuild with policy-agent embed."
            )
        if meta["corpus"] != corpus_status(self.settings.database) or len(rows) != meta["chunks"]:
            raise ConfigurationError("Embedding index does not match the corpus. Rebuild it.")
        if any(
            hashlib.sha256(input_text(row).encode()).hexdigest() != row["input_hash"]
            for row in rows
        ):
            raise ConfigurationError("Embedding input changed. Rebuild the index.")
        embedder = self.embedder_factory(self.settings)
        q = normalize([embedder.embed_query(query)])
        matrix = normalize([json.loads(row["vector"]) for row in rows])
        if q.shape[1] != meta["dimensions"] or matrix.shape[1] != meta["dimensions"]:
            raise ConfigurationError("Embedding dimensions changed. Rebuild the index.")
        scores = (matrix @ q[0]).tolist()
        semantic = sorted(range(len(rows)), key=lambda i: (-scores[i], rows[i]["chunk_id"]))[:20]
        keyword = search(self.settings.database, query, 20)
        ranking = {}
        evidence = {}
        for result_list in (keyword, [rows[i] for i in semantic]):
            for rank, row in enumerate(result_list, 1):
                key = row["chunk_id"]
                ranking[key] = ranking.get(key, 0) + 1 / (60 + rank)
                evidence[key] = {
                    k: v for k, v in row.items() if k not in {"vector", "input_hash", "score"}
                }
        if meta["corpus"] != corpus_status(self.settings.database):
            raise ConfigurationError("Corpus changed during retrieval. Please retry.")
        return [
            {**evidence[key], "score": ranking[key]}
            for key in sorted(ranking, key=lambda key: (-ranking[key], key))[:limit]
        ]
