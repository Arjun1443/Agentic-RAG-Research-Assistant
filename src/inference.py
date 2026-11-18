"""Server-side chat routing for the research agents."""
import os
from urllib.parse import urlsplit

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


class InferenceConfigurationError(ValueError):
    pass


def get_groq_client():
    return OpenAI(api_key=_groq_key(), base_url="https://api.groq.com/openai/v1")


def _groq_key():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise InferenceConfigurationError("Configure GROQ_API_KEY before running research.")
    return key


def research_backend(role):
    default = os.getenv("RAG_BACKEND", "groq").strip().lower()
    backend = (os.getenv("RAG_CRITIC_BACKEND") or default) if role == "critic" else default
    backend = backend.strip().lower()
    if backend == "groq":
        return backend, os.getenv("GROQ_MODEL", GROQ_MODEL), _groq_key(), "https://api.groq.com/openai/v1"
    if backend not in {"vllm", "sglang"}:
        raise InferenceConfigurationError("Research backend must be groq, vllm, or sglang.")
    prefix = backend.upper()
    url, model, key = (os.getenv(f"{prefix}_{name}", "").strip()
                       for name in ("BASE_URL", "MODEL", "API_KEY"))
    if not url or not model:
        raise InferenceConfigurationError(f"Configure {prefix}_BASE_URL and {prefix}_MODEL.")
    parsed = urlsplit(url)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.rstrip("/").endswith("/v1")
            or parsed.scheme not in ({"http", "https"} if local and not os.getenv("VERCEL") else {"https"})):
        raise InferenceConfigurationError(f"{prefix}_BASE_URL must be an OpenAI-compatible /v1 URL.")
    if (not local or os.getenv("VERCEL")) and not key:
        raise InferenceConfigurationError(f"Configure {prefix}_API_KEY for the hosted endpoint.")
    return backend, model, key or "local", url.rstrip("/")


def complete_research(role, messages, max_tokens):
    _, model, key, url = research_backend(role)
    with OpenAI(api_key=key, base_url=url, timeout=25.0, max_retries=0) as client:
        response = client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=0.1
        )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("The research model returned an empty response.")
    return content
