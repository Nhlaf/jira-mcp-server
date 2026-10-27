"""Expose Jira Cloud operations as tools over the MCP stdio transport."""

import asyncio
import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jira_api import operations

mcp = FastMCP("jira")


@mcp.tool()
async def get_issue_details(issue_key: str) -> dict:
    """Look up a Jira issue by its key."""
    return await asyncio.to_thread(operations.get_issue_details, issue_key)


@mcp.tool()
async def search_issues(jql: str, max_results: int = 10) -> dict:
    """Search Jira issues with a JQL query and a result limit."""
    return await asyncio.to_thread(operations.search_issues, jql, max_results)


@mcp.tool()
async def create_issue(
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None = None,
) -> dict:
    """Create a Jira issue in a project."""
    return await asyncio.to_thread(
        operations.create_issue,
        project_key,
        summary,
        issue_type,
        description,
    )


@mcp.tool()
async def transition_issue(issue_key: str, status: str) -> dict:
    """Move a Jira issue to a target status using an available workflow transition."""
    return await asyncio.to_thread(
        operations.transition_issue,
        issue_key,
        status,
    )


@mcp.tool()
async def add_comment(issue_key: str, comment: str) -> dict:
    """Add a comment to a Jira issue."""
    return await asyncio.to_thread(operations.add_comment, issue_key, comment)


if __name__ == "__main__":
    mcp.run(transport="stdio")
