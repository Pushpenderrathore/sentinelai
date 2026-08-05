"""
Tests for LLM backend selection.

Covers a real failure: with no GROQ_API_KEY, ChatGroq raised at construction
time and the exception propagated instead of failing over, so every scan died
on a machine with no key. A missing key means the cloud backend was never set
up; a wrong key is a config error that must still surface.
"""

from __future__ import annotations

import pytest

from agents import llm_router


@pytest.fixture(autouse=True)
def reset_router_state(monkeypatch):
    """The router keeps module-level state; reset it around every test."""
    monkeypatch.setattr(llm_router, "_active_backend", "groq")
    monkeypatch.setattr(llm_router, "_groq_failed_at", None)
    monkeypatch.setattr(llm_router, "_groq_llm", None)
    yield


class TestGroqConfigured:
    def test_missing_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert llm_router._groq_configured() is False

    def test_blank_key_counts_as_missing(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "   ")
        assert llm_router._groq_configured() is False

    def test_present_key(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_example")
        assert llm_router._groq_configured() is True


class TestActiveBackend:
    def test_reports_ollama_when_no_key(self, monkeypatch):
        """/health must not claim Groq when Groq cannot possibly serve a call."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert llm_router.get_active_backend() == "ollama"
        assert "Ollama" in llm_router.active_model_label()

    def test_reports_groq_when_key_present(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_example")
        assert llm_router.get_active_backend() == "groq"
        assert "Groq" in llm_router.active_model_label()


class TestErrorClassification:
    def test_missing_key_error_triggers_fallback(self):
        exc = Exception(
            "The api_key client option must be set either by passing api_key "
            "to the client or by setting the GROQ_API_KEY environment variable"
        )
        assert llm_router._is_groq_error(exc) is True

    def test_invalid_key_does_not_trigger_fallback(self):
        """A wrong key is a config problem and must surface, not be swallowed."""
        assert llm_router._is_groq_error(Exception("invalid_api_key")) is False

    def test_401_does_not_trigger_fallback(self):
        assert llm_router._is_groq_error(Exception("Error code: 401")) is False

    @pytest.mark.parametrize("msg", [
        "rate_limit_exceeded",
        "Error code: 429",
        "quota exceeded for this month",
        "service_unavailable",
    ])
    def test_transient_errors_trigger_fallback(self, msg):
        assert llm_router._is_groq_error(Exception(msg)) is True

    def test_connection_error_type_triggers_fallback(self):
        class APIConnectionError(Exception):
            pass

        assert llm_router._is_groq_error(APIConnectionError("Connection error.")) is True

    def test_unrelated_error_does_not_trigger_fallback(self):
        assert llm_router._is_groq_error(ValueError("bad prompt")) is False


class TestRoutingWithoutKey:
    def test_no_key_skips_groq_entirely(self, monkeypatch):
        """Without a key the router must not construct a Groq client at all."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        def _fail(*_args, **_kwargs):
            raise AssertionError("Groq client must not be built without a key")

        monkeypatch.setattr(llm_router, "_build_groq", _fail)
        monkeypatch.setattr(
            llm_router, "_build_ollama",
            lambda: type("M", (), {"invoke": lambda self, m: "ollama-reply"})(),
        )
        assert llm_router.invoke_llm(["hi"]) == "ollama-reply"
        assert llm_router.get_active_backend() == "ollama"
