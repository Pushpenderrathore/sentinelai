"""
VulnSentinel — LangGraph Orchestrator
Coordinates all security scanning agents in a directed acyclic pipeline.

Graph shape:
  orchestrator → scanner → vuln_analyzer → exploit_reasoner → fix_suggester → report_generator → END
                         ↘                ↘
                       (no findings)   (no vulns)
                               ↘         ↘
                              report_generator → END
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .state import ScanState
from .llm_router import invoke_llm, active_model_label

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════

def _parse_json(text: str, fallback: object) -> object:
    """Strip markdown fences if present, then parse JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed, using fallback. Raw: %s", text[:200])
        return fallback


def _log(msg: str) -> list[str]:
    logger.info(msg)
    return [msg]


# ══════════════════════════════════════════════════════════════
#  Node: Orchestrator
# ══════════════════════════════════════════════════════════════

def orchestrator_node(state: ScanState) -> dict:
    """Uses LLM to plan the scan strategy before handing off to the scanner."""
    from tools.website_scanner import is_github_url
    scan_type = "github" if is_github_url(state["repo_url"]) else "website"

    response = invoke_llm([
        SystemMessage(content="""You are a security orchestrator agent.
Given a target URL (GitHub repo or live website), output a JSON scan plan:
{
  "strategy": "brief description of approach",
  "priority_areas": ["list", "of", "focus", "areas"],
  "risk_level": "HIGH|MEDIUM|LOW"
}
Output only valid JSON. No markdown."""),
        HumanMessage(content=f"Plan a security audit for: {state['repo_url']}"),
    ])

    plan = _parse_json(response.content, {
        "strategy": "standard security scan",
        "priority_areas": ["authentication", "input validation", "dependencies"],
        "risk_level": "MEDIUM",
    })

    scan_label = "GitHub repository" if scan_type == "github" else "live website"
    return {
        "status": "scanning",
        "agent_logs": [
            f"[Orchestrator] Scan {state['scan_id']} started — target: {state['repo_url']}",
            f"[Orchestrator] Scan type: {scan_label}",
            f"[Orchestrator] LLM: {active_model_label()}",
            f"[Orchestrator] Strategy: {plan['strategy']}",
            f"[Orchestrator] Priority areas: {', '.join(plan['priority_areas'])}",
            f"[Orchestrator] Estimated risk level: {plan['risk_level']}",
        ],
    }


# ══════════════════════════════════════════════════════════════
#  Node: Scanner
# ══════════════════════════════════════════════════════════════

def scanner_node(state: ScanState) -> dict:
    """Routes to repo scanner (Semgrep + Bandit) or website scanner based on URL."""
    from tools.website_scanner import is_github_url, scan_website

    if is_github_url(state["repo_url"]):
        return _scan_github(state)
    return _scan_website(state)


def _scan_github(state: ScanState) -> dict:
    """Clone repo and run Semgrep + Bandit static analysis."""
    from tools.git_cloner import clone_repo, detect_tech_stack
    from tools.bandit_runner import run_bandit
    from tools.semgrep_runner import run_semgrep

    try:
        repo_path = clone_repo(state["repo_url"], state["scan_id"])
        tech_stack = detect_tech_stack(repo_path)
        logs = [
            f"[Scanner] Mode: GitHub repository",
            f"[Scanner] Cloned to {repo_path}",
            f"[Scanner] Languages: {', '.join(tech_stack.get('languages', ['unknown']))}",
            f"[Scanner] Dependencies: {len(tech_stack.get('dependencies', []))} found",
        ]

        raw_findings: list[dict] = []

        if "python" in [l.lower() for l in tech_stack.get("languages", [])]:
            bandit_results = run_bandit(repo_path)
            raw_findings.extend(bandit_results)
            logs.append(f"[Scanner] Bandit: {len(bandit_results)} issues")

        semgrep_results = run_semgrep(repo_path)
        raw_findings.extend(semgrep_results)
        logs.append(f"[Scanner] Semgrep: {len(semgrep_results)} issues")
        logs.append(f"[Scanner] Total raw findings: {len(raw_findings)}")

        return {
            "repo_path": repo_path,
            "tech_stack": tech_stack,
            "raw_findings": raw_findings,
            "status": "analyzing",
            "agent_logs": logs,
        }

    except Exception as exc:
        logger.exception("GitHub scanner failed")
        return {
            "errors": [f"Scanner error: {exc}"],
            "status": "error",
            "agent_logs": [f"[Scanner] ERROR: {exc}"],
        }


