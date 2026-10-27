# Current Jira Service Scope

The calculator-only design below is historical and is superseded by the Jira
Cloud service requirements. The active implementation uses a custom Groq
tool-calling loop with no LangChain or LangGraph, exposes `/health`, `/tools`,
and `/chat`, and preserves in-memory chat history by `session_id`.

The Jira MCP server exposes exactly five tools: `get_issue_details`,
`search_issues`, `create_issue`, `transition_issue`, and `add_comment`. Jira
Cloud and Groq settings are loaded from environment variables or `.env`. See
[`README.md`](./README.md) for configuration, request formats, and Postman setup.

# Historical Architecture: MCP Calculator Agent

## 0. Rules for the coding agent (read first)
1. Build ONE step at a time (see section 9). Stop after each step and wait for confirmation.
2. Each module goes in its own file. Never bundle modules into one block.
3. Every function gets a one-line comment/docstring saying what it does.
4. Before writing a step, explain in 2-3 lines why it is designed that way.
5. Do not add features, files, or dependencies that are not in this document.
6. Keep code simple. No frameworks, no abstract base classes, no premature generalization.

## 1. Goal
A CLI agent that answers "What is tan(1/2) + cos(1/2)?" by letting an LLM
choose tools exposed by an MCP server, using an agent loop we write ourselves.
Expected final answer: about 1.4234.

## 2. System overview

```
                 ┌────────────────────────────────────────────┐
                 │               agent process                │
                 │                                            │
  user query ──► │  main.py ──► agent_loop.py ──► llm.py ─────┼──► Groq API
                 │                  │                         │
                 │                  ▼                         │
                 │            tool_bridge.py                  │
                 │                  │                         │
                 │                  ▼                         │
                 │          client/mcp_client.py              │
                 └──────────────────┬─────────────────────────┘
                                    │ stdio (JSON-RPC)
                 ┌──────────────────▼─────────────────────────┐
                 │        MCP server subprocess               │
                 │  server/main.py ──► calculator/operations  │
                 └────────────────────────────────────────────┘
```

Two processes: the agent (client side) and the MCP server (spawned by the
client over stdio). The LLM is a remote HTTP API.

## 3. Stack
- Python 3.11+
- `mcp` (server + client; match the version already used in server/main.py)
- `groq` (async client, OpenAI-style tool calling)
- `python-dotenv`
- Standard library only for everything else

## 4. Project layout

```
project/
├── .env
├── requirements.txt
├── config.py
├── calculator/
│   ├── __init__.py
│   └── operations.py        EXISTS: add, subtract, multiply, divide, power
├── server/
│   └── main.py              EXISTS: add tan, cos
├── client/
│   ├── __init__.py
│   └── mcp_client.py        EXISTS: review per section 5.2
└── agent/
    ├── __init__.py
    ├── llm.py
    ├── tool_bridge.py
    ├── agent_loop.py
    └── main.py
```

## 5. Module specifications

### 5.1 server/main.py (extend existing)
- Add tools `tan(x: float) -> float` and `cos(x: float) -> float` (radians).
- Use `math.tan` / `math.cos`. Same decorator pattern as the existing tools.
- Total tools after change: 7.
- Do not change existing tools.

### 5.2 client/mcp_client.py (review existing)
Interface the agent depends on (must not change):
```python
class MCPClient:
    async def connect() -> None
    async def list_tools() -> list          # MCP Tool objects
    async def call_tool(name: str, arguments: dict) -> str | list | dict
    async def close() -> None
```
Review items:
- The existing code reads `result.is_error` and `result.structured_content`
  via getattr. The MCP SDK may name these `isError` and `structuredContent`.
  With getattr defaults, a wrong name fails SILENTLY (errors never detected).
  Check the installed SDK's CallToolResult fields and use the correct names.
- Optional cleanup: manage the two async contexts with `contextlib.AsyncExitStack`
  instead of manual `__aenter__`/`__aexit__`.
- `call_tool` should return a plain string for the LLM (see 5.4), so decide
  here: either return str always, or convert in tool_bridge. Chosen: convert
  in tool_bridge, keep the client generic.

### 5.3 config.py
```python
@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    model_name: str        # default "openai/gpt-oss-120b"
    temperature: float     # default 0.0
    server_script: str     # default "server/main.py"
    max_iterations: int    # default 8

def load_settings() -> Settings
```
- Loads `.env` with python-dotenv.
- Raises `ValueError("GROQ_API_KEY is not set...")` if the key is missing.
- No other module reads `os.environ` directly.

### 5.4 agent/tool_bridge.py
Converts between MCP and LLM formats, in both directions.

```python
def mcp_tools_to_llm_tools(mcp_tools: list) -> list[dict]
def tool_result_to_text(result) -> str
```

`mcp_tools_to_llm_tools` output shape, one entry per MCP tool:
```python
{
  "type": "function",
  "function": {
    "name": tool.name,
    "description": tool.description or "",
    "parameters": tool.inputSchema,     # JSON Schema dict, pass through
  },
}
```
`tool_result_to_text`: dict/list -> `json.dumps`, str -> as is, anything
else -> `str()`. The LLM message content must always be a string.

### 5.5 agent/llm.py
```python
class LLM:
    def __init__(self, settings: Settings) -> None
    async def chat(self, messages: list[dict], tools: list[dict] | None = None)
        -> ChatMessage      # the first choice's message object
```
- Uses `groq.AsyncGroq`.
- Calls `client.chat.completions.create(model, messages, tools, tool_choice="auto",
  temperature)`. Omit `tools`/`tool_choice` when `tools` is None or empty.
- Returns the assistant message only (not the whole response).
- No retry logic in v1.
- This is the ONLY file that imports `groq`.

### 5.6 agent/agent_loop.py
```python
async def run_agent(
    query: str,
    llm: LLM,
    mcp_client: MCPClient,
    llm_tools: list[dict],
    system_prompt: str,
    max_iterations: int,
) -> str
```

Algorithm:
```
messages = [system, user]
for i in range(max_iterations):
    reply = await