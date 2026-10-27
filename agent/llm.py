"""Send tool-calling chat completion requests to Groq."""

from typing import Any

from groq import AsyncGroq

from config import Settings


class LLM:
    """Wrap the Groq asynchronous chat-completions client."""

    def __init__(self, settings: Settings) -> None:
        """Create a Groq client using the configured credentials."""
        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._model = settings.groq_model
        self._temperature = settings.temperature

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        """Return the first assistant message from Groq."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=self._temperature,
        )
        if not response.choices:
            raise RuntimeError("Groq returned no completion choices.")
        return response.choices[0].message

    async def close(self) -> None:
        """Close the Groq HTTP client."""
        await self._client.close()