def _scan_website(state: ScanState) -> dict:
    """Run HTTP-based security checks + port scan against a live website."""
    from tools.website_scanner import scan_website
    from tools.port_scanner import scan_ports
    from urllib.parse import urlparse

    try:
        logs = [
            f"[Scanner] Mode: Live website",
            f"[Scanner] Checking security headers, SSL, exposed files, CORS, cookies…",
        ]
        raw_findings = scan_website(state["repo_url"])

        by_sev: dict[str, int] = {}
        for f in raw_findings:
            s = f.get("severity", "?")
            by_sev[s] = by_sev.get(s, 0) + 1

        logs.append(f"[Scanner] HTTP checks complete — {len(raw_findings)} raw findings")
        logs.append(f"[Scanner] Severity breakdown: {by_sev}")

        # Port scan
        host = urlparse(state["repo_url"]).hostname or state["repo_url"]
        from tools.port_scanner import COMMON_PORTS as _CP
        logs.append(f"[Scanner] Starting port scan on {host} ({len(_CP)} common ports)…")
        port_findings = scan_ports(host)

        open_ports = [p for p in port_findings if "port" in p]
        critical_ports = [p for p in open_ports if p["severity"] in ("CRITICAL", "HIGH")]

        if open_ports:
            port_list = ", ".join(f"{p['port']}/{p['service']}" for p in open_ports)
            logs.append(f"[Scanner] Open ports ({len(open_ports)}): {port_list}")
        else:
            logs.append(f"[Scanner] No common high-risk ports found open")

        if critical_ports:
            for p in critical_ports:
                logs.append(f"[Scanner] {p['severity']} RISK — {p['port']}/{p['service']}: {p['description']}")

        raw_findings = raw_findings + port_findings

        return {
            "repo_path": "",
            "tech_stack": {"type": "website", "url": state["repo_url"]},
            "raw_findings": raw_findings,
            "status": "analyzing",
            "agent_logs": logs,
        }

    except Exception as exc:
        logger.exception("Website scanner failed")
        return {
            "errors": [f"Scanner error: {exc}"],
            "status": "error",
            "agent_logs": [f"[Scanner] ERROR: {exc}"],
        }


# ══════════════════════════════════════════════════════════════
#  Node: Vulnerability Analyzer
# ══════════════════════════════════════════════════════════════

