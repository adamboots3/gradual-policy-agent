"""Index a clean, pinned Git checkout without changing its original line numbers."""

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

import yaml

from policy_agent.storage import connect


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    title: str
    heading: str
    content: str
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    source_url: str
    content_hash: str


def parse_document(text: str, path: str, commit: str, max_chars: int = 2400) -> list[Chunk]:
    lines = text.splitlines()
    start = 0
    title = Path(path).stem
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            raise ValueError(f"Unclosed YAML front matter: {path}")
        metadata = yaml.safe_load("\n".join(lines[1:end])) or {}
        title = str(metadata.get("title", title))
        start = end + 1

    chunks: list[Chunk] = []
    headings: list[tuple[int, str]] = []
    block_start = start
    block_size = 0
    in_fence = False

    def emit(end: int) -> None:
        nonlocal block_start, block_size
        lo, hi = block_start, end
        while lo < hi and not lines[lo].strip():
            lo += 1
        while hi > lo and not lines[hi - 1].strip():
            hi -= 1
        content = "\n".join(lines[lo:hi])
        if content and re.sub(r"<!--.*?-->", "", content, flags=re.S).strip():
            digest = hashlib.sha256(content.encode()).hexdigest()
            chunk_id = hashlib.sha256(f"{commit}:{path}:{lo + 1}:{digest}".encode()).hexdigest()[
                :20
            ]
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    title=title,
                    heading=" > ".join(h for _, h in headings),
                    content=content,
                    path=path,
                    start_line=lo + 1,
                    end_line=hi,
                    commit_sha=commit,
                    source_url=(
                        f"https://github.com/github/site-policy/blob/{commit}/"
                        f"{quote(path, safe='/')}#L{lo + 1}-L{hi}"
                    ),
                    content_hash=digest,
                )
            )
        block_start, block_size = end, 0

    for i in range(start, len(lines)):
        line = lines[i]
        heading = None if in_fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            emit(i)
            level, label = len(heading[1]), heading[2]
            headings[:] = [(depth, name) for depth, name in headings if depth < level]
            headings.append((level, label))
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        block_size += len(line) + 1
        # Split at paragraph boundaries; preserve whole paragraphs/tables/code blocks.
        if block_size >= max_chars and not line.strip() and not in_fence:
            emit(i + 1)
    emit(len(lines))
    return chunks


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def sync_source(lock_path: Path, repo: Path) -> str:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if not repo.exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", lock["repository"], str(repo)], check=True)
    if git(repo, "remote", "get-url", "origin") != lock["repository"]:
        raise ValueError("Source origin does not match corpus.lock.json")
    if git(repo, "status", "--porcelain"):
        raise ValueError("Source checkout has local changes; refusing to overwrite them")
    subprocess.run(["git", "-C", str(repo), "fetch", "origin", lock["commit"]], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "--detach", lock["commit"]], check=True)
    return lock["commit"]


def index_source(repo: Path, database: Path, lock_path: Path) -> dict:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    commit = git(repo, "rev-parse", "HEAD")
    if commit != lock["commit"] or git(repo, "status", "--porcelain"):
        raise ValueError("Index requires a clean checkout at the locked commit; run sync first")
    paths = sorted(repo.glob(lock["include"]))
    if not paths:
        raise ValueError("No policy documents found")
    chunks = [
        chunk
        for path in paths
        for chunk in parse_document(
            path.read_text(encoding="utf-8"),
            path.relative_to(repo).as_posix(),
            commit,
        )
    ]
    manifest = {
        "commit": commit,
        "documents": len(paths),
        "chunks": len(chunks),
        "parser_version": lock["parser_version"],
    }
    with connect(database) as db:
        db.execute("DELETE FROM embeddings")
        db.execute("DELETE FROM metadata WHERE key='embeddings'")
        db.execute("DELETE FROM chunks")
        db.execute("DELETE FROM chunks_fts")
        for chunk in chunks:
            row = asdict(chunk)
            db.execute(
                f"INSERT INTO chunks ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
                list(row.values()),
            )
            db.execute(
                "INSERT INTO chunks_fts(chunk_id,title,heading,content) VALUES (?,?,?,?)",
                (chunk.chunk_id, chunk.title, chunk.heading, chunk.content),
            )
        db.execute(
            "INSERT OR REPLACE INTO metadata(key,value) VALUES ('corpus',?)",
            (json.dumps(manifest),),
        )
    return manifest
