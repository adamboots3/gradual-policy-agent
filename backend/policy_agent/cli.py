import argparse
import json
from pathlib import Path

from policy_agent.config import Settings
from policy_agent.conversations import ConversationService
from policy_agent.ingestion import index_source, sync_source
from policy_agent.providers import ConfigurationError
from policy_agent.retrieval import corpus_status
from policy_agent.semantic import Retriever, build_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducible GitHub policy corpus tools")
    parser.add_argument("command", choices=["sync", "index", "embed", "search", "status", "chat"])
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--lock", type=Path, default=Path("corpus.lock.json"))
    parser.add_argument("--conversation", help="Resume an existing conversation ID")
    args = parser.parse_args()
    settings = Settings()
    repo = settings.data_dir / "source" / "site-policy"
    if args.command == "sync":
        result = {"commit": sync_source(args.lock, repo)}
    elif args.command == "index":
        result = index_source(repo, settings.database, args.lock)
    elif args.command == "search":
        if not args.query.strip():
            parser.error("search requires a nonempty query")
        result = Retriever(settings).search(args.query)
    elif args.command == "embed":
        result = build_embeddings(settings)
    elif args.command == "chat":
        service = ConversationService(settings)
        conversation = args.conversation or service.create()["id"]
        print(f"Conversation: {conversation} (type /exit to quit)")
        while True:
            try:
                question = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if question == "/exit":
                break
            if not question:
                continue
            try:
                response = service.chat(conversation, question)
                print(f"Agent: {response['answer']}")
                for citation in response["citations"]:
                    print(f"[{citation['label']}] {citation['title']} — {citation['source_url']}")
            except ConfigurationError as exc:
                print(f"Configuration: {exc}")
            except Exception as exc:
                print(f"Request failed ({type(exc).__name__}); no partial turn was saved.")
        return
    else:
        result = corpus_status(settings.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
