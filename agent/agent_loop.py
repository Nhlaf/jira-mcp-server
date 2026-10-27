"""Run a Groq tool-calling loop with per-session in-memory history."""

import asyncio
import json
import logging
from typing import Any

from agent.llm import LLM
from agent.tool_bridge import tool_result_to_text

logger = logging.getLogger(__name__)
SESSION_HISTORY: dict[str, list[dict[str, Any]]] = {}
SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def _session_lock(session_id: str) -> asyncio.Lock:
    """Return the lock that serializes turns for a conversation session."""
    lock = SESSION_LOCKS.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        SESSION_LOCKS[session_id] = lock
    return lock


async def run_agent(
    query: str,
    llm: LLM,
    mcp_client: Any,
    llm_tools: list[dict[str, Any]],
    system_prompt: str,
    session_id: str,
    max_iterations: int,
) -> str:
    """Run tool calls until Groq returns an answer or the loop limit is reached."""
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    async with _session_lock(session_id):
        messages = SESSION_HISTORY.setdefault(
            session_id,
            [{"role": "system", "content": system_prompt}],
        )
        messages.append({"role": "user", "content": query})

        for _ in range(max_iterations):
            reply = await llm.chat(messages, llm_tools)
            tool_calls = reply.tool_calls or []
            assistant_message = reply.model_dump(mode="json", exclude_none=True)
            messages.append(assistant_message)

            if not tool_calls:
                if not isinstance(reply.content, str):
                    raise RuntimeError("Groq returned an assistant response without text.")
                return reply.content

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be a JSON object.")
                    result = await mcp_client.call_tool(tool_name, arguments)
                    content = tool_result_to_text(result)
                except (json.JSONDecodeError, ValueError, RuntimeError) as error:
                    logger.warning("Jira tool %s failed: %s", tool_name, error)
                    content = json.dumps({"error": str(error)})
                except Exception as error:
                    logger.exception("Unexpected error calling Jira tool %s.", tool_name)
                    content = json.dumps({"error": str(error)})

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": content,
                    }
                )

        raise RuntimeError(
            f"Agent did not produce a final answer within {max_iterations} iterations."
        )
