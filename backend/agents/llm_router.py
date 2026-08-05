"""
LLM Router — system-aware, Groq-first with Ollama fallback.

Routing priority
----------------
1. Groq (llama-3.1-8b-instant)     — fast cloud inference; requires internet +
                                      GROQ_API_KEY. Override with GROQ_MODEL.
2. Ollama (local)                   — offline fallback.  The model is chosen
                                      automatically based on detected hardware
                                      unless OLLAMA_MODEL is set explicitly.

System-aware Ollama model selection
------------------------------------
On startup, system_detector.detect() classifies the host as:
  high  → llama3.1:8b   (RAM ≥ 16 GB  AND  cores ≥ 8)
  mid   → llama3.2      (RAM ≥ 8 GB   AND  cores ≥ 4,  or GPU present)
  low   → phi3:mini     (anything else — lightweight, ~2.3 GB)

Override any tier's model via env vars:
  OLLAMA_MODEL          — override for ALL tiers (backward-compatible)
  OLLAMA_MODEL_LOW      — override for low tier only
  OLLAMA_MODEL_MID      — override for mid tier only
  OLLAMA_MODEL_HIGH     — override for high tier only
  SYSTEM_SPEC_OVERRIDE  — force tier:  high | mid | low

Groq failover
-------------
Groq rate-limit / network errors switch ALL subsequent calls to Ollama.
After _GROQ_RETRY_SECS (30 min) the router probes Groq again automatically.
Auth errors (401) are never swallowed — they propagate immediately.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from agents.system_detector import detect as _detect_system

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────
# Guarded by _state_lock so concurrent LangGraph nodes don't race.

_state_lock      = threading.Lock()
_groq_llm        = None
_ollama_llm      = None
_active_backend:  str        = "groq"
_groq_failed_at:  float|None = None
_GROQ_RETRY_SECS: int        = 1800   # 30 minutes

# Transient Groq errors (e.g. 429 rate limit) are retried in-place with backoff
# before failing over — this matters on hosts with no Ollama (e.g. Render), where
# a single blip would otherwise lock every scan onto a dead backend.
_GROQ_MAX_ATTEMPTS:  int   = int(os.getenv("GROQ_MAX_ATTEMPTS", "3"))
_GROQ_RETRY_BACKOFF: float = float(os.getenv("GROQ_RETRY_BACKOFF", "2.0"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ollama_model() -> str:
    """
    Return the Ollama model name to use.

    Precedence (highest first):
      1. OLLAMA_MODEL env var  — explicit user override, always wins.
      2. System-detected tier  — auto-selected lightweight/mid/full model.
    """
    explicit = os.getenv("OLLAMA_MODEL", "").strip()
    if explicit:
        return explicit
    profile = _detect_system()
    logger.debug("llm_router: system tier=%s → ollama model=%s", profile.tier, profile.ollama_model)
    return profile.ollama_model


# ── LLM constructors ─────────────────────────────────────────────────────────

def _build_groq():
    global _groq_llm
    with _state_lock:
        if _groq_llm is None:
            from langchain_groq import ChatGroq
            _groq_llm = ChatGroq(
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                temperature=0,
            )
        return _groq_llm


def _build_ollama():
    global _ollama_llm
    with _state_lock:
        if _ollama_llm is None:
            from langchain_ollama import ChatOllama
            model    = _ollama_model()
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            logger.info("llm_router: Ollama → %s @ %s", model, base_url)
            _ollama_llm = ChatOllama(model=model, base_url=base_url, temperature=0)
        return _ollama_llm


def _groq_configured() -> bool:
    """True when a Groq API key is present in the environment."""
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def _is_groq_error(exc: Exception) -> bool:
    """Return True only for transient errors that justify falling back to Ollama."""
    exc_type = type(exc).__name__.lower()
    msg = str(exc).lower()
    # A WRONG key is a config problem and must surface. A MISSING key is not —
    # it just means the cloud backend was never set up, so Ollama should serve
    # the request instead of the whole pipeline dying.
    if "must be set" in msg or "api_key client option" in msg:
        return True
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
    # Report the backend that would actually serve the next call. Without a key
    # that is Ollama, even before the first request has flipped the state.
    if _active_backend == "groq" and not _groq_configured():
        return "ollama"
    return _active_backend


def active_model_label() -> str:
    """Human-readable label for the currently active LLM (used in /health)."""
    if get_active_backend() == "groq":
        return f"Groq / {os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')}"
    model   = _ollama_model()
    profile = _detect_system()
    return f"Ollama / {model} (tier={profile.tier}, offline)"


def get_system_profile() -> dict:
    """Return the detected system profile as a plain dict (for /health endpoint)."""
    p = _detect_system()
    return {
        "tier":         p.tier,
        "ram_gb":       p.ram_gb,
        "cpu_cores":    p.cpu_cores,
        "has_gpu":      p.has_gpu,
        "ollama_model": p.ollama_model,
    }


def invoke_llm(messages: list) -> Any:
    """
    Invoke the active LLM with automatic fallback.

    Flow:
      - Groq is tried first (if active).
      - Transient Groq errors trigger an immediate Ollama retry and mark
        Groq as failed for _GROQ_RETRY_SECS.
      - After the cooldown the next call transparently probes Groq again.
      - If both fail, raises RuntimeError with actionable instructions.
    """
    global _active_backend, _groq_failed_at, _groq_llm

    # No key configured at all — Groq was never an option. Go straight to the
    # local model instead of burning the retry/backoff budget on every call.
    if not _groq_configured():
        with _state_lock:
            if _active_backend != "ollama":
                logger.info("llm_router: no GROQ_API_KEY set — running offline on Ollama")
                _active_backend = "ollama"
        return _invoke_ollama(messages)

    # Auto-retry Groq after cooldown
    with _state_lock:
        if _active_backend == "ollama" and _groq_cooldown_elapsed():
            logger.info("llm_router: Groq cooldown elapsed — probing Groq again")
            _active_backend = "groq"
            _groq_failed_at = None
            _groq_llm       = None   # force fresh client
        backend = _active_backend

    if backend == "groq":
        last_exc: Exception | None = None
        for attempt in range(_GROQ_MAX_ATTEMPTS):
            try:
                return _build_groq().invoke(messages)
            except Exception as exc:
                if not _is_groq_error(exc):
                    raise   # auth error, bad prompt, etc. — don't swallow
                last_exc = exc
                if attempt < _GROQ_MAX_ATTEMPTS - 1:
                    delay = _GROQ_RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "llm_router: Groq transient error (%s) — retry %d/%d in %.1fs",
                        exc, attempt + 1, _GROQ_MAX_ATTEMPTS, delay,
                    )
                    time.sleep(delay)
        # Retries exhausted — fail over to Ollama for this call.
        logger.warning(
            "llm_router: Groq unavailable after %d attempts (%s) — falling back to Ollama",
            _GROQ_MAX_ATTEMPTS, last_exc,
        )
        with _state_lock:
            _active_backend = "ollama"
            _groq_failed_at = time.time()
        # fall through to Ollama

    return _invoke_ollama(messages)


def _invoke_ollama(messages: list) -> Any:
    """Run the request on the local Ollama model, or explain why it cannot."""
    global _active_backend, _groq_failed_at

    try:
        return _build_ollama().invoke(messages)
    except Exception as exc:
        # Ollama is unavailable too (common in cloud deploys). Don't stay pinned
        # to a dead backend for the whole cooldown — revert to Groq so the next
        # call retries the cloud instead of failing fast for 30 minutes. With no
        # key configured there is nothing to revert to, so stay on Ollama and
        # keep /health honest.
        if _groq_configured():
            with _state_lock:
                _active_backend = "groq"
                _groq_failed_at = None
        model   = _ollama_model()
        profile = _detect_system()
        groq_state = ("rate-limited / no internet" if _groq_configured()
                      else "no GROQ_API_KEY configured")
        raise RuntimeError(
            f"Both Groq and Ollama are unavailable.\n"
            f"Groq: {groq_state}.\n"
            f"Ollama error: {exc}\n\n"
            f"Detected system: {profile}\n\n"
            f"To enable offline mode:\n"
            f"  1. Install Ollama: https://ollama.com/download\n"
            f"  2. Pull the recommended model: ollama pull {model}\n"
            f"  3. Ollama serves automatically on port 11434.\n"
            f"\nOr override the model for your tier in .env:\n"
            f"  OLLAMA_MODEL_LOW=phi3:mini   # < 8 GB RAM\n"
            f"  OLLAMA_MODEL_MID=llama3.2    # 8-16 GB RAM\n"
            f"  OLLAMA_MODEL_HIGH=llama3.1:8b  # 16+ GB RAM"
        ) from exc
