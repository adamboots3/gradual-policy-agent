from typing import Annotated

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError
from policy_agent.retrieval import corpus_status
from policy_agent.semantic import Retriever


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    limit: int = Field(default=6, ge=1, le=20)


class MessageRequest(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)


def create_app(settings: Settings | None = None, service=None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="GitHub Policy Support Agent", version="0.1.0")
    service = service or ChatService(settings)
    retriever = Retriever(settings)

    @app.exception_handler(ConfigurationError)
    def configuration_error(request: Request, exc: ConfigurationError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.middleware("http")
    async def no_chat_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/api/chat":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "stage": "agent-backend",
            "retrieval_mode": settings.retrieval_mode,
            "chat_configured": bool(settings.chat_provider and settings.chat_model),
            "conversation_mode": "window-memory",
        }

    @app.get("/api/knowledge")
    def knowledge():
        return corpus_status(settings.database)

    @app.post("/api/knowledge/search")
    def retrieve(request: SearchRequest):
        if not corpus_status(settings.database)["chunks"]:
            raise HTTPException(503, "Knowledge base is empty. Run sync and index first.")
        return {
            "results": retriever.search(request.query, request.limit),
            "retrieval_mode": settings.retrieval_mode,
        }

    @app.post("/api/chat")
    def send_message(request: MessageRequest):
        try:
            return service.chat(request.content, request.history)
        except ConfigurationError:
            raise
        except Exception as exc:
            raise HTTPException(
                502,
                "Model or retrieval request failed. Check provider configuration "
                "and retry; the server does not save conversations.",
            ) from exc

    return app


app = create_app()
