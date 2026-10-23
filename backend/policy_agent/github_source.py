"""Read github/site-policy online, with an immutable snapshot and request-only memory."""

import base64
import hashlib
import json
import re
from urllib.parse import quote

import httpx

from policy_agent.config import Settings

REPOSITORY = "github/site-policy"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
API = f"https://api.github.com/repos/{REPOSITORY}"
SHA = re.compile(r"^[0-9a-f]{40}$")


class PolicySourceError(Exception):
    """Sanitized online-source failure. Never substitute model memory for a failed read."""


class PolicyToolError(ValueError):
    """Server-authored safe correction for an invalid tool request."""


class PolicyRepository:
    def __init__(self, settings: Settings, *, transport=None):
        self.settings = settings
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "policy-support-agent"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self.client = httpx.Client(
            headers=headers, timeout=20, transport=transport, follow_redirects=False
        )
        self.commit: str | None = None
        self.documents: dict[str, dict] | None = None
        self.files: dict[str, list[str]] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()
        self.files.clear()
        self.documents = None

    def _get(self, route: str, *, params=None, limit=2_000_000):
        try:
            with self.client.stream("GET", API + route, params=params) as response:
                if response.status_code in (403, 429):
                    raise PolicySourceError(
                        "GitHub denied or rate-limited policy access. Check the optional "
                        "POLICY_GITHUB_TOKEN, or retry after the GitHub rate limit resets."
                    )
                if response.status_code != 200:
                    raise PolicySourceError(
                        "GitHub policy access failed. Check POLICY_GITHUB_REF and network access, "
                        "then retry. No policy answer was generated from this failed read."
                    )
                body = bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body) > limit:
                        raise PolicySourceError("GitHub policy response exceeds the allowed size.")
                return json.loads(body)
        except (httpx.HTTPError, ValueError) as exc:
            raise PolicySourceError(
                "Cannot read GitHub policies. Check network access and retry."
            ) from exc

    def list_documents(self):
        if self.documents is None:
            value = self._get("/commits/" + quote(self.settings.github_ref, safe=""))
            commit = value.get("sha", "")
            tree = value.get("commit", {}).get("tree", {}).get("sha", "")
            if not SHA.fullmatch(commit) or not SHA.fullmatch(tree):
                raise PolicySourceError("GitHub returned invalid policy snapshot metadata.")
            result = self._get(f"/git/trees/{tree}", params={"recursive": "1"}, limit=8_000_000)
            if result.get("truncated"):
                raise PolicySourceError(
                    "GitHub returned an incomplete policy directory; retry later."
                )
            documents = {}
            for entry in result.get("tree", []):
                path = entry.get("path", "")
                if (
                    path.startswith("Policies/")
                    and path.endswith(".md")
                    and entry.get("type") == "blob"
                    and entry.get("mode") in ("100644", "100755")
                    and SHA.fullmatch(entry.get("sha", ""))
                ):
                    documents[path] = {
                        "path": path,
                        "bytes": entry.get("size", 0),
                        "sha": entry["sha"],
                    }
            if not documents or len(documents) > 1000:
                raise PolicySourceError(
                    "GitHub policy directory is empty or exceeds the allowed size."
                )
            self.commit, self.documents = commit, documents
        return {
            "repository": REPOSITORY,
            "commit": self.commit,
            "documents": [
                {"path": row["path"], "bytes": row["bytes"]}
                for _, row in sorted(self.documents.items())
            ],
        }

    def read_document(self, path: str, start_line: int = 1, line_count: int = 200):
        if self.documents is None:
            raise PolicyToolError("Call list_policy_documents before choosing a file to read.")
        # Exact membership blocks traversal, URLs, symlinks and paths outside Policies/.
        if path not in self.documents:
            raise PolicyToolError("Choose an exact Markdown file path from the policy directory.")
        if start_line < 1 or not 1 <= line_count <= 200:
            raise PolicyToolError("Use a positive start_line and a line_count between 1 and 200.")
        if path not in self.files:
            entry = self.documents[path]
            if entry["bytes"] > 512_000:
                raise PolicyToolError("This policy file exceeds the 512 KB reading limit.")
            blob = self._get(f"/git/blobs/{entry['sha']}")
            try:
                if blob.get("encoding") != "base64":
                    raise PolicyToolError("Unsupported blob encoding")
                raw = base64.b64decode("".join(blob["content"].split()), validate=True)
                digest = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                if len(raw) > 512_000 or digest != entry["sha"]:
                    raise PolicyToolError("Blob identity mismatch")
                self.files[path] = raw.decode("utf-8").splitlines()
            except (ValueError, KeyError, UnicodeError) as exc:
                raise PolicySourceError(
                    "GitHub policy file content failed integrity validation."
                ) from exc
        lines = self.files[path]
        if start_line > len(lines):
            raise PolicyToolError(f"start_line exceeds the document's {len(lines)} lines.")
        selected = []
        size = 0
        for line in lines[start_line - 1 : start_line - 1 + line_count]:
            if size + len(line) + 16 > self.settings.read_max_chars:
                break
            selected.append(line)
            size += len(line) + 16
        if not selected:
            raise PolicyToolError(
                "This line exceeds the per-read text limit. Read another section."
            )
        end = start_line + len(selected) - 1
        source_id = hashlib.sha256(f"{self.commit}:{path}:{start_line}:{end}".encode()).hexdigest()[
            :20
        ]
        return {
            "source_id": source_id,
            "title": next(
                (
                    line.split(":", 1)[1].strip().strip("\"'")
                    for line in lines[:15]
                    if line.startswith("title:")
                ),
                path.rsplit("/", 1)[-1].removesuffix(".md"),
            ),
            "path": path,
            "commit_sha": self.commit,
            "start_line": start_line,
            "end_line": end,
            "total_lines": len(lines),
            "next_start_line": end + 1 if end < len(lines) else None,
            "content": "\n".join(selected),
            "numbered_content": "\n".join(
                f"{i}: {line}" for i, line in enumerate(selected, start_line)
            ),
        }


def citation_from_read(record: dict, start: int, end: int):
    if not record["start_line"] <= start <= end <= record["end_line"] or end - start >= 80:
        raise PolicyToolError(
            "Citations must select 1–80 lines from a document range read in this turn."
        )
    content = "\n".join(
        record["content"].split("\n")[start - record["start_line"] : end - record["start_line"] + 1]
    )
    return {
        "source_id": record["source_id"],
        "title": record["title"],
        "heading": "",
        "content": content,
        "path": record["path"],
        "start_line": start,
        "end_line": end,
        "commit_sha": record["commit_sha"],
        "source_url": (
            f"{REPOSITORY_URL}/blob/{record['commit_sha']}/"
            f"{quote(record['path'], safe='/')}#L{start}-L{end}"
        ),
    }
