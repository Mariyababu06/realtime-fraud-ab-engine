"""Structured logging with defence-in-depth redaction and audit events."""
import json
import logging
import os
import re
import stat
from logging.handlers import RotatingFileHandler
from pathlib import Path

ACCOUNT_RE = re.compile(r"\b[CM]\d{6,}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
SECRET_RE = re.compile(r"(?i)\b(password|passwd|token|secret|salt|api[_-]?key)\b(\s*[:=]\s*)([^\s,;]+)")
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_configured = False


def redact(value):
    """Recursively redact strings in messages, exception traces and structured fields."""
    if isinstance(value, dict):
        return {str(k): redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    value = ACCOUNT_RE.sub("[REDACTED_ID]", value)
    value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    value = PHONE_RE.sub("[REDACTED_PHONE]", value)
    value = CARD_RE.sub("[REDACTED_CARD]", value)
    value = SECRET_RE.sub(r"\1\2[REDACTED_SECRET]", value)
    return value.replace("\r", r"\r").replace("\n", r"\n")


class RedactPIIFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg, record.args = redact(message), ()
        if record.exc_info:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        for key, value in list(record.__dict__.items()):
            if key not in {"msg", "args", "exc_info", "exc_text"} and not key.startswith("_"):
                if isinstance(value, (str, dict, list, tuple)):
                    setattr(record, key, redact(value))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
                   "level": record.levelname, "logger": record.name, "msg": redact(record.getMessage())}
        ctx = getattr(record, "ctx", None)
        if ctx:
            payload["ctx"] = redact(ctx)
        if record.exc_text:
            payload["exc"] = redact(record.exc_text)
        elif record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def _secure_file_handler(path):
    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        handler.close()
        raise
    return handler


def setup_logging(level=None):
    global _configured
    if _configured:
        return
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    formatter = JsonFormatter() if os.getenv("LOG_FORMAT", "json") == "json" else logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    handlers = [logging.StreamHandler()]
    try:
        LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(LOG_DIR, 0o700)
        handlers.append(_secure_file_handler(LOG_DIR / "pipeline.log"))
    except OSError:
        pass
    root = logging.getLogger()
    root.setLevel(level)
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(RedactPIIFilter())
        root.addHandler(handler)
    _configured = True


def get_logger(name):
    setup_logging()
    return logging.getLogger(name)


def audit(action, *, actor="system", outcome="success", context=None):
    """Emit a distinct structured audit event; callers must never pass raw account identifiers."""
    logger = logging.getLogger("audit")
    setup_logging()
    logger.info("audit_event", extra={"ctx": {"action": action, "actor": actor,
                                               "outcome": outcome, "context": context or {}}})
