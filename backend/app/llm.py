"""Optional OpenAI-compatible LLM. Disabled (mock mode) unless LLM_API_KEY is set."""
import os
import httpx


def enabled() -> bool:
    return bool(os.environ.get("LLM_API_KEY"))


def chat(system: str, user: str, timeout: float = 20) -> str | None:
    if not enabled():
        return None
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    try:
        r = httpx.post(f"{base}/chat/completions", timeout=timeout,
                       headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                       json={"model": os.environ.get("LLM_MODEL", "gpt-4o-mini"), "temperature": 0.3,
                             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # always fall back to deterministic replies
