"""
LLM Router — Groq-first with Ollama offline fallback.

Priority:
  1. Groq (llama-3.3-70b-versatile) — fast cloud inference, needs internet
  2. Ollama (local model)            — fully offline fallback

Groq failures (rate-limit 429, quota exhausted, connection error) automatically
switch ALL subsequent calls to Ollama. After 30 minutes the router retries Groq
once; if it succeeds the switch reverts automatically.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────
# Guarded by _state_lock — LangGraph nodes run in worker threads, so concurrent
# scans can hit the router simultaneously.

_state_lock = threading.Lock()
_groq_llm   = None
_ollama_llm = None
_active_backend:  str        = "groq"
_groq_failed_at:  float|None = None
_GROQ_RETRY_SECS: int        = 1800   # retry Groq after 30 min

# ── LLM constructors ─────────────────────────────────────────────────────────

def _build_groq():
    global _groq_llm
    with _state_lock:
        if _groq_llm is None:
            from langchain_groq import ChatGroq
            _groq_llm = ChatGroq(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                temperature=0,
            )
        return _groq_llm


def _build_ollama():
    global _ollama_llm
    with _state_lock:
        if _ollama_llm is None:
            from langchain_ollama import ChatOllama
            model    = os.getenv("OLLAMA_MODEL", "llama3.2")
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            logger.info("Connecting to Ollama at %s model=%s", base_url, model)
            _ollama_llm = ChatOllama(model=model, base_url=base_url, temperature=0)
        return _ollama_llm

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_groq_error(exc: Exception) -> bool:
    """Return True only for errors that justify switching to Ollama.
    Auth errors (401 invalid key) are config issues — let them propagate."""
    exc_type = type(exc).__name__.lower()
    msg = str(exc).lower()
    # Never swallow auth errors — wrong key is a config problem, not an outage
    if "authentication" in exc_type or "invalid_api_key" in msg or "401" in msg:
        return False
    return any(k in msg or k in exc_type for k in (
        "rate_limit", "ratelimit", "429", "token", "quota", "exceeded",
        "connectionerror", "connection_error", "connection refused",
        "network", "timeout", "unreachable", "503", "service_unavailable",
    ))


def _groq_cooldown_elapsed() -> bool:
    return _groq_failed_at is not None and (time.time() - _groq_failed_at) > _GROQ_RETRY_SECS


# ── Public API ────────────────────────────────────────────────────────────────

def get_active_backend() -> str:
    """Return 'groq' or 'ollama'."""
    return _active_backend


def active_model_label() -> str:
    """Human-readable label for the currently active LLM."""
    if _active_backend == "groq":
        return f"Groq / {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}"
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    return f"Ollama / {model} (offline)"


def invoke_llm(messages: list) -> Any:
    """
    Invoke the active LLM.
    - Tries Groq first.
    - On rate-limit / connectivity error: logs a warning, switches to Ollama,
      and retries the SAME call on Ollama immediately.
    - After _GROQ_RETRY_SECS the next call will probe Groq again.
    - If both backends fail, raises RuntimeError with install instructions.
    """
    global _active_backend, _groq_failed_at, _groq_llm

    # Auto-retry Groq after cooldown
    with _state_lock:
        if _active_backend == "ollama" and _groq_cooldown_elapsed():
            logger.info("Groq cooldown elapsed — probing Groq again")
            _active_backend  = "groq"
            _groq_failed_at  = None
            _groq_llm = None  # force fresh client
        backend = _active_backend

    if backend == "groq":
        try:
            return _build_groq().invoke(messages)
        except Exception as exc:
            if _is_groq_error(exc):
                logger.warning(
                    "Groq unavailable (%s) — switching to Ollama offline model", exc
                )
                with _state_lock:
                    _active_backend = "ollama"
                    _groq_failed_at = time.time()
                # fall through to Ollama below
            else:
                raise   # real error (bad prompt, auth, etc.) — don't swallow

    # ── Ollama path ───────────────────────────────────────────────────────────
    try:
        return _build_ollama().invoke(messages)
    except Exception as exc:
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        raise RuntimeError(
            f"Both Groq and Ollama are unavailable.\n"
            f"Groq: rate-limited / no internet.\n"
            f"Ollama error: {exc}\n\n"
            f"To enable offline mode:\n"
            f"  1. Install Ollama: https://ollama.com/download\n"
            f"  2. Run: ollama pull {model}\n"
            f"  3. Ollama starts automatically on port 11434.\n"
            f"Or set OLLAMA_MODEL in .env to a model you have pulled."
        ) from exc
