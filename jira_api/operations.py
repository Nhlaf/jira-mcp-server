"""Implement Jira Cloud issue operations using the REST API."""

import base64
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from config import load_jira_settings

ISSUE_FIELDS = (
    "summary,status,issuetype,assignee,reporter,priority,created,updated,description"
)
SEARCH_FIELDS = "summary,status,issuetype,assignee,priority"


def _jira_request(
    method: str,
    path: str,
    query: dict[str, str | int] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send an authenticated request to the Jira Cloud REST API."""
    settings = load_jira_settings()
    url = f"{settings.base_url}/rest/api/3{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    credentials = base64.b64encode(
        f"{settings.email}:{settings.api_token}".encode("utf-8")
    ).decode("ascii")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {credentials}",
    }
    request_body = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        request_body = json.dumps(body).encode("utf-8")
    request = Request(url, data=request_body, headers=headers, method=method)

    try:
        with urlopen(request, timeout=30) as response:
            response_body = response.read()
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Jira API request failed with HTTP {error.code}: {error_body}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to Jira: {error.reason}") from error

    if not response_body:
        return {}
    try:
        result = json.loads(response_body)
    except json.JSONDecodeError as error:
        raise RuntimeError("Jira returned a response that was not valid JSON.") from error
    if not isinstance(result, dict):
        raise RuntimeError("Jira returned a JSON response that was not an object.")
    return result


def _adf_text(text: str) -> dict[str, Any]:
    """Convert plain text to the Atlassian Document Format used by Jira."""
    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def get_issue_details(issue_key: str) -> dict[str, Any]:
    """Return the issue matching a Jira issue key."""
    if not issue_key.strip():
        raise ValueError("issue_key must not be empty.")
    return _jira_request(
        "GET",
        f"/issue/{quote(issue_key, safe='')}",
        query={"fields": ISSUE_FIELDS},
    )


def search_issues(jql: str, max_results: int = 10) -> dict[str, Any]:
    """Search Jira issues using JQL."""
    if not jql.strip():
        raise ValueError("jql must not be empty.")
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100.")
    return _jira_request(
        "POST",
        "/search/jql",
        body={
            "jql": jql,
            "maxResults": max_results,
            "fields": SEARCH_FIELDS.split(","),
        },
    )


def create_issue(
    project_key: str,
    summary: str,
    issue_type: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a Jira issue using the supplied project and issue details."""
    if not project_key.strip() or not summary.strip() or not issue_type.strip():
        raise ValueError("project_key, summary, and issue_type must not be empty.")
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if description:
        fields["description"] = _adf_text(description)
    return _jira_request("POST", "/issue", body={"fields": fields})


def _get_transitions(issue_key: str) -> list[dict[str, Any]]:
    """Return the workflow transitions Jira currently allows for an issue."""
    if not issue_key.strip():
        raise ValueError("issue_key must not be empty.")
    result = _jira_request(
        "GET",
        f"/issue/{quote(issue_key, safe='')}/transitions",
    )
    transitions = result.get("transitions")
    if not isinstance(transitions, list):
        raise RuntimeError("Jira returned an invalid transitions response.")
    return transitions


def transition_issue(issue_key: str, status: str) -> dict[str, Any]:
    """Move an issue to a status using its unique matching workflow transition."""
    if not issue_key.strip() or not status.strip():
        raise ValueError("issue_key and status must not be empty.")

    transitions = _get_transitions(issue_key)
    matching_transitions = [
        transition
        for transition in transitions
        if status.casefold()
        in {
            str(transition.get("name", "")).casefold(),
            str((transition.get("to") or {}).get("name", "")).casefold(),
        }
    ]
    if not matching_transitions:
        available_statuses = sorted(
            {
                str((transition.get("to") or {}).get("name", ""))
                for transition in transitions
                if (transition.get("to") or {}).get("name")
            }
        )
        available = ", ".join(available_statuses) or "none"
        raise ValueError(
            f"No available transition matches status {status!r}. "
            f"Available target statuses: {available}."
        )
    if len(matching_transitions) > 1:
        choices = ", ".join(
            f"{transition.get('name', 'unnamed')} (ID {transition.get('id', 'unknown')})"
            for transition in matching_transitions
        )
        raise ValueError(
            f"More than one transition matches status {status!r}: {choices}."
        )

    transition_id = matching_transitions[0].get("id")
    if transition_id is None:
        raise RuntimeError("Jira returned a transition without an ID.")
    _jira_request(
        "POST",
        f"/issue/{quote(issue_key, safe='')}/transitions",
        body={"transition": {"id": str(transition_id)}},
    )
    return {"issue_key": issue_key, "status": status}


def add_comment(issue_key: str, comment: str) -> dict[str, Any]:
    """Add a plain-text comment to a Jira issue."""
    if not issue_key.strip() or not comment.strip():
        raise ValueError("issue_key and comment must not be empty.")
    return _jira_request(
        "POST",
        f"/issue/{quote(issue_key, safe='')}/comment",
        body={"body": _adf_text(comment)},
    )
