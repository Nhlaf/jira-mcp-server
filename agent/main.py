"""Connect the custom agent loop to the Jira MCP server."""

from pathlib import Path
from typing import Any

from fastmcp import Client # type: ignore

from agent.agent_loop import run_agent
from agent.llm import LLM
from agent.tool_bridge import mcp_tools_to_llm_tools
from config import load_settings

SYSTEM_PROMPT = (
    "You are a Jira assistant. Use the available Jira tools to answer requests. "
    "Do not claim an issue was created, transitioned, or commented on unless the "
    "corresponding tool succeeded. Ask for required Jira details when they are "
    "missing. Do not invent issue data."
)
SERVER_SCRIPT = Path(__file__).resolve().parents[1] / "server" / "main.py"


def _tool_schema(tool: Any) -> dict[str, Any]:
    """Convert a FastMCP tool into a JSON-serializable catalog entry."""
    parameters = tool.input_schema
    if not isinstance(parameters, dict):
        raise RuntimeError(f"MCP tool {tool.name!r} has an invalid input schema.")
    return {
        "name": tool.name,
        "description": tool.description or "",
        "parameters": parameters,
    }


async def get_tool_catalog() -> list[dict[str, Any]]:
    """Discover and describe the tools exposed by the Jira MCP server."""
    async with Client(SERVER_SCRIPT) as mcp_client:
        return [_tool_schema(tool) for tool in await mcp_client.list_tools()]


async def run_query(query: str, session_id: str) -> str:
    """Run a chat turn and preserve history for its session ID."""
    settings = load_settings()
    llm = LLM(settings)
    try:
        async with Client(SERVER_SCRIPT) as mcp_client:
            llm_tools = mcp_tools_to_llm_tools(await mcp_client.list_tools())
            return await run_agent(
                query=query,
                llm=llm,
                mcp_client=mcp_client,
                llm_tools=llm_tools,
                system_prompt=SYSTEM_PROMPT,
                session_id=session_id,
                max_iterations=8,
            )
    finally:
        await llm.close()
