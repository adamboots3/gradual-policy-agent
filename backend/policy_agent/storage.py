import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY, title TEXT NOT NULL, heading TEXT NOT NULL,
  content TEXT NOT NULL, path TEXT NOT NULL, start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL, commit_sha TEXT NOT NULL,
  source_url TEXT NOT NULL, content_hash TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED, title, heading, content, tokenize='porter unicode61'
);
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id TEXT PRIMARY KEY, input_hash TEXT NOT NULL, vector TEXT NOT NULL
);
"""


@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=30)) as db, db:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        yield db
