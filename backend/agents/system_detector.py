"""
system_detector.py — Detect host system capabilities and classify spec tier.

Spec tiers
----------
high  RAM >= 16 GB  AND  CPU cores >= 8
mid   RAM >= 8 GB   AND  CPU cores >= 4   (and not high)
low   anything else (RAM < 8 GB  OR  CPU cores < 4)

GPU presence upgrades a "low" system to "mid" automatically, because even
a modest GPU can handle larger quantised models.

The result is cached for the lifetime of the process — hardware doesn't
change at runtime.

Environment overrides (useful for containers / CI)
---------------------------------------------------
SYSTEM_SPEC_OVERRIDE=high|mid|low   — skip detection entirely
SYSTEM_RAM_GB=<float>               — pretend the system has this much RAM
SYSTEM_CPU_CORES=<int>              — pretend the system has this many cores
SYSTEM_HAS_GPU=true|false           — pretend GPU presence

Recommended Ollama models per tier
-----------------------------------
low   phi3:mini   (3.8 B, ~2.3 GB VRAM/RAM)
mid   llama3.2    (3 B default; or mistral 7 B)
high  llama3.1:8b (8 B; or llama3.3:70b if VRAM allows)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

# ── Recommended models per tier ───────────────────────────────────────────────

TIER_OLLAMA_MODELS: dict[str, str] = {
    "low":  os.getenv("OLLAMA_MODEL_LOW",  "phi3:mini"),
    "mid":  os.getenv("OLLAMA_MODEL_MID",  "llama3.2"),
    "high": os.getenv("OLLAMA_MODEL_HIGH", "llama3.1:8b"),
}

# Thresholds
_RAM_LOW_GB   = 8
_RAM_HIGH_GB  = 16
_CORES_LOW    = 4
_CORES_HIGH   = 8


@dataclass(frozen=True)
class SystemProfile:
    ram_gb:    float
    cpu_cores: int
    has_gpu:   bool
    tier:      str          # "low" | "mid" | "high"
    ollama_model: str       # recommended model for this tier

    def is_low(self)  -> bool: return self.tier == "low"
    def is_mid(self)  -> bool: return self.tier == "mid"
    def is_high(self) -> bool: return self.tier == "high"

    def __str__(self) -> str:
        gpu = "GPU" if self.has_gpu else "no GPU"
        return (
            f"SystemProfile(tier={self.tier}, ram={self.ram_gb:.1f}GB, "
            f"cores={self.cpu_cores}, {gpu}, model={self.ollama_model})"
        )


def _detect_ram_gb() -> float:
    """Return total RAM in GB. Falls back to 0 on failure."""
    override = os.getenv("SYSTEM_RAM_GB")
    if override:
        return float(override)
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    # /proc/meminfo fallback (Linux)
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / (1024 ** 2)
    except OSError:
        pass
    logger.warning("system_detector: could not read RAM — assuming 0 GB")
    return 0.0


def _detect_cpu_cores() -> int:
    """Return logical CPU count. Falls back to 1 on failure."""
    override = os.getenv("SYSTEM_CPU_CORES")
    if override:
        return int(override)
    try:
        import os as _os
        count = _os.cpu_count()
        if count:
            return count
    except Exception:
        pass
    logger.warning("system_detector: could not read CPU count — assuming 1")
    return 1


def _detect_gpu() -> bool:
    """Return True if any GPU is detectable (CUDA, ROCm, Apple MPS, or env flag)."""
    override = os.getenv("SYSTEM_HAS_GPU", "").lower()
    if override in ("true", "1", "yes"):
        return True
    if override in ("false", "0", "no"):
        return False
    # CUDA via PyTorch (optional)
    try:
        import torch
        if torch.cuda.is_available() or getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return True
    except ImportError:
        pass
    # nvidia-smi binary present?
    try:
        import shutil
        if shutil.which("nvidia-smi"):
            return True
    except Exception:
        pass
    # ROCm
    try:
        if shutil.which("rocm-smi"):
            return True
    except Exception:
        pass
    return False


def _classify(ram_gb: float, cpu_cores: int, has_gpu: bool) -> str:
    """Return 'high', 'mid', or 'low'."""
    # Explicit override wins
    override = os.getenv("SYSTEM_SPEC_OVERRIDE", "").lower()
    if override in ("high", "mid", "low"):
        return override

    if ram_gb >= _RAM_HIGH_GB and cpu_cores >= _CORES_HIGH:
        return "high"
    if (ram_gb >= _RAM_LOW_GB and cpu_cores >= _CORES_LOW) or has_gpu:
        return "mid"
    return "low"


@lru_cache(maxsize=1)
def detect() -> SystemProfile:
    """
    Detect system capabilities and return a cached SystemProfile.

    Call this once at startup; the result is memoised for the process lifetime.
    Use detect.cache_clear() in tests to reset.
    """
    ram_gb    = _detect_ram_gb()
    cpu_cores = _detect_cpu_cores()
    has_gpu   = _detect_gpu()
    tier      = _classify(ram_gb, cpu_cores, has_gpu)
    model     = TIER_OLLAMA_MODELS[tier]

    profile = SystemProfile(
        ram_gb=round(ram_gb, 2),
        cpu_cores=cpu_cores,
        has_gpu=has_gpu,
        tier=tier,
        ollama_model=model,
    )
    logger.info("system_detector: %s", profile)
    return profile
