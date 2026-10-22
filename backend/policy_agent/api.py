from typing import Annotated

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

from policy_agent.config import Settings
from policy_agent.conversations import ConversationNotFound, ConversationService
from policy_agent.providers import ConfigurationError
from policy_agent.retrieval import corpus_status
from policy_agent.semantic import Retriever


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    limit: int = Field(default=6, ge=1, le=20)


class MessageRequest(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


def create_app(settings: Settings | None = None, service=None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="GitHub Policy Support Agent", version="0.1.0")
    service = service or ConversationService(settings)
    retriever = Retriever(settings)

    @app.exception_handler(ConfigurationError)
    def configuration_error(request: Request, exc: ConfigurationError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ConversationNotFound)
    def not_found(request: Request, exc: ConversationNotFound):
        return JSONResponse(status_code=404, content={"detail": "Conversation not found."})

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "stage": "agent-backend",
            "retrieval_mode": settings.retrieval_mode,
            "chat_configured": bool(settings.chat_provider and settings.chat_model),
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

    @app.post("/api/conversations", status_code=201)
    def create_conversation():
        return service.create()

    @app.get("/api/conversations")
    def list_conversations():
        return {"conversations": service.list()}

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(conversation_id: str):
        return service.get(conversation_id)

    @app.delete("/api/conversations/{conversation_id}", status_code=204)
    def delete_conversation(conversation_id: str):
        service.delete(conversation_id)
        return Response(status_code=204)

    @app.post("/api/conversations/{conversation_id}/messages")
    def send_message(conversation_id: str, request: MessageRequest):
        try:
            return service.chat(conversation_id, request.content)
        except (ConfigurationError, ConversationNotFound):
            raise
        except Exception as exc:
            raise HTTPException(
                502,
                "Model or retrieval request failed. Check provider configuration "
                "and retry; no partial turn was added to history.",
            ) from exc

    return app


app = create_app()
