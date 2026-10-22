export interface Citation {
  label: number;
  chunk_id: string;
  title: string;
  heading: string;
  content: string;
  path: string;
  start_line: number;
  end_line: number;
  commit_sha: string;
  source_url: string;
}
export interface Answer {
  kind: string;
  answer: string;
  citations: Citation[];
  run_id: string;
  corpus_commit: string;
  search_calls: number;
  latency_ms: number;
}
export interface Turn {
  question: string;
  response: Answer;
}
export interface Conversation {
  id: string;
  created_at: string;
  title?: string;
  turn_count?: number;
}
export interface Detail extends Conversation {
  turns: Turn[];
}
export interface Knowledge {
  commit: string | null;
  documents: number;
  chunks: number;
}
export interface Health {
  status: string;
  chat_configured: boolean;
  retrieval_mode: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(
      "Cannot reach the server. Check that the backend is running, then retry.",
      0,
    );
  }
  if (!response.ok) {
    let body: { detail?: unknown } = {};
    try {
      body = await response.json();
    } catch {
      /* An upstream proxy may return HTML. */
    }
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}). Please retry.`;
    throw new ApiError(detail, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const api = {
  health: () => request<Health>("/health"),
  knowledge: () => request<Knowledge>("/knowledge"),
  conversations: async () =>
    (await request<{ conversations: Conversation[] }>("/conversations"))
      .conversations,
  create: () => request<Conversation>("/conversations", json("POST")),
  get: (id: string) =>
    request<Detail>(`/conversations/${encodeURIComponent(id)}`),
  remove: (id: string) =>
    request<void>(`/conversations/${encodeURIComponent(id)}`, json("DELETE")),
  send: (id: string, content: string) =>
    request<Answer>(
      `/conversations/${encodeURIComponent(id)}/messages`,
      json("POST", { content }),
    ),
};
