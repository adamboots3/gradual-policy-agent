import json

import pytest
from policy_agent.ingestion import index_source, parse_document
from policy_agent.retrieval import corpus_status, search


def test_citations_reproduce_exact_source_lines():
    text = "---\ntitle: Policy\n---\n\n## Appeals\n\nAppeal here.\n\n### Time\nSix months.\n"
    chunks = parse_document(text, "Policies/example policy.md", "a" * 40)
    assert [c.heading for c in chunks] == ["Appeals", "Appeals > Time"]
    assert all(c.title == "Policy" for c in chunks)
    for chunk in chunks:
        assert chunk.content == "\n".join(text.splitlines()[chunk.start_line - 1 : chunk.end_line])
        assert "%20" in chunk.source_url
        assert chunk.source_url.endswith(f"#L{chunk.start_line}-L{chunk.end_line}")
    assert chunks == parse_document(text, "Policies/example policy.md", "a" * 40)


def test_code_headings_do_not_change_section():
    chunks = parse_document("## Real\n```sh\n# Not a heading\n```\n", "p.md", "abc")
    assert len(chunks) == 1
    assert chunks[0].heading == "Real"


def test_long_sections_split_without_losing_lines():
    text = "## Heading\n\n" + ("This is one paragraph.\n\n" * 40)
    chunks = parse_document(text, "p.md", "abc", max_chars=100)
    assert len(chunks) > 1
    recovered = "\n".join(c.content for c in chunks)
    assert recovered.count("This is one paragraph.") == 40
    assert all(c.heading == "Heading" for c in chunks)


def test_unclosed_metadata_rejected():
    with pytest.raises(ValueError, match="Unclosed"):
        parse_document("---\ntitle: Bad", "bad.md", "abc")


def test_index_is_idempotent(corpus):
    repo, db, lock = corpus
    before = search(db, "appeals")
    index_source(repo, db, lock)
    assert search(db, "appeals") == before
    assert corpus_status(db)["documents"] == 1


def test_dirty_source_does_not_replace_index(corpus):
    repo, db, lock = corpus
    before = corpus_status(db)
    (repo / "Policies" / "appeals.md").write_text("Changed", encoding="utf-8")
    with pytest.raises(ValueError, match="clean checkout"):
        index_source(repo, db, lock)
    assert corpus_status(db) == before
    assert search(db, "appeals")


def test_wrong_commit_rejected(corpus):
    repo, db, lock = corpus
    config = json.loads(lock.read_text())
    config["commit"] = "0" * 40
    lock.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="locked commit"):
        index_source(repo, db, lock)
