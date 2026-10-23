"""Knowledge-base initialization only; conversations are available through the web UI."""

import argparse
import json
from pathlib import Path

from policy_agent.config import Settings
from policy_agent.ingestion import index_source, sync_source
from policy_agent.retrieval import corpus_status
from policy_agent.semantic import build_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["sync", "index", "embed", "status"])
    parser.add_argument("--lock", type=Path, default=Path("corpus.lock.json"))
    args = parser.parse_args()
    settings = Settings()
    repo = settings.data_dir / "source" / "site-policy"
    if args.command == "sync":
        result = {"commit": sync_source(args.lock, repo)}
    elif args.command == "index":
        result = index_source(repo, settings.database, args.lock)
    elif args.command == "embed":
        result = build_embeddings(settings)
    else:
        result = corpus_status(settings.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
