"""Deterministic English keyword baseline. Semantic fusion is a later milestone."""

import json
import re
from pathlib import Path

from policy_agent.storage import connect

STOPWORDS = set(
    (
        "a an the is are was were can could do does how what which "
        "i my to of in on for and or it github"
    ).split()
)


def search(database: Path, query: str, limit: int = 6) -> list[dict]:
    terms = [
        term
        for term in dict.fromkeys(re.findall(r"[a-zA-Z0-9]+", query.lower()))
        if term not in STOPWORDS
    ][:32]
    if not terms:
        return []
    # Construct FTS syntax exclusively from tokenized words, never from user operators.
    expression = " OR ".join(f'"{term}"' for term in terms)
    with connect(database) as db:
        rows = db.execute(
            """
            SELECT c.*, bm25(chunks_fts, 0, 5, 3, 1) AS score
            FROM chunks_fts JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ? ORDER BY score, c.chunk_id LIMIT ?
        """,
            (expression, max(1, min(limit, 20))),
        ).fetchall()
    return [dict(row) for row in rows]


def corpus_status(database: Path) -> dict:
    with connect(database) as db:
        row = db.execute("SELECT value FROM metadata WHERE key='corpus'").fetchone()
    return json.loads(row[0]) if row else {"commit": None, "documents": 0, "chunks": 0}
