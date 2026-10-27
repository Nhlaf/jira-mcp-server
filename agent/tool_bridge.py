"""Convert between MCP tool formats and Groq function-calling formats."""

import json
from typing import Any


def mcp_tools_to_llm_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool schemas into Groq function tool definitions."""
    tools: list[dict[str, Any]] = []
    for tool in mcp_tools:
        schema = tool.input_schema
        if not isinstance(schema, dict):
            raise RuntimeError(f"MCP tool {tool.name!r} has an invalid input schema.")
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": schema,
                },
            }
        )
    return tools


def tool_result_to_text(result: Any) -> str:
    """Convert an MCP result into the string required by Groq tool messages."""
    if result.is_error:
        details = [
            item.text
            for item in result.content
            if getattr(item, "text", None) is not None
        ]
        raise RuntimeError("\n".join(details) or "The MCP tool call failed.")

    if result.data is not None:
        if isinstance(result.data, str):
            return result.data
        return json.dumps(result.data)
    if result.structured_content is not None:
        return json.dumps(result.structured_content)

    text_blocks = [
        item.text
        for item in result.content
        if getattr(item, "text", None) is not None
    ]
    if text_blocks:
        return "\n".join(text_blocks)
    return json.dumps(
        [item.model_dump(mode="json", by_alias=True) for item in result.content]
    )
