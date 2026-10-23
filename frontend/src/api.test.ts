import { afterEach, expect, it, vi } from "vitest";
import { api, type Turn } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("sends bounded question/answer context without stored IDs, sources or metadata", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ answer: "ok" }),
  });
  vi.stubGlobal("fetch", fetch);
  const turns = Array.from({ length: 25 }, (_, index) => ({
    question: `Question ${index}`,
    response: {
      kind: "answered",
      corpus_commit: "test",
      search_calls: 1,
      latency_ms: 1,
      answer: `Answer ${index}`,
      run_id: "not-context",
      citations: [],
    },
  })) as Turn[];
  const controller = new AbortController();
  await api.send("Follow-up", turns, controller.signal);
  const [url, request] = fetch.mock.calls[0];
  expect(url).toBe("/api/chat");
  expect(request.cache).toBe("no-store");
  expect(request.signal).toBe(controller.signal);
  const body = JSON.parse(request.body);
  expect(Object.keys(body).sort()).toEqual(["content", "history"]);
  expect(body.history).toHaveLength(20);
  expect(body.history[0]).toEqual({
    question: "Question 5",
    answer: "Answer 5",
  });
  expect(body.history[19]).toEqual({
    question: "Question 24",
    answer: "Answer 24",
  });
});

it("a new window request sends empty context", async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ answer: "ok" }),
  });
  vi.stubGlobal("fetch", fetch);
  await api.send("Hello", []);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    content: "Hello",
    history: [],
  });
});
