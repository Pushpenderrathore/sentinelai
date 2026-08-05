"""
Tests for hardware detection and spec-tier classification.

Covers a real failure: RAM detection supported only psutil (not a dependency)
and /proc/meminfo (Linux only), so every macOS host reported 0 GB and was
classified as the lowest tier regardless of its actual hardware.
"""

from __future__ import annotations

import pytest

from agents import system_detector


@pytest.fixture(autouse=True)
def clear_detect_cache():
    system_detector.detect.cache_clear()
    yield
    system_detector.detect.cache_clear()


class TestRamDetection:
    def test_reports_real_ram_on_this_platform(self, monkeypatch):
        """Must work without psutil on Linux, macOS and Windows CI runners."""
        monkeypatch.delenv("SYSTEM_RAM_GB", raising=False)
        assert system_detector._detect_ram_gb() > 0.0

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("SYSTEM_RAM_GB", "8")
        assert system_detector._detect_ram_gb() == 8.0


class TestClassification:
    @pytest.mark.parametrize("ram,cores,gpu,tier", [
        (32.0, 16, False, "high"),
        (24.0, 15, True, "high"),
        (8.0, 4, False, "mid"),
        (4.0, 2, True, "mid"),      # GPU alone lifts a weak host to mid
        (4.0, 2, False, "low"),
        (0.0, 15, False, "low"),    # the misdetection symptom
    ])
    def test_tiers(self, monkeypatch, ram, cores, gpu, tier):
        monkeypatch.delenv("SYSTEM_SPEC_OVERRIDE", raising=False)
        assert system_detector._classify(ram, cores, gpu) == tier

    def test_explicit_override_wins(self, monkeypatch):
        monkeypatch.setenv("SYSTEM_SPEC_OVERRIDE", "low")
        assert system_detector._classify(64.0, 32, True) == "low"


class TestProfile:
    def test_detected_profile_is_self_consistent(self, monkeypatch):
        monkeypatch.delenv("SYSTEM_SPEC_OVERRIDE", raising=False)
        monkeypatch.delenv("SYSTEM_RAM_GB", raising=False)
        profile = system_detector.detect()
        assert profile.tier in ("low", "mid", "high")
        assert profile.ram_gb > 0.0
        assert profile.cpu_cores >= 1
        assert profile.ollama_model

    def test_simulated_low_spec_host(self, monkeypatch):
        monkeypatch.setenv("SYSTEM_RAM_GB", "2")
        monkeypatch.setenv("SYSTEM_CPU_CORES", "2")
        monkeypatch.setenv("SYSTEM_HAS_GPU", "false")
        monkeypatch.delenv("SYSTEM_SPEC_OVERRIDE", raising=False)
        system_detector.detect.cache_clear()
        assert system_detector.detect().tier == "low"
