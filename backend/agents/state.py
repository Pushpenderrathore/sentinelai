"""
Shared state schema for the VulnSentinel agent graph.
All nodes read from and write to ScanState.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class Vulnerability(TypedDict):
    id: str
    file: str
    line: int
    severity: str       # CRITICAL | HIGH | MEDIUM | LOW
    category: str       # OWASP Top 10 label e.g. "A03:2021-Injection"
    description: str
    cve: Optional[str]


class ExploitAnalysis(TypedDict):
    vuln_id: str
    exploitability: str     # EASY | MODERATE | HARD | UNKNOWN (not model-assessed)
    attack_vector: str
    impact: str
    poc_description: str


class Patch(TypedDict):
    vuln_id: str
    file: str
    original_code: str
    patched_code: str
    explanation: str


class ScanState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    repo_url: str
    scan_id: str

    # ── Scanner output ─────────────────────────────────────
    repo_path: str
    tech_stack: Dict[str, Any]
    raw_findings: List[Dict[str, Any]]

    # ── Per-agent outputs ──────────────────────────────────
    vulnerabilities: List[Vulnerability]
    exploits: List[ExploitAnalysis]
    patches: List[Patch]

    # ── Final report ───────────────────────────────────────
    report: Dict[str, Any]

    # ── Control flow ───────────────────────────────────────
    status: str         # starting | scanning | analyzing | exploiting | patching | reporting | done | error
    errors: List[str]

    # Accumulates across nodes; streamed live to frontend via WebSocket
    agent_logs: Annotated[List[str], operator.add]
