export interface Citation {
  label: number;
  source_id: string;
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
  source_commit: string | null;
  read_calls: number;
  latency_ms: number;
}
export interface Turn {
  question: string;
  response: Answer;
}
export interface PolicySource {
  repository: string;
  ref: string;
  source_mode: string;
}
export interface Health {
  status: string;
  chat_configured: boolean;
  source_mode: string;
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
  policies: () => request<PolicySource>("/policies"),
  send: (content: string, turns: Turn[], signal?: AbortSignal) =>
    request<Answer>("/chat", {
      ...json("POST", {
        content,
        history: turns.slice(-20).map((turn) => ({
          question: turn.question,
          answer: turn.response.answer,
        })),
      }),
      signal,
      cache: "no-store",
    }),
};
