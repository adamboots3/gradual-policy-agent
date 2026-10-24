import base64

import httpx
import pytest
from policy_agent.config import Settings
from policy_agent.github_source import PolicyRepository, PolicySourceError, citation_from_read


def test_directory_then_numbered_reads_use_one_snapshot_and_request_only_cache(corpus):
    with corpus.factory(Settings()) as source:
        directory = source.list_documents()
        assert directory["commit"] == corpus.commit
        assert directory["documents"][0]["path"] == "Policies/appeals.md"
        assert "content" not in str(directory)
        first = source.read_document("Policies/appeals.md", 1, 3)
        assert first["numbered_content"].startswith("1: # Example")
        assert first["next_start_line"] == 4 and first["end_line"] == 3
        second = source.read_document("Policies/appeals.md", 4, 200)
        assert "six months" in second["content"] and second["next_start_line"] is None
        source.list_documents()
        assert len(corpus.calls) == 3  # resolve commit + tree + one blob, no refetch.
        assert corpus.calls[1].url.params["recursive"] == "1"
        assert corpus.calls[1].url.path.endswith(corpus.tree)
        citation = citation_from_read(first, 3, 3)
        assert (
            citation["content"]
            == "Users can appeal an account suspension using the reinstatement form."
        )
        assert citation["source_url"].endswith(f"{corpus.commit}/Policies/appeals.md#L3-L3")
    assert source.files == {} and source.documents is None
    with corpus.factory(Settings()) as fresh:
        fresh.list_documents()
    assert len(corpus.calls) == 5  # No cross-request snapshot cache.


def test_directory_required_before_read(corpus):
    with corpus.factory(Settings()) as source:
        with pytest.raises(ValueError, match="list_policy_documents"):
            source.read_document("Policies/appeals.md")
    assert not corpus.calls


def test_moving_ref_does_not_change_current_question_snapshot(corpus):
    original = corpus.commit
    with corpus.factory(Settings()) as source:
        source.list_documents()
        corpus.commit = "c" * 40  # Simulate upstream changing after the directory was read.
        assert source.read_document("Policies/appeals.md")["commit_sha"] == original
        assert source.list_documents()["commit"] == original
    with corpus.factory(Settings()) as next_question:
        assert next_question.list_documents()["commit"] == corpus.commit


@pytest.mark.parametrize(
    "path",
    [
        "../README.md",
        "Policies/../README.md",
        "https://evil.test/x.md",
        "Policies/unknown.md",
        "README.md",
    ],
)
def test_model_cannot_read_unlisted_paths_or_arbitrary_urls(corpus, path):
    with corpus.factory(Settings()) as source:
        source.list_documents()
        with pytest.raises(ValueError, match="exact Markdown"):
            source.read_document(path)
    assert len(corpus.calls) == 2


def test_directory_excludes_symlinks_and_non_policy_files(corpus):
    base = corpus.respond

    def respond(request):
        value = base(request)
        if "/trees/" in request.url.path:
            body = value.json()
            body["tree"] += [
                {"path": "Policies/link.md", "sha": "c" * 40, "mode": "120000", "type": "blob"},
                {"path": "README.md", "sha": "d" * 40, "mode": "100644", "type": "blob"},
            ]
            return httpx.Response(200, json=body)
        return value

    with PolicyRepository(Settings(), transport=httpx.MockTransport(respond)) as source:
        paths = [d["path"] for d in source.list_documents()["documents"]]
        assert "Policies/link.md" not in paths and "README.md" not in paths


def test_truncated_tree_is_not_presented_as_complete(corpus):
    base = corpus.respond

    def respond(request):
        return (
            httpx.Response(200, json={"truncated": True})
            if "/trees/" in request.url.path
            else base(request)
        )

    with PolicyRepository(Settings(), transport=httpx.MockTransport(respond)) as source:
        with pytest.raises(PolicySourceError, match="incomplete"):
            source.list_documents()


@pytest.mark.parametrize("status", [403, 429, 404, 500])
def test_http_errors_are_sanitized_and_token_goes_only_to_github(status):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status, text="sensitive-upstream-body")

    with PolicyRepository(
        Settings(github_token="test-secret"), transport=httpx.MockTransport(respond)
    ) as source:
        with pytest.raises(PolicySourceError) as exc:
            source.list_documents()
        assert "sensitive" not in str(exc.value) and "test-secret" not in str(exc.value)
    assert requests[0].url.host == "api.github.com"
    assert requests[0].headers["Authorization"] == "Bearer test-secret"


def test_network_timeout_is_actionable():
    def respond(request):
        raise httpx.ReadTimeout("sensitive timeout diagnostics")

    with PolicyRepository(Settings(), transport=httpx.MockTransport(respond)) as source:
        with pytest.raises(PolicySourceError, match="network access"):
            source.list_documents()


def test_blob_integrity_failure_is_not_given_to_model(corpus):
    base = corpus.respond

    def respond(request):
        if "/blobs/" in request.url.path:
            return httpx.Response(
                200, json={"encoding": "base64", "content": base64.b64encode(b"corrupted").decode()}
            )
        return base(request)

    with PolicyRepository(Settings(), transport=httpx.MockTransport(respond)) as source:
        source.list_documents()
        with pytest.raises(PolicySourceError, match="integrity"):
            source.read_document("Policies/appeals.md")
        assert not source.files


def test_long_document_returns_bounded_ranges_and_continuation(corpus):
    corpus.files["Policies/long.md"] = "\n".join(f"Line {i} " + "x" * 100 for i in range(500))
    with corpus.factory(Settings(read_max_chars=1000)) as source:
        source.list_documents()
        first = source.read_document("Policies/long.md")
        assert first["end_line"] < 200 and first["next_start_line"] == first["end_line"] + 1
        second = source.read_document("Policies/long.md", first["next_start_line"])
        assert second["start_line"] == first["end_line"] + 1
        assert len(first["numbered_content"]) <= 1000
        with pytest.raises(ValueError):
            citation_from_read(first, first["start_line"], second["end_line"])
        with pytest.raises(ValueError, match="exceeds"):
            source.read_document("Policies/long.md", 10000)


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        ("/commits/", []),
        ("/commits/", {"sha": "a" * 40, "commit": None}),
        ("/commits/", {"sha": [], "commit": {"tree": {"sha": "b" * 40}}}),
        ("/trees/", {"tree": {}}),
        ("/trees/", {"tree": [None]}),
        (
            "/trees/",
            {
                "tree": [
                    {
                        "path": "Policies/appeals.md",
                        "mode": "100644",
                        "type": "blob",
                        "sha": "c" * 40,
                        "size": None,
                    }
                ]
            },
        ),
        ("/blobs/", []),
        ("/blobs/", {"encoding": "base64", "content": []}),
    ],
)
def test_malformed_upstream_metadata_is_a_sanitized_source_error(corpus, route, payload):
    base = corpus.respond

    def respond(request):
        return httpx.Response(200, json=payload) if route in request.url.path else base(request)

    with PolicyRepository(Settings(), transport=httpx.MockTransport(respond)) as source:
        with pytest.raises(PolicySourceError):
            source.list_documents()
            source.read_document("Policies/appeals.md")
        assert not source.files
