# Jira MCP Agent

The service exposes a Jira Cloud MCP server through a custom Groq tool-calling
agent loop. It does not use LangChain or LangGraph. The API keeps conversation
history in process memory, keyed by `session_id`; history is lost when the API
process stops.

## Configuration

Copy `.env.example` to `.env`, then set Jira Cloud and Groq credentials:

| Variable | Purpose |
| --- | --- |
| `JIRA_BASE_URL` | Jira Cloud site URL, such as `https://example.atlassian.net` |
| `JIRA_EMAIL` | Email address for the Jira API-token account |
| `JIRA_API_TOKEN` | Jira Cloud API token |
| `GROQ_API_KEY` | Groq API key |
| `GROQ_MODEL` | Groq model; defaults to `openai/gpt-oss-120b` |
| `GROQ_TEMPERATURE` | Groq temperature from `0.0` to `2.0`; defaults to `0.0` |

## Run locally on Windows

Open PowerShell in the project directory. Create and activate a virtual
environment, copy the example configuration, and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Edit `.env` and replace the example values with your Jira Cloud and Groq
credentials. Then start the API:

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open while using the service. The HTTP server listens on
`http://127.0.0.1:8000`. FastAPI's interactive API documentation is available
at `http://127.0.0.1:8000/docs`; OpenAPI JSON is at
`http://127.0.0.1:8000/openapi.json`.

In another PowerShell window, verify the service and discover its Jira tools:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/tools
```

Send a chat request (replace `ABC-123` with an issue key in your Jira site):

```powershell
$body = @{
    query = "Look up Jira issue ABC-123 and summarize its current status."
    session_id = "my-jira-chat"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/chat `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

Reuse the same `session_id` in subsequent requests to continue that
conversation. Chat history is held in memory and is cleared when the API
process stops. Alternatively, import the Postman collection below and update
its `issueKey` variable to test the endpoints in Postman.

## HTTP endpoints

### `GET /health`

Returns `{"status":"ok"}` when the API process is responding.

### `GET /tools`

Returns the Jira MCP tool names, descriptions, and input schemas.

### `POST /chat`

Request:

```json
{
  "query": "Find open issues in project ABC",
  "session_id": "optional-client-session-id"
}
```

If `session_id` is omitted, the response provides a generated ID; send that ID
on later requests to continue the same conversation. The response shape is:

```json
{
  "answer": "The agent response",
  "session_id": "client-session-id"
}
```

The MCP server exposes exactly five tools: `get_issue_details`,
`search_issues`, `create_issue`, `transition_issue`, and `add_comment`.
`transition_issue` accepts a target status and uses Jira's available workflow
transitions to resolve it. Import
[`postman/Jira MCP Agent.postman_collection.json`](./postman/Jira%20MCP%20Agent.postman_collection.json)
to test the HTTP endpoints.