def vuln_analyzer_node(state: ScanState) -> dict:
    """Maps raw static-analysis findings to structured Vulnerability objects."""
    from tools.owasp_data import get_owasp_context

    # Port scan findings already have CVE/CWE data — promote them directly
    port_vulns = []
    for i, f in enumerate(state["raw_findings"]):
        if f.get("type") == "port_exposure" and "port" in f:
            port_vulns.append({
                "id": f"PORT-{f['port']}",
                "file": f.get("file", f"{f['service']}:{f['port']}"),
                "line": 0,
                "severity": f["severity"],
                "category": f.get("owasp_category", "A05:2021-Security Misconfiguration"),
                "description": f["description"],
                "cve": f["cves"][0] if f.get("cves") else None,
                "cwes": f.get("cwes", []),
                "all_cves": f.get("cves", []),
                "port": f["port"],
                "service": f["service"],
                "banner": f.get("banner", "—"),
                "recommendation": f.get("recommendation", ""),
            })

    # Static analysis / HTTP findings go through the LLM
    other_findings = [f for f in state["raw_findings"] if f.get("type") != "port_exposure"]
    findings_json = json.dumps(other_findings[:25], indent=2)  # cap for token budget
    owasp_ref = get_owasp_context()

    response = invoke_llm([
        SystemMessage(content=f"""You are a vulnerability analysis agent.
Map raw static analysis findings to structured vulnerability objects.
Use the OWASP reference below to assign the correct category and severity.

{owasp_ref}

Return a JSON array. Each object must have:
{{
  "id": "VULN-001",
  "file": "relative/path/to/file.py",
  "line": 42,
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "category": "OWASP label e.g. A03:2021-Injection",
  "description": "clear one-sentence description",
  "cve": "CVE-XXXX-XXXX or null"
}}
Severity guide: CRITICAL = direct RCE/SQLi/auth bypass, HIGH = exploitable with low effort,
MEDIUM = exploitable with moderate effort or requires chaining, LOW = hardening/best-practice.
Output only a valid JSON array. No markdown."""),
        HumanMessage(content=f"Analyze these raw findings:\n{findings_json}"),
    ])

    llm_vulns = _parse_json(response.content, [])
    vulns = port_vulns + llm_vulns

    severity_counts: dict[str, int] = {}
    for v in vulns:
        sev = v.get("severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    owasp_cats = list({v.get("category", "").split("-")[0] for v in vulns if v.get("category")})

    logs = [
        f"[VulnAnalyzer] Mapped {len(vulns)} structured vulnerabilities",
        f"[VulnAnalyzer] Severity breakdown: {severity_counts}",
        f"[VulnAnalyzer] OWASP categories identified: {', '.join(sorted(owasp_cats)) or 'none'}",
    ]
    if port_vulns:
        logs.append(f"[VulnAnalyzer] Port exposures: {len(port_vulns)} open ports mapped to CVEs/CWEs")

    return {
        "vulnerabilities": vulns,
        "status": "exploiting",
        "agent_logs": logs,
    }


# ══════════════════════════════════════════════════════════════
#  Node: Exploit Reasoner
# ══════════════════════════════════════════════════════════════

def exploit_reasoner_node(state: ScanState) -> dict:
    """Reasons about real-world exploitability for HIGH/CRITICAL vulnerabilities."""
    targets = [v for v in state["vulnerabilities"] if v["severity"] in ("CRITICAL", "HIGH")]

    if not targets:
        return {
            "exploits": [],
            "status": "patching",
            "agent_logs": ["[ExploitReasoner] No HIGH/CRITICAL findings — skipping."],
        }

    from tools.owasp_data import get_owasp_context
    owasp_ref = get_owasp_context()

    response = invoke_llm([
        SystemMessage(content=f"""You are an exploit reasoning agent.
For each vulnerability explain how a real-world attacker would exploit it.
Use the OWASP reference to inform the attack vector and realistic impact.

{owasp_ref}

Return a JSON array. Each object must have:
{{
  "vuln_id": "VULN-001",
  "exploitability": "EASY|MODERATE|HARD",
  "attack_vector": "e.g. unauthenticated POST /api/login with payload",
  "impact": "e.g. full database dump, RCE, account takeover",
  "poc_description": "step-by-step attack walkthrough"
}}
Output only a valid JSON array. Be specific and technical. No markdown."""),
        HumanMessage(content=f"Reason about exploitability:\n{json.dumps(targets, indent=2)}"),
    ])

    exploits = _parse_json(response.content, [])
    easy = sum(1 for e in exploits if e.get("exploitability") == "EASY")

    return {
        "exploits": exploits,
        "status": "patching",
        "agent_logs": [
            f"[ExploitReasoner] Analyzed {len(exploits)} critical/high vulnerabilities",
            f"[ExploitReasoner] {easy} are trivially exploitable (EASY)",
        ],
    }


# ══════════════════════════════════════════════════════════════
#  Node: Fix Suggester
# ══════════════════════════════════════════════════════════════

def fix_suggester_node(state: ScanState) -> dict:
    """Generates code patches for CRITICAL, HIGH, and MEDIUM vulnerabilities."""
    targets = [v for v in state["vulnerabilities"] if v["severity"] in ("CRITICAL", "HIGH", "MEDIUM")]

    if not targets:
        return {
            "patches": [],
            "status": "reporting",
            "agent_logs": ["[FixSuggester] Nothing to patch."],
        }

    patches = []
    logs = []

    for vuln in targets:
        response = invoke_llm([
            SystemMessage(content="""You are a secure code fix agent.
Generate a targeted code patch for the vulnerability provided.
Return a single JSON object:
{
  "vuln_id": "VULN-001",
  "file": "path/to/file.py",
  "original_code": "the vulnerable snippet",
  "patched_code": "the fixed snippet",
  "explanation": "what changed and why it fixes the vulnerability"
}
Output only valid JSON. No markdown."""),
            HumanMessage(content=f"Fix this vulnerability:\n{json.dumps(vuln, indent=2)}"),
        ])

        patch = _parse_json(response.content, None)
        if patch:
            patches.append(patch)
            logs.append(f"[FixSuggester] Patch ready for {vuln['id']} — {vuln['severity']}")
        else:
            logs.append(f"[FixSuggester] Could not generate patch for {vuln['id']}")

    logs.append(f"[FixSuggester] {len(patches)}/{len(targets)} patches generated")

    return {
        "patches": patches,
        "status": "reporting",
        "agent_logs": logs,
    }


# ══════════════════════════════════════════════════════════════
#  Node: Report Generator
# ══════════════════════════════════════════════════════════════

def report_generator_node(state: ScanState) -> dict:
    """Compiles all agent outputs into the final structured report."""
    critical = [v for v in state.get("vulnerabilities", []) if v["severity"] == "CRITICAL"]
    high = [v for v in state.get("vulnerabilities", []) if v["severity"] == "HIGH"]

    response = invoke_llm([
        SystemMessage(content="""You are a security report writer.
Produce an executive summary for a security audit.
Return a JSON object:
{
  "executive_summary": "2-3 sentences for a non-technical stakeholder",
  "risk_score": <integer 0-100>,
  "overall_risk": "CRITICAL|HIGH|MEDIUM|LOW",
  "key_recommendations": ["top 3 action items, ordered by priority"]
}
Output only valid JSON. No markdown."""),
        HumanMessage(content=f"""Repository: {state['repo_url']}
Tech stack: {state.get('tech_stack', {})}
Total vulnerabilities: {len(state.get('vulnerabilities', []))}
Critical: {len(critical)}, High: {len(high)}
Top findings: {json.dumps(state.get('vulnerabilities', [])[:5], indent=2)}"""),
    ])

    summary = _parse_json(response.content, {
        "executive_summary": "Security scan completed. Review findings for details.",
        "risk_score": 50,
        "overall_risk": "MEDIUM",
        "key_recommendations": ["Review and patch all CRITICAL and HIGH findings immediately."],
    })

    # Normalise key_recommendations — local models sometimes return objects
    recs = summary.get("key_recommendations", [])
    summary["key_recommendations"] = [
        r if isinstance(r, str)
        else r.get("recommendation") or r.get("text") or str(r)
        for r in (recs if isinstance(recs, list) else [])
    ]

    report = {
        "scan_id": state["scan_id"],
        "repo_url": state["repo_url"],
        "tech_stack": state.get("tech_stack", {}),
        "summary": summary,
        "vulnerabilities": state.get("vulnerabilities", []),
        "exploits": state.get("exploits", []),
        "patches": state.get("patches", []),
        "total_findings": len(state.get("vulnerabilities", [])),
        "errors": state.get("errors", []),
    }

    return {
        "report": report,
        "status": "done",
        "agent_logs": [
            f"[ReportGenerator] Risk score: {summary['risk_score']}/100",
            f"[ReportGenerator] Overall risk: {summary['overall_risk']}",
            f"[ReportGenerator] Scan {state['scan_id']} complete.",
        ],
    }


# ══════════════════════════════════════════════════════════════
#  Conditional routing
# ══════════════════════════════════════════════════════════════

def _route_after_scanner(state: ScanState) -> Literal["vuln_analyzer", "report_generator"]:
    if state.get("errors") or not state.get("raw_findings"):
        return "report_generator"
    return "vuln_analyzer"


def _route_after_vuln_analyzer(state: ScanState) -> Literal["exploit_reasoner", "report_generator"]:
    if not state.get("vulnerabilities"):
        return "report_generator"
    return "exploit_reasoner"


# ══════════════════════════════════════════════════════════════
#  Graph assembly
# ══════════════════════════════════════════════════════════════

def build_graph() -> StateGraph:
    graph = StateGraph(ScanState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("scanner", scanner_node)
    graph.add_node("vuln_analyzer", vuln_analyzer_node)
    graph.add_node("exploit_reasoner", exploit_reasoner_node)
    graph.add_node("fix_suggester", fix_suggester_node)
    graph.add_node("report_generator", report_generator_node)

    graph.set_entry_point("orchestrator")

    graph.add_edge("orchestrator", "scanner")
    graph.add_conditional_edges("scanner", _route_after_scanner, {
        "vuln_analyzer": "vuln_analyzer",
        "report_generator": "report_generator",
    })
    graph.add_conditional_edges("vuln_analyzer", _route_after_vuln_analyzer, {
        "exploit_reasoner": "exploit_reasoner",
        "report_generator": "report_generator",
    })
    graph.add_edge("exploit_reasoner", "fix_suggester")
    graph.add_edge("fix_suggester", "report_generator")
    graph.add_edge("report_generator", END)

    return graph.compile(checkpointer=MemorySaver())


_graph = build_graph()


# ══════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════

def _initial_state(repo_url: str, scan_id: Optional[str] = None) -> ScanState:
    sid = scan_id or str(uuid.uuid4())[:8]
    return ScanState(
        repo_url=repo_url,
        scan_id=sid,
        repo_path="",
        tech_stack={},
        raw_findings=[],
        vulnerabilities=[],
        exploits=[],
        patches=[],
        report={},
        status="starting",
        errors=[],
        agent_logs=[f"[Orchestrator] Initializing scan {sid} for {repo_url}"],
    )


async def run_scan(repo_url: str, scan_id: Optional[str] = None) -> ScanState:
    """Run a full scan and return the completed state."""
    state = _initial_state(repo_url, scan_id)
    config = {"configurable": {"thread_id": state["scan_id"]}}
    return await _graph.ainvoke(state, config=config)


async def stream_scan(repo_url: str, scan_id: Optional[str] = None) -> AsyncGenerator[dict, None]:
    """Yield node-by-node updates for WebSocket streaming to the frontend."""
    state = _initial_state(repo_url, scan_id)
    config = {"configurable": {"thread_id": state["scan_id"]}}

    async for event in _graph.astream(state, config=config):
        node_name, node_output = next(iter(event.items()))
        yield {
            "node": node_name,
            "logs": node_output.get("agent_logs", []),
            "status": node_output.get("status", ""),
            "scan_id": state["scan_id"],
        }
