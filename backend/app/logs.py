"""Structured logging. JSON lines by default (LOG_FORMAT=json), human text with LOG_FORMAT=text.

Usage: from .logs import log_event; log_event("webhook_received", messages=2)
Never pass tokens or secrets as fields.
"""
import json, logging, os, sys, time

_LOGGER = logging.getLogger("cyberfield")
_RESERVED = set(vars(logging.makeLogRecord({})))


class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(r.created)) + "Z", "level": r.levelname.lower(),
             "event": r.getMessage()}
        d.update({k: v for k, v in vars(r).items() if k not in _RESERVED and not k.startswith("_")})
        if r.exc_info:
            d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        extra = " ".join(f"{k}={v}" for k, v in vars(r).items() if k not in _RESERVED and not k.startswith("_"))
        return f"{time.strftime('%H:%M:%S')} {r.levelname:<7} {r.getMessage()} {extra}".rstrip()


def setup():
    if getattr(_LOGGER, "_cf_ready", False):
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(TextFormatter() if (os.environ.get("LOG_FORMAT") or "json").lower() == "text" else JsonFormatter())
    _LOGGER.handlers[:] = [h]
    _LOGGER.setLevel((os.environ.get("LOG_LEVEL") or "INFO").upper())
    _LOGGER.propagate = False
    _LOGGER._cf_ready = True


def mask_phone(p: str | None) -> str:
    p = str(p or "")
    return ("…" + p[-4:]) if len(p) > 4 else p


def log_event(event: str, level: str = "info", **fields):
    setup()
    exc = fields.pop("exc_info", False)
    _LOGGER.log(getattr(logging, level.upper(), logging.INFO), event, exc_info=exc, extra=fields)
