"""Expose health, Jira tools, and session-aware chat through FastAPI."""

import logging
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from agent.main import get_tool_catalog, run_query

logger = logging.getLogger(__name__)
app = FastAPI(
    title="Jira MCP Agent API",
    description="Chat with Jira through a custom Groq agent loop and Jira MCP tools.",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    """Validate a chat request and its optional conversation session ID."""

    query: str = Field(min_length=1)
    session_id: str | None = Field(default=None, min_length=1)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        """Reject queries that contain only whitespace."""
        if not value.strip():
            raise ValueError("query must not be empty.")
        return value

    @field_validator("session_id")
    @classmethod
    def session_id_must_not_be_blank(cls, value: str | None) -> str | None:
        """Reject an explicitly supplied session ID that contains only whitespace."""
        if value is not None and not value.strip():
            raise ValueError("session_id must not be empty when provided.")
        return value


class ChatResponse(BaseModel):
    """Return the assistant answer and the conversation session ID."""

    answer: str
    session_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}


@app.get("/tools")
async def tools() -> dict[str, list[dict[str, Any]]]:
    """Return the Jira MCP tool names, descriptions, and input schemas."""
    try:
        return {"tools": await get_tool_catalog()}
    except Exception as error:
        logger.exception("Could not load the Jira MCP tool catalog.")
        raise HTTPException(
            status_code=502,
            detail="The Jira tool catalog could not be loaded.",
        ) from error


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Run one chat turn and preserve history for the provided session ID."""
    session_id = request.session_id or str(uuid.uuid4())
    try:
        answer = await run_query(request.query, session_id)
    except Exception as error:
        logger.exception("Jira agent request failed.")
        raise HTTPException(
            status_code=502,
            detail="The agent could not complete the request.",
        ) from error
    return ChatResponse(answer=answer, session_id=session_id)


def main() -> None:
    """Run the local FastAPI server on 127.0.0.1:8000."""
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
