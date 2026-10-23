import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowUp,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  ExternalLink,
  FileText,
  GitBranch,
  Github,
  LoaderCircle,
  MessageSquare,
  Plus,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  api,
  type Answer,
  type Citation,
  type Health,
  type Knowledge,
  type Turn,
} from "./api";

const suggestions = [
  {
    title: "Appeal an account suspension",
    question: "How can I appeal an account suspension?",
    tag: "Account access",
  },
  {
    title: "Understand content ownership",
    question: "Who owns the content I upload to GitHub?",
    tag: "Terms of service",
  },
  {
    title: "Report a copyright concern",
    question: "How do I submit a DMCA takedown notice?",
    tag: "Content policies",
  },
];
const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please retry.";

function CitationText({
  answer,
  onSelect,
}: {
  answer: Answer;
  onSelect: (c: Citation) => void;
}) {
  return (
    <div className="answer-text">
      {answer.answer.split(/(\[\d+\])/g).map((part, index) => {
        const match = /^\[(\d+)\]$/.exec(part);
        const source =
          match && answer.citations.find((c) => c.label === Number(match[1]));
        return source ? (
          <button
            className="inline-citation"
            key={index}
            aria-label={`View source ${source.label}`}
            onClick={() => onSelect(source)}
          >
            {source.label}
          </button>
        ) : (
          <span key={index}>{part}</span>
        );
      })}
    </div>
  );
}

