"""
LLM Router — system-aware, Groq-first with Ollama fallback.

Routing priority
----------------
1. Groq (llama-3.3-70b-versatile)  — fast cloud inference; requires internet +
                                      GROQ_API_KEY.
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
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
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


def _is_groq_error(exc: Exception) -> bool:
    """Return True only for transient errors that justify falling back to Ollama."""
    exc_type = type(exc).__name__.lower()
    msg = str(exc).lower()
    # Never swallow auth errors — wrong key is a config problem, not an outage.
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
    """Human-readable label for the currently active LLM (used in /health)."""
    if _active_backend == "groq":
        return f"Groq / {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}"
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

    # Auto-retry Groq after cooldown
    with _state_lock:
        if _active_backend == "ollama" and _groq_cooldown_elapsed():
            logger.info("llm_router: Groq cooldown elapsed — probing Groq again")
            _active_backend = "groq"
            _groq_failed_at = None
            _groq_llm       = None   # force fresh client
        backend = _active_backend

    if backend == "groq":
        try:
            return _build_groq().invoke(messages)
        except Exception as exc:
            if _is_groq_error(exc):
                logger.warning("llm_router: Groq unavailable (%s) — falling back to Ollama", exc)
                with _state_lock:
                    _active_backend = "ollama"
                    _groq_failed_at = time.time()
                # fall through to Ollama
            else:
                raise   # auth error, bad prompt, etc. — don't swallow

    # ── Ollama path ───────────────────────────────────────────────────────────
    try:
        return _build_ollama().invoke(messages)
    except Exception as exc:
        model   = _ollama_model()
        profile = _detect_system()
        raise RuntimeError(
            f"Both Groq and Ollama are unavailable.\n"
            f"Groq: rate-limited / no internet.\n"
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
