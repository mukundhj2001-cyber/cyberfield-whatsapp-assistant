"""Optional OpenAI-compatible AI services. Everything returns None when not configured (demo/mock mode).

- Chat (grounded FAQ fallback):   LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
- Vision (photos):                LLM_VISION_MODEL (defaults to LLM_MODEL; must be a vision-capable model)
- Speech-to-text (voice notes):   STT_API_KEY, STT_BASE_URL, STT_MODEL (fall back to the LLM_* key/base URL)
  e.g. OpenAI whisper-1, or Groq: STT_BASE_URL=https://api.groq.com/openai/v1 STT_MODEL=whisper-large-v3
"""
import base64, json, os, re
import httpx
from .logs import log_event

UNKNOWN = "UNKNOWN"
WHISPER_LANG = {"english": "en", "hindi": "hi", "tamil": "ta", "en": "en", "hi": "hi", "ta": "ta"}


def enabled() -> bool:
    return bool(os.environ.get("LLM_API_KEY"))


def stt_enabled() -> bool:
    return bool(os.environ.get("STT_API_KEY") or os.environ.get("LLM_API_KEY"))


def _base(prefix="LLM") -> str:
    return (os.environ.get(f"{prefix}_BASE_URL") or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


def _complete(messages, model: str, timeout: float, temperature=0.2) -> str | None:
    try:
        r = httpx.post(f"{_base()}/chat/completions", timeout=timeout,
                       headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
                       json={"model": model, "temperature": temperature, "messages": messages})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log_event("llm_error", "warning", error=type(e).__name__)
        return None  # always fall back to deterministic replies


def chat(system: str, user: str, timeout: float = 20) -> str | None:
    if not enabled():
        return None
    return _complete([{"role": "system", "content": system}, {"role": "user", "content": user}],
                     (os.environ.get("LLM_MODEL") or "gpt-4o-mini"), timeout)


LANG_NAME = {"en": "English", "hi": "Hindi", "ta": "Tamil"}


def grounded_prompt(business: str, facts: str, lang: str) -> str:
    return (f"You are the WhatsApp assistant for {business}. Answer the customer's question using ONLY the FACTS below. "
            f"Do not use outside knowledge, do not guess prices, times, policies or availability, and do not invent anything. "
            f"If the FACTS do not clearly contain the answer, reply with exactly {UNKNOWN} and nothing else. "
            f"Keep answers to 1-3 short sentences, friendly, in {LANG_NAME.get(lang, 'English')}.\n\nFACTS:\n{facts}")


def grounded_answer(business: str, facts: str, question: str, lang: str) -> str | None:
    """Returns an answer, UNKNOWN (model refused), or None (LLM off/failed)."""
    out = chat(grounded_prompt(business, facts, lang), question)
    if out is None:
        return None
    return UNKNOWN if UNKNOWN in out.upper()[:40] else out


def vision(prompt: str, image: bytes, mime: str, timeout: float = 45) -> str | None:
    if not enabled():
        return None
    url = f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image).decode()}"
    return _complete([{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]}],
                     os.environ.get("LLM_VISION_MODEL") or (os.environ.get("LLM_MODEL") or "gpt-4o-mini"), timeout, 0)


def parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group()) if m else None
    except ValueError:
        return None


def transcribe(audio: bytes, mime: str = "audio/ogg", timeout: float = 60) -> dict | None:
    """Returns {'text': ..., 'lang': 'en'|'hi'|'ta'|None} or None if STT is off/failed."""
    if not stt_enabled():
        return None
    key = os.environ.get("STT_API_KEY") or os.environ["LLM_API_KEY"]
    ext = {"audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/amr": "amr", "audio/aac": "aac"}.get((mime or "").split(";")[0], "ogg")
    try:
        r = httpx.post(f"{_base('STT')}/audio/transcriptions", timeout=timeout, headers={"Authorization": f"Bearer {key}"},
                       data={"model": (os.environ.get("STT_MODEL") or "whisper-1"), "response_format": "verbose_json"},
                       files={"file": (f"voice.{ext}", audio, mime or "audio/ogg")})
        r.raise_for_status()
        d = r.json()
        return {"text": (d.get("text") or "").strip(), "lang": WHISPER_LANG.get(str(d.get("language", "")).lower())}
    except Exception as e:
        log_event("stt_error", "warning", error=type(e).__name__)
        return None
