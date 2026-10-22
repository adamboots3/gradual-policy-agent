import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api, ApiError, type Answer } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  api: {
    health: vi.fn(),
    knowledge: vi.fn(),
    conversations: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    remove: vi.fn(),
    send: vi.fn(),
  },
}));

const answer: Answer = {
  kind: "answered",
  answer: "You can submit an appeal. [1]",
  run_id: "run-1",
  corpus_commit: "abcdef123456",
  search_calls: 1,
  latency_ms: 320,
  citations: [
    {
      label: 1,
      chunk_id: "evidence",
      title: "Appeal and Reinstatement",
      heading: "How this works",
      content: "Please fill out the appeal form. <script>unsafe()</script>",
      path: "Policies/appeal.md",
      start_line: 10,
      end_line: 15,
      commit_sha: "abcdef123456",
      source_url:
        "https://github.com/github/site-policy/blob/abcdef123456/Policies/appeal.md#L10-L15",
    },
  ],
};
const conversation = {
  id: "chat-1",
  title: "Saved conversation",
  created_at: "2026-10-22T10:00:00Z",
  turn_count: 1,
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.health).mockResolvedValue({
    status: "ok",
    chat_configured: true,
    retrieval_mode: "keyword",
  });
  vi.mocked(api.knowledge).mockResolvedValue({
    commit: "abcdef123456",
    documents: 57,
    chunks: 721,
  });
  vi.mocked(api.conversations).mockResolvedValue([]);
  vi.mocked(api.create).mockResolvedValue(conversation);
  vi.mocked(api.send).mockResolvedValue(answer);
  vi.mocked(api.remove).mockResolvedValue(undefined);
});
afterEach(cleanup);

async function ready() {
  render(<App />);
  await screen.findByText("Connected");
}

describe("Policy Desk", () => {
  it("shows the library and lets a suggestion populate the composer without sending", async () => {
    await ready();
    expect(screen.getByText("57 documents")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Appeal an account suspension/ }),
    );
    expect(screen.getByLabelText("Ask a policy question")).toHaveValue(
      "How can I appeal an account suspension?",
    );
    expect(api.send).not.toHaveBeenCalled();
  });

  it("sends follow-ups in the same conversation and displays safe source excerpts", async () => {
    await ready();
    const input = screen.getByLabelText("Ask a policy question");
    await userEvent.type(input, "Can I appeal?");
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await screen.findByText("You can submit an appeal.");
    await userEvent.click(
      screen.getByRole("button", { name: "View source 1" }),
    );
    expect(
      screen.getByText(/Please fill out the appeal form/),
    ).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(
      screen.getByRole("link", { name: /Open original on GitHub/ }),
    ).toHaveAttribute("href", answer.citations[0].source_url);
    vi.mocked(api.send).mockResolvedValue({ ...answer, run_id: "run-2" });
    await userEvent.type(input, "What is the deadline?");
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await waitFor(() => expect(api.send).toHaveBeenCalledTimes(2));
    expect(api.send).toHaveBeenLastCalledWith(
      "chat-1",
      "What is the deadline?",
    );
    expect(api.create).toHaveBeenCalledTimes(1);
  });

  it("restores a conversation and deletes it after a reviewable confirmation", async () => {
    vi.mocked(api.conversations).mockResolvedValue([conversation]);
    vi.mocked(api.get).mockResolvedValue({
      ...conversation,
      turns: [{ question: "Old question", response: answer }],
    });
    await ready();
    await userEvent.click(
      screen.getByRole("button", { name: "Saved conversation" }),
    );
    await screen.findByText("Old question");
    await userEvent.click(
      screen.getByRole("button", { name: "Delete Saved conversation" }),
    );
    const dialog = screen.getByRole("dialog");
    expect(api.remove).not.toHaveBeenCalled();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Delete conversation" }),
    );
    await waitFor(() => expect(api.remove).toHaveBeenCalledWith("chat-1"));
    await waitFor(() =>
      expect(screen.queryByText("Old question")).not.toBeInTheDocument(),
    );
  });

  it("keeps a failed question editable and retries without creating another conversation", async () => {
    vi.mocked(api.send)
      .mockRejectedValueOnce(new ApiError("Provider unavailable", 502))
      .mockResolvedValueOnce(answer);
    await ready();
    await userEvent.type(
      screen.getByLabelText("Ask a policy question"),
      "Retry this question",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Ask a policy question")).toHaveValue(
      "Retry this question",
    );
    await userEvent.click(screen.getByRole("button", { name: /Edit & retry/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await screen.findByText("You can submit an appeal.");
    expect(api.create).toHaveBeenCalledTimes(1);
    expect(api.send).toHaveBeenCalledTimes(2);
  });

  it("prevents duplicate submits and conversation changes during generation", async () => {
    let resolve!: (value: Answer) => void;
    vi.mocked(api.send).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    await ready();
    await userEvent.type(
      screen.getByLabelText("Ask a policy question"),
      "Wait for this",
    );
    await userEvent.dblClick(
      screen.getByRole("button", { name: "Send question" }),
    );
    await screen.findByText("Looking through the policies…");
    expect(api.send).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: /New conversation ↗/ }),
    ).toBeDisabled();
    resolve(answer);
    await screen.findByText("You can submit an appeal.");
  });

  it("shows a recoverable offline error without fabricating library data", async () => {
    vi.mocked(api.health).mockRejectedValue(
      new ApiError("Cannot reach the server", 0),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cannot reach the server",
    );
    expect(screen.queryByText("57 documents")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
  });
});
