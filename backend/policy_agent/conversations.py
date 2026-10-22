"""Durable finalized turns; failed graph runs never become conversation history."""

import json
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from policy_agent.agent import PROMPT_VERSION, build_agent
from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError, create_chat
from policy_agent.retrieval import corpus_status
from policy_agent.semantic import Retriever

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS turns (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
  question TEXT NOT NULL, response TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, status TEXT NOT NULL,
  metadata TEXT NOT NULL
);
"""


class ConversationNotFound(LookupError):
    pass


class ConversationService:
    """Use one service per process. Local deployment supports one API worker."""

    def __init__(self, settings: Settings, model_factory=create_chat, retriever=None):
        self.settings = settings
        self.model_factory = model_factory
        self.retriever = retriever or Retriever(settings)
        self._guard = threading.Lock()
        self._locks = {}

    @contextmanager
    def connect(self):
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        with (
            closing(
                sqlite3.connect(self.settings.data_dir / "conversations.sqlite3", timeout=30)
            ) as db,
            db,
        ):
            db.row_factory = sqlite3.Row
            db.executescript(SCHEMA)
            yield db

    def lock(self, conversation_id):
        with self._guard:
            return self._locks.setdefault(conversation_id, threading.Lock())

    def create(self):
        row = {"id": str(uuid4()), "created_at": datetime.now(UTC).isoformat()}
        with self.connect() as db:
            db.execute("INSERT INTO conversations VALUES (?,?)", tuple(row.values()))
        return row

    def list(self):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute("""
                    SELECT c.*,
                      COALESCE((SELECT substr(question,1,90) FROM turns
                                WHERE conversation_id=c.id ORDER BY sequence LIMIT 1),
                               'New conversation') AS title,
                      (SELECT count(*) FROM turns WHERE conversation_id=c.id) AS turn_count
                    FROM conversations c ORDER BY created_at DESC
                """)
            ]

    def get(self, conversation_id):
        with self.connect() as db:
            conversation = db.execute(
                "SELECT * FROM conversations WHERE id=?", (conversation_id,)
            ).fetchone()
            if not conversation:
                raise ConversationNotFound(conversation_id)
            turns = db.execute(
                "SELECT question,response FROM turns WHERE conversation_id=? ORDER BY sequence",
                (conversation_id,),
            ).fetchall()
        return {
            **dict(conversation),
            "turns": [
                {"question": row["question"], "response": json.loads(row["response"])}
                for row in turns
            ],
        }

    def delete(self, conversation_id):
        with self.lock(conversation_id):
            self.get(conversation_id)
            with SqliteSaver.from_conn_string(
                str(self.settings.data_dir / "checkpoints.sqlite3")
            ) as saver:
                saver.delete_thread(conversation_id)
            with self.connect() as db:
                for table in ("turns", "runs"):
                    db.execute(f"DELETE FROM {table} WHERE conversation_id=?", (conversation_id,))
                db.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))

    def chat(self, conversation_id: str, question: str) -> dict:
        if not question.strip() or len(question) > 4000:
            raise ValueError("Question must contain 1–4000 characters.")
        with self.lock(conversation_id):
            conversation = self.get(conversation_id)
            corpus = corpus_status(self.settings.database)
            if not corpus["chunks"]:
                raise ConfigurationError("Knowledge base is empty. Run sync and index first.")
            messages = []
            for turn in conversation["turns"][-self.settings.history_turns :]:
                messages.extend(
                    [
                        HumanMessage(content=turn["question"]),
                        AIMessage(content=turn["response"]["answer"]),
                    ]
                )
            messages.append(HumanMessage(content=question.strip()))
            run_id, started = str(uuid4()), time.perf_counter()
            metadata = {
                "run_id": run_id,
                "corpus_commit": corpus["commit"],
                "prompt_version": PROMPT_VERSION,
                "model": self.settings.chat_model,
                "provider": self.settings.chat_provider,
                "retrieval_mode": self.settings.retrieval_mode,
            }
            try:
                model = self.model_factory(self.settings)
                with SqliteSaver.from_conn_string(
                    str(self.settings.data_dir / "checkpoints.sqlite3")
                ) as saver:
                    graph = build_agent(
                        model, self.retriever, self.settings.max_search_calls, saver
                    )
                    # Replace ALL state, even after a failed prior run: canonical completed turns
                    # are the only dialogue history. Tool evidence and budgets are per-turn.
                    state = graph.invoke(
                        {
                            "messages": messages,
                            "evidence": {},
                            "search_calls": 0,
                            "model_calls": 0,
                            "result": {},
                            "trace": [],
                            "question": question.strip(),
                        },
                        {"configurable": {"thread_id": conversation_id}, "recursion_limit": 40},
                    )
                if corpus != corpus_status(self.settings.database):
                    raise ConfigurationError("Corpus changed during this turn. Please retry.")
                metadata.update(
                    {
                        "latency_ms": round((time.perf_counter() - started) * 1000),
                        "model_calls": state["model_calls"],
                        "trace": state["trace"],
                    }
                )
                response = {
                    **state["result"],
                    **{k: v for k, v in metadata.items() if k != "trace"},
                }
                with self.connect() as db:
                    db.execute(
                        "INSERT INTO turns(conversation_id,question,response) VALUES (?,?,?)",
                        (conversation_id, question.strip(), json.dumps(response)),
                    )
                    db.execute(
                        "INSERT INTO runs VALUES (?,?,?,?)",
                        (run_id, conversation_id, "completed", json.dumps(metadata)),
                    )
                return response
            except Exception as exc:
                metadata.update(
                    {
                        "error_type": type(exc).__name__,
                        "latency_ms": round((time.perf_counter() - started) * 1000),
                    }
                )
                with self.connect() as db:
                    db.execute(
                        "INSERT INTO runs VALUES (?,?,?,?)",
                        (run_id, conversation_id, "failed", json.dumps(metadata)),
                    )
                raise