function Sources({
  source,
  onClose,
}: {
  source: Citation | null;
  onClose: () => void;
}) {
  return (
    <aside
      className={`sources ${source ? "sources-open" : ""}`}
      aria-label="Source details"
    >
      <div className="source-heading">
        <span>
          <BookOpen size={16} /> Source details
        </span>
        {source && (
          <button
            className="icon-button"
            aria-label="Close source details"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        )}
      </div>
      {source ? (
        <div className="source-body">
          <span className="eyebrow">CITED POLICY · {source.label}</span>
          <h2>{source.title}</h2>
          <p className="source-section">
            {source.heading || "Policy document"}
          </p>
          <div className="source-position">
            <FileText size={13} /> Lines {source.start_line}–{source.end_line}
          </div>
          <pre className="source-excerpt">{source.content}</pre>
          <a
            className="source-link"
            href={source.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Open original on GitHub <ArrowUpRight size={15} />
          </a>
          <div className="source-version">
            <GitBranch size={13} /> Snapshot {source.commit_sha.slice(0, 8)}
          </div>
        </div>
      ) : (
        <div className="source-empty">
          <div className="soft-icon">
            <FileText size={25} />
          </div>
          <h3>Follow the evidence</h3>
          <p>
            Sources appear alongside each policy answer. Select a citation to
            read the exact passage.
          </p>
          <div className="source-hint">
            <Check size={14} /> Original policy text
            <br />
            <Check size={14} /> Links to a fixed snapshot
            <br />
            <Check size={14} /> Exact document location
          </div>
        </div>
      )}
      <div className="source-footer">
        <ShieldCheck size={15} /> Based on published GitHub policies
      </div>
    </aside>
  );
}

export default function App() {
  const questionId = useId();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [knowledge, setKnowledge] = useState<Knowledge | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState("");
  const [busy, setBusy] = useState("");
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState("");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [source, setSource] = useState<Citation | null>(null);
  const working = useRef(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const scrollEnd = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    setBooting(true);
    Promise.all([api.health(), api.knowledge()])
      .then(([h, k]) => {
        if (!cancelled) {
          setHealth(h);
          setKnowledge(k);
          setBootError("");
        }
      })
      .catch((e) => {
        if (!cancelled) setBootError(message(e));
      })
      .finally(() => {
        if (!cancelled) setBooting(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  useEffect(() => {
    if (turns.length || pending)
      scrollEnd.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turns, pending]);

  function clearWindow() {
    generation.current += 1;
    controller.current?.abort();
    controller.current = null;
    working.current = false;
    setBusy("");
    setPending("");
    setTurns([]);
    setDraft("");
    setSource(null);
    setError("");
  }

  useEffect(() => {
    window.addEventListener("pagehide", clearWindow);
    return () => {
      window.removeEventListener("pagehide", clearWindow);
      generation.current += 1;
      controller.current?.abort();
    };
  }, []);

  function newConversation() {
    if (working.current) return;
    clearWindow();
    input.current?.focus();
  }

  async function send() {
    const question = draft.trim();
    if (
      !question ||
      question.length > 4000 ||
      working.current ||
      booting ||
      bootError
    )
      return;
    working.current = true;
    setBusy("send");
    setPending(question);
    setDraft("");
    setError("");
    const requestGeneration = generation.current;
    const requestController = new AbortController();
    controller.current = requestController;
    try {
      const answer = await api.send(question, turns, requestController.signal);
      if (generation.current !== requestGeneration) return;
      setTurns((previous) => [...previous, { question, response: answer }]);
      if (answer.citations.length) setSource(answer.citations[0]);
    } catch (e) {
      if (generation.current !== requestGeneration) return;
      setDraft(question);
      setError(message(e));
    } finally {
      if (generation.current === requestGeneration) {
        setPending("");
        working.current = false;
        controller.current = null;
        setBusy("");
        input.current?.focus();
      }
    }
  }

  const disabled = Boolean(busy) || booting || Boolean(bootError);
  const setupIssue =
    !booting &&
    !bootError &&
    (knowledge?.chunks === 0
      ? "The policy library is empty. Run the corpus setup in README, then refresh."
      : health && !health.chat_configured
        ? "Chat is not configured yet. Complete the model setup in README, restart the backend, then refresh."
        : "");

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Policy workspace">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            newConversation();
          }}
        >
          <span className="brand-mark">
            <BookOpen size={21} />
          </span>
          Policy Desk
          <span className="brand-dot" />
        </a>
        <p className="workspace-label">GITHUB POLICY SUPPORT</p>
        <button
          className="new-chat"
          disabled={disabled}
          onClick={newConversation}
        >
          <Plus size={17} /> New conversation <span>↗</span>
        </button>
        <div className="session-info">
          <MessageSquare size={18} />
          <strong>This window only</strong>
          <p>
            Follow up in this chat. Closing or refreshing the window clears the
            conversation.
          </p>
          <p>Chat history is not saved by this app.</p>
        </div>
        <div className="library-card">
          <div className="library-label">
            <span
              className={`status-dot ${knowledge?.chunks ? "" : "muted"}`}
            />{" "}
            Policy library
          </div>
          <strong>{knowledge?.documents ?? "—"} documents</strong>
          <p>GitHub’s published site policies</p>
          <div className="snapshot">
            <GitBranch size={13} />
            {knowledge?.commit?.slice(0, 8) || "Not indexed"}
            <span>SNAPSHOT</span>
          </div>
        </div>
        <a
          className="repository-link"
          href="https://github.com/github/site-policy"
          target="_blank"
          rel="noreferrer"
        >
          <Github size={16} /> Explore the policy repository{" "}
          <ExternalLink size={12} />
        </a>
        <div className="sidebar-footer">
          <span className="avatar">PD</span>
          <div>
            Policy support workspace<small>Grounded in the source</small>
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <ChevronRight size={13} />
            <strong>GitHub policy support</strong>
          </div>
          <span className={`connection-pill ${bootError ? "offline" : ""}`}>
            <span className="status-dot" />
            {booting ? "Connecting" : bootError ? "Offline" : "Connected"}
          </span>
        </header>
        <div className="mobile-session">
          <span>This window only · history is not saved</span>
          <button
            aria-label="New mobile conversation"
            disabled={disabled}
            onClick={newConversation}
          >
            <Plus size={16} /> New chat
          </button>
        </div>
        <section className="chat-region" aria-label="Chat">
          {(bootError || setupIssue) && (
            <div
              className={`notice ${bootError ? "notice-error" : ""}`}
              role={bootError ? "alert" : "status"}
            >
              <CircleHelp size={17} />
              <span>{bootError || setupIssue}</span>
              <button
                disabled={Boolean(busy)}
                onClick={() => setReload((n) => n + 1)}
              >
                Refresh
              </button>
            </div>
          )}
          <div className="chat-scroll">
            {turns.length === 0 && !pending && (
              <div className="welcome">
                <span className="welcome-badge">
                  <ShieldCheck size={14} /> POLICY QUESTIONS, WITH PROOF
                </span>
                <h1>
                  A clear answer.
                  <br />
                  <span>A source behind it.</span>
                </h1>
                <p>
                  Make sense of GitHub’s policies. Ask a question, follow up,
                  <br className="desktop-break" /> and see the original text
                  behind every policy answer.
                </p>
                <div className="suggestions">
                  {suggestions.map((s) => (
                    <button
                      key={s.tag}
                      disabled={disabled}
                      onClick={() => {
                        setDraft(s.question);
                        input.current?.focus();
                      }}
                    >
                      <span className="suggestion-tag">{s.tag}</span>
                      <strong>{s.title}</strong>
                      <ArrowUpRight size={16} />
                    </button>
                  ))}
                </div>
                <div className="welcome-foot">
                  <BookOpen size={15} /> Ask about account access, acceptable
                  use, privacy, and more.
                </div>
              </div>
            )}
            <div
              className="messages"
              aria-live="polite"
              aria-busy={busy === "send"}
            >
              {turns.map((turn, i) => (
                <div className="turn" key={turn.response.run_id || i}>
                  <div className="user-message">
                    <span className="message-kicker">YOU</span>
                    <p>{turn.question}</p>
                  </div>
                  <article className="assistant-message">
                    <div className="assistant-title">
                      <span className="assistant-icon">
                        <BookOpen size={16} />
                      </span>
                      <strong>Policy Desk</strong>
                      <span>
                        {turn.response.kind === "answered"
                          ? "Source-backed answer"
                          : "Response"}
                      </span>
                    </div>
                    <CitationText answer={turn.response} onSelect={setSource} />
                    {turn.response.citations.length > 0 && (
                      <div className="citation-list">
                        {turn.response.citations.map((c) => (
                          <button key={c.chunk_id} onClick={() => setSource(c)}>
                            <span>{c.label}</span>
                            {c.title}
                            <ArrowUpRight size={12} />
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="answer-meta">
                      {turn.response.search_calls}{" "}
                      {turn.response.search_calls === 1 ? "search" : "searches"}
                      <span>·</span>
                      {(turn.response.latency_ms / 1000).toFixed(1)}s
                      <span>·</span>Snapshot{" "}
                      {turn.response.corpus_commit.slice(0, 8)}
                    </div>
                  </article>
                </div>
              ))}
              {pending && (
                <div className="turn">
                  <div className="user-message">
                    <span className="message-kicker">YOU</span>
                    <p>{pending}</p>
                  </div>
                  <div className="thinking" role="status">
                    <LoaderCircle className="spin" size={17} /> Looking through
                    the policies…
                  </div>
                </div>
              )}
              <div ref={scrollEnd} />
            </div>
          </div>
          <div className="composer-area">
            {error && (
              <div className="error-message" role="alert">
                <span>{error}</span>
                <button
                  onClick={() => {
                    setError("");
                    input.current?.focus();
                  }}
                >
                  <RotateCcw size={13} /> Edit & retry
                </button>
              </div>
            )}
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <label className="sr-only" htmlFor={questionId}>
                Ask a policy question
              </label>
              <textarea
                id={questionId}
                ref={input}
                placeholder="Ask a question about GitHub policies…"
                value={draft}
                maxLength={4000}
                rows={2}
                disabled={disabled}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    void send();
                  }
                }}
              />
              <div className="composer-bottom">
                <span>
                  <BookOpen size={13} /> GitHub policy library
                </span>
                <span className="composer-shortcut">
                  {draft.length > 3500
                    ? `${draft.length}/4000`
                    : "Enter to send"}
                </span>
                <button
                  className="send-button"
                  type="submit"
                  aria-label="Send question"
                  disabled={disabled || !draft.trim()}
                >
                  {busy === "send" ? (
                    <LoaderCircle className="spin" size={17} />
                  ) : (
                    <ArrowUp size={19} />
                  )}
                </button>
              </div>
            </form>
            <p className="composer-note">
              This chat is temporary. Closing or refreshing clears it. Check
              cited sources for policy context.
            </p>
          </div>
        </section>
      </main>
      <Sources source={source} onClose={() => setSource(null)} />
    </div>
  );
}
