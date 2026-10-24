import {
  act,
  cleanup,
  fireEvent,
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
  api: { health: vi.fn(), policies: vi.fn(), send: vi.fn() },
}));

const answer: Answer = {
  kind: "answered",
  answer: "You can submit an appeal. [1]",
  run_id: "run-1",
  source_commit: "abcdef123456",
  read_calls: 1,
  latency_ms: 320,
  citations: [
    {
      label: 1,
      source_id: "evidence",
      title: "Appeal and Reinstatement",
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

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.health).mockResolvedValue({
    status: "ok",
    chat_configured: true,
    source_mode: "github-online",
  });
  vi.mocked(api.policies).mockResolvedValue({
    repository: "https://github.com/github/site-policy",
    ref: "HEAD",
    source_mode: "github-online",
  });
  vi.mocked(api.send).mockResolvedValue(answer);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function ready() {
  const view = render(<App />);
  await within(view.container).findByText("Connected");
  return view;
}

async function ask(question: string, container: HTMLElement = document.body) {
  const view = within(container);
  await userEvent.type(
    view.getByRole("textbox", { name: "Ask a policy question" }),
    question,
  );
  await userEvent.click(view.getByRole("button", { name: "Send question" }));
}

describe("temporary Policy Desk", () => {
  it("opens independently numbered passages from the same source read", async () => {
    vi.mocked(api.send).mockResolvedValue({
      ...answer,
      answer: "Use the form. [1] Six months. [2]",
      citations: [
        answer.citations[0],
        {
          ...answer.citations[0],
          label: 2,
          start_line: 29,
          end_line: 29,
          content: "Appeal within six months.",
        },
      ],
    });
    await ready();
    await ask("What is the deadline?");
    await screen.findByRole("button", { name: "View source 2" });
    await userEvent.click(
      screen.getByRole("button", { name: "View source 2" }),
    );
    expect(screen.getByText("Appeal within six months.")).toBeInTheDocument();
    expect(screen.getByText("Lines 29–29")).toBeInTheDocument();
  });
  it("renders a greeting without a policy snapshot or file read", async () => {
    vi.mocked(api.send).mockResolvedValue({
      ...answer,
      kind: "greeting",
      answer: "Hello!",
      citations: [],
      source_commit: null,
      read_calls: 0,
    });
    await ready();
    await ask("Hello");
    expect(await screen.findByText("Hello!")).toBeInTheDocument();
    expect(screen.getByText(/0 file reads/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "View source 1" }),
    ).not.toBeInTheDocument();
  });
  it("shows the online source and suggestion without any history controls", async () => {
    await ready();
    expect(screen.getByText("Read from GitHub")).toBeInTheDocument();
    expect(screen.getByText("This window only")).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Conversation history" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /Appeal an account suspension/ }),
    );
    expect(screen.getByLabelText("Ask a policy question")).toHaveValue(
      "How can I appeal an account suspension?",
    );
    expect(api.send).not.toHaveBeenCalled();
  });

  it("passes only completed in-window turns to a follow-up and displays safe sources", async () => {
    await ready();
    await ask("Can I appeal?");
    await screen.findByText("You can submit an appeal.");
    expect(api.send).toHaveBeenNthCalledWith(
      1,
      "Can I appeal?",
      [],
      expect.any(AbortSignal),
    );
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
    expect(screen.getByText("Policies/appeal.md")).toBeInTheDocument();
    vi.mocked(api.send).mockResolvedValue({ ...answer, run_id: "run-2" });
    await ask("What is the deadline?");
    await waitFor(() => expect(api.send).toHaveBeenCalledTimes(2));
    expect(api.send).toHaveBeenLastCalledWith(
      "What is the deadline?",
      [{ question: "Can I appeal?", response: answer }],
      expect.any(AbortSignal),
    );
  });

  it("starts a remounted window empty and writes no browser storage", async () => {
    const save = vi.spyOn(Storage.prototype, "setItem");
    const first = await ready();
    await ask("Temporary question");
    await screen.findByText("You can submit an appeal.");
    first.unmount();
    await ready();
    expect(screen.queryByText("Temporary question")).not.toBeInTheDocument();
    await ask("A fresh window");
    await screen.findByText("You can submit an appeal.");
    expect(api.send).toHaveBeenLastCalledWith(
      "A fresh window",
      [],
      expect.any(AbortSignal),
    );
    expect(save).not.toHaveBeenCalled();
  });

  it("clears a previous source when the next reply has no citations", async () => {
    await ready();
    await ask("Can I appeal?");
    await screen.findByRole("link", { name: /Open original on GitHub/ });
    vi.mocked(api.send).mockResolvedValue({
      ...answer,
      run_id: "greeting-2",
      kind: "greeting",
      answer: "Hello!",
      citations: [],
      source_commit: null,
      read_calls: 0,
    });
    await ask("Hello");
    await screen.findByText("Hello!");
    expect(
      screen.queryByRole("link", { name: /Open original on GitHub/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Follow the evidence")).toBeInTheDocument();
  });

  it("isolates two open windows", async () => {
    const a = await ready();
    await ask("Window A secret", a.container);
    await within(a.container).findByText("You can submit an appeal.");
    const b = await ready();
    await ask("Window B question", b.container);
    await within(b.container).findByText("You can submit an appeal.");
    expect(api.send).toHaveBeenLastCalledWith(
      "Window B question",
      [],
      expect.any(AbortSignal),
    );
    expect(
      within(b.container).queryByText("Window A secret"),
    ).not.toBeInTheDocument();
  });

  it("new chat clears the current context and source selection", async () => {
    await ready();
    await ask("Clear this question");
    await screen.findByText("You can submit an appeal.");
    await userEvent.click(
      screen.getByRole("button", { name: /New conversation ↗/ }),
    );
    expect(screen.queryByText("Clear this question")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Open original on GitHub/ }),
    ).not.toBeInTheDocument();
    await ask("Start over");
    await screen.findByText("You can submit an appeal.");
    expect(api.send).toHaveBeenLastCalledWith(
      "Start over",
      [],
      expect.any(AbortSignal),
    );
  });

  it("page exit clears context and discards a late reply", async () => {
    let resolve!: (value: Answer) => void;
    vi.mocked(api.send).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    await ready();
    await ask("Pending before exit");
    const signal = vi.mocked(api.send).mock.calls[0][2]!;
    fireEvent(window, new Event("pagehide"));
    expect(signal.aborted).toBe(true);
    await act(async () => {
      resolve(answer);
    });
    expect(screen.queryByText("Pending before exit")).not.toBeInTheDocument();
    expect(
      screen.queryByText("You can submit an appeal."),
    ).not.toBeInTheDocument();
  });

  it("keeps failed questions editable and excludes them from retry context", async () => {
    vi.mocked(api.send)
      .mockRejectedValueOnce(new ApiError("Provider unavailable", 502))
      .mockResolvedValueOnce(answer);
    await ready();
    await ask("Retry this question");
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Ask a policy question")).toHaveValue(
      "Retry this question",
    );
    await userEvent.click(screen.getByRole("button", { name: /Edit & retry/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Send question" }),
    );
    await screen.findByText("You can submit an appeal.");
    expect(api.send).toHaveBeenLastCalledWith(
      "Retry this question",
      [],
      expect.any(AbortSignal),
    );
  });

  it("prevents duplicate submissions and clearing during generation", async () => {
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
    await act(async () => {
      resolve(answer);
    });
    await screen.findByText("You can submit an appeal.");
  });

  it("shows a recoverable offline error without fabricated source data", async () => {
    vi.mocked(api.health).mockRejectedValue(
      new ApiError("Cannot reach the server", 0),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cannot reach the server",
    );
    expect(screen.queryByText("Not indexed")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Send question" }),
    ).toBeDisabled();
  });
});
