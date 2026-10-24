from typing import Annotated

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.context import ContextWindowError
from policy_agent.github_source import REPOSITORY_URL, PolicySourceError
from policy_agent.providers import ConfigurationError


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)


def create_app(settings: Settings | None = None, service=None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="GitHub Policy Support Agent", version="0.1.0")
    service = service or ChatService(settings)

    @app.exception_handler(ConfigurationError)
    def configuration_error(request: Request, exc: ConfigurationError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.middleware("http")
    async def no_chat_cache(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/api/chat":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ContextWindowError)
    def context_error(request: Request, exc: ContextWindowError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "source_mode": "github-online",
            "chat_configured": bool(settings.chat_provider and settings.chat_model),
            "conversation_mode": "window-memory",
        }

    @app.exception_handler(PolicySourceError)
    def source_error(request: Request, exc: PolicySourceError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/api/policies")
    def policies():
        # Configuration only: page startup never spends GitHub API quota.
        return {
            "repository": REPOSITORY_URL,
            "ref": settings.github_ref,
            "source_mode": "github-online",
        }

    @app.post("/api/chat")
    def send_message(request: MessageRequest):
        try:
            return service.chat(request.content, request.history)
        except (ConfigurationError, ContextWindowError, PolicySourceError):
            raise
        except Exception as exc:
            raise HTTPException(
                502,
                "Model or policy-reading request failed. Check provider configuration "
                "and retry; the server does not save conversations.",
            ) from exc

    return app


app = create_app()
