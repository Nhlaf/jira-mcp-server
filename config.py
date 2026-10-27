"""Jira and Groq settings loaded from the environment and .env file."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True)
class JiraSettings:
    """Hold the Jira Cloud URL and API-token credentials."""

    base_url: str
    email: str
    api_token: str


@dataclass(frozen=True)
class Settings:
    """Hold the settings required to run a Jira-backed Groq agent."""

    jira: JiraSettings
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"
    temperature: float = 0.0


def load_environment() -> None:
    """Load values from the project .env file into the process environment."""
    load_dotenv()


def _required_environment(name: str) -> str:
    """Return a required environment value or report its missing name."""
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} is not set. Configure it in the environment or .env.")
    return value.strip()


def load_jira_settings() -> JiraSettings:
    """Load and validate Jira Cloud credentials."""
    load_environment()
    base_url = _required_environment("JIRA_BASE_URL").rstrip("/")
    parsed_url = urlparse(base_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or parsed_url.path not in ("", "/")
        or parsed_url.query
        or parsed_url.fragment
        or parsed_url.username
        or parsed_url.password
    ):
        raise ValueError("JIRA_BASE_URL must be an HTTPS Jira Cloud site URL.")
    return JiraSettings(
        base_url=base_url,
        email=_required_environment("JIRA_EMAIL"),
        api_token=_required_environment("JIRA_API_TOKEN"),
    )


def load_settings() -> Settings:
    """Load and validate Jira and Groq configuration."""
    load_environment()
    try:
        temperature = float(os.getenv("GROQ_TEMPERATURE", "0.0"))
    except ValueError as error:
        raise ValueError("GROQ_TEMPERATURE must be a number.") from error
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("GROQ_TEMPERATURE must be between 0.0 and 2.0.")
    groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    if not groq_model:
        raise ValueError("GROQ_MODEL must not be empty.")
    return Settings(
        jira=load_jira_settings(),
        groq_api_key=_required_environment("GROQ_API_KEY"),
        groq_model=groq_model,
        temperature=temperature,
    )
