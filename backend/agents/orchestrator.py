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
import os
import re
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

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_MISSING = object()  # sentinel: "no value yet", since None is a valid parse result


def _balanced_slice(text: str, open_ch: str, close_ch: str) -> str | None:
    """Return the first balanced open_ch..close_ch span, ignoring brackets that
    appear inside JSON string literals."""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_json(text: str, fallback: object) -> object:
    """
    Parse JSON out of an LLM response.

    Smaller local models routinely wrap the answer in prose ("Here are the
    findings:") and/or markdown fences. Treating that as a parse failure
    discarded the whole result, which in the vulnerability analyzer meant a repo
    full of real findings was reported as clean. Try, in order: the raw text,
    any fenced block, then the first balanced JSON array or object anywhere in
    the response.

    Each candidate is also retried with strict=False, which tolerates literal
    newlines inside string values. Models produce those whenever the schema
    asks for prose — a "step-by-step attack walkthrough" comes back with real
    line breaks in it — and the strict parser rejects the whole document for
    it, discarding an otherwise perfectly good answer.
    """
    cleaned = text.strip()
    candidates = [cleaned]
    candidates += [m.group(1).strip() for m in _FENCE_RE.finditer(cleaned)]
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        span = _balanced_slice(cleaned, open_ch, close_ch)
        if span:
            candidates.append(span)

    # The fallback declares the shape the caller wants. Without that, a reply
    # like {"executive_summary": ..., "key_recommendations": [...]} was parsed
    # into just the inner recommendations array, because the first balanced
    # "[" span is found before the enclosing "{" span — a perfectly good
    # summary object came back as a list and was discarded.
    expected = type(fallback) if isinstance(fallback, (list, dict)) else None
    wrong_shape = _MISSING

    for candidate in candidates:
        if not candidate:
            continue
        for strict in (True, False):
            try:
                value = json.loads(candidate, strict=strict)
            except json.JSONDecodeError:
                continue
            if expected is None or isinstance(value, expected):
                return value
            if wrong_shape is _MISSING:
                wrong_shape = value
            break

    if wrong_shape is not _MISSING:
        # Parsed, but not the shape asked for. Still better than the fallback:
        # the caller normalises it.
        return wrong_shape

    logger.warning("JSON parse failed, using fallback. Raw: %s", text[:200])
    return fallback


def _log(msg: str) -> list[str]:
    logger.info(msg)
    return [msg]


# Semgrep reports ERROR/WARNING/INFO; the rest of the pipeline speaks
# CRITICAL/HIGH/MEDIUM/LOW.
_SEMGREP_SEVERITY = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
_VALID_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# Patch generation is one LLM call per vulnerability, so it is capped.
_MAX_PATCH_TARGETS = int(os.getenv("MAX_PATCH_TARGETS", "10"))

# ── Risk scoring ──────────────────────────────────────────────
# The risk score used to be whatever number the model wrote, and it did not
# survive comparison between scans: 12 findings (1 HIGH, 5 MEDIUM, 6 LOW)
# scored 20/100 LOW while 6 findings (1 HIGH, 2 MEDIUM, 3 LOW) scored 40/100
# MEDIUM — half the findings, less severe, double the score. The score is the
# largest number in the UI and it is plotted as a trend across rescans, so it
# has to be reproducible and it has to fall when a vulnerability is fixed.
# It is now derived from the severity counts; the model only writes prose.
_SEVERITY_WEIGHT = {"CRITICAL": 40, "HIGH": 20, "MEDIUM": 8, "LOW": 2}
# Each severity contributes at most this much, so a long tail of LOW findings
# cannot add up to a crisis (50 informational findings is not a breach).
_SEVERITY_BAND_CAP = {"CRITICAL": 100, "HIGH": 60, "MEDIUM": 30, "LOW": 10}
# ...and the worst finding sets a floor, so one RCE in an otherwise clean repo
# cannot be diluted into a low score.
_SEVERITY_FLOOR = {"CRITICAL": 80, "HIGH": 40, "MEDIUM": 15, "LOW": 5}
_RISK_BANDS = ((80, "CRITICAL"), (60, "HIGH"), (30, "MEDIUM"), (0, "LOW"))


def compute_risk(vulnerabilities: list[dict]) -> dict:
    """
    Score 0-100 from the severity mix, plus the arithmetic behind it.

    Deterministic and monotonic: the same findings always give the same score,
    and removing a finding never raises it.
    """
    counts = {sev: 0 for sev in _VALID_SEVERITIES}
    for v in vulnerabilities:
        sev = (v.get("severity") or "").upper()
        counts[sev if sev in counts else "MEDIUM"] += 1

    contributions = {
        sev: min(_SEVERITY_BAND_CAP[sev], _SEVERITY_WEIGHT[sev] * n)
        for sev, n in counts.items()
    }
    score = sum(contributions.values())

    worst = next((sev for sev in _VALID_SEVERITIES if counts[sev]), None)
    if worst:
        score = max(score, _SEVERITY_FLOOR[worst])
    score = min(100, score)

    level = next(name for threshold, name in _RISK_BANDS if score >= threshold)
    return {
        "risk_score": score,
        "overall_risk": level,
        "counts": counts,
        "contributions": contributions,
        "floor_applied": _SEVERITY_FLOOR[worst] if worst else 0,
    }


def _normalize_severity(finding: dict) -> str:
    sev = (finding.get("severity") or "").upper()
    if finding.get("source") == "semgrep":
        sev = _SEMGREP_SEVERITY.get(sev, sev)
    return sev if sev in _VALID_SEVERITIES else "MEDIUM"


def _vulns_from_raw_findings(findings: list[dict]) -> list[dict]:
    """
    Map scanner output to structured vulnerabilities without the LLM.

    Used when the model returns nothing usable. Semgrep and Bandit already
    supply a file, line, severity and description, so a failed LLM call must
    never turn real findings into a clean bill of health — it should only cost
    the enrichment (CVE lookup, prose, patches), not the findings themselves.
    """
    from tools.owasp_data import OWASP_TOP_10, match_owasp_category

    vulns = []
    for i, f in enumerate(findings, start=1):
        description = f.get("description", "") or ""
        category = f.get("category")
        if not category:
            key = match_owasp_category(
                f"{description} {f.get('rule_id', '')} {f.get('test_id', '')}"
            )
            category = (f"{key}-{OWASP_TOP_10[key]['name']}" if key
                        else "A05:2021-Security Misconfiguration")
        vulns.append({
            "id": f"VULN-{i:03d}",
            "file": f.get("file", ""),
            "line": f.get("line", 0),
            "severity": _normalize_severity(f),
            "category": category,
            "description": description,
            "cve": None,
            "source": f.get("source", "static-analysis"),
            "rule": f.get("test_id") or f.get("rule_id") or "",
        })
    return vulns


def _recommendations_from_vulns(vulnerabilities: list[dict], limit: int = 3) -> list[str]:
    """
    Derive action items from the findings themselves.

    The report model sometimes returns an executive summary and simply omits
    key_recommendations, which rendered as an empty "Key Recommendations"
    section on a report that had six findings. The most severe findings are
    the recommendations, so they never need to be invented.
    """
    ranked = sorted(
        vulnerabilities,
        key=lambda v: _SEVERITY_RANK.get((v.get("severity") or "").upper(), 99),
    )
    recs, seen = [], set()
    for v in ranked:
        # Falls back to the OWASP category so a finding with a blank
        # description still produces an action item rather than vanishing.
        description = (v.get("description") or "").strip() or v.get("category", "")
        if not description or description in seen:
            continue
        seen.add(description)
        location = v.get("file") or ""
        suffix = f" ({location})" if location and not location.startswith("http") else ""
        recs.append(f"[{v.get('severity', 'MEDIUM')}] Remediate: {description}{suffix}")
        if len(recs) == limit:
            break
    return recs


# Headers a browser only honours from a real response header, so a meta tag is
# not a workaround for them. (CSP and Referrer-Policy are excluded: those can be
# applied from the document, so the host is not what blocks them.)
_HEADER_ONLY_POLICIES = (
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Permissions-Policy",
    "Strict-Transport-Security",
)


def _header_remediation_for_static_host(vuln: dict, static_host: str | None) -> dict | None:
    """
    The fixed, correct answer for a header that the host cannot set.

    Returns None when this is not that case, so the caller falls through to the
    model. Deterministic because the remediation depends only on the platform:
    asking an LLM produced confident instructions for a settings page that does
    not exist.
    """
    if not static_host:
        return None

    description = vuln.get("description", "")
    if "security header" not in description.lower():
        return None
    header = next((h for h in _HEADER_ONLY_POLICIES if h.lower() in description.lower()), None)
    if not header:
        return None

    return {
        "vuln_id": vuln.get("id", ""),
        "file": vuln.get("file", ""),
        "remediation": (
            f"Not fixable on {static_host}. Serve the site through a proxy that "
            f"can add headers (Cloudflare: Rules > Transform Rules > Modify "
            f"Response Header), or move to a host with header rules "
            f"(Netlify _headers, Vercel vercel.json, Cloudflare Pages _headers), "
            f"then set: {header}"
        ),
        "explanation": (
            f"{static_host} serves static files and exposes no way to set a "
            f"response header, so there is no change to this repository that "
            f"adds {header}. A meta tag is not a substitute: browsers ignore "
            f"{header} in markup. Until the site sits behind something that can "
            f"set headers, this finding stands as an accepted risk."
        ),
        "source": "platform-constraint",
    }


def _exploit_from_vuln(vuln: dict) -> dict:
    """
    Describe a vulnerability's attack surface without the LLM.

    Counterpart to _vulns_from_raw_findings: when the model returns nothing
    usable for a finding, the OWASP category still supplies a real attack
    vector and impact. Degraded enrichment, not a missing finding.
    """
    from tools.owasp_data import get_category_detail

    detail = get_category_detail(vuln.get("category", "")) or {}
    location = vuln.get("file") or "the affected component"
    if vuln.get("line"):
        location = f"{location}:{vuln['line']}"
    examples = detail.get("examples") or []

    return {
        "vuln_id": vuln["id"],
        # Unscored rather than guessed — claiming EASY without analysis would
        # be the same invention this fallback exists to avoid.
        "exploitability": "UNKNOWN",
        "attack_vector": (
            f"{detail.get('name', 'Security weakness')} reachable at {location}. "
            f"Typical vector: {examples[0]}" if examples
            else f"{detail.get('name', 'Security weakness')} reachable at {location}."
        ),
        "impact": detail.get("description", vuln.get("description", "")),
        "poc_description": (
            "Automated exploit reasoning was unavailable for this finding. "
            f"Reproduce manually at {location}: {vuln.get('description', '')}"
        ),
        "cwes": detail.get("cwes", []),
        "source": "owasp-reference",
    }


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
        meta: dict = {}
        raw_findings = scan_website(state["repo_url"], meta=meta)

        # The target served a bot challenge instead of the application. Its
        # headers and cookies are the challenge page's, so grading them would
        # produce confident findings about a page real users never see. Stop
        # here, and do not port scan a host that has just told us to go away.
        if meta.get("blocked"):
            logs.append(f"[Scanner] Target blocked automated scanning: {meta['blocked']}")
            logs.append("[Scanner] No assessment performed - results would not "
                        "reflect the real security posture")
            return {
                "repo_path": "",
                "tech_stack": {"type": "website", "url": state["repo_url"],
                               "cdn": meta.get("cdn"), "blocked": meta["blocked"]},
                "raw_findings": [],
                "errors": [f"Target blocked automated scanning: {meta['blocked']}. "
                           f"Scan a target you control, or one that permits scanning."],
                "status": "analyzing",
                "agent_logs": logs,
            }

        if meta.get("cdn"):
            logs.append(f"[Scanner] Fronted by {meta['cdn']} - findings describe the "
                        f"edge, not necessarily the origin")

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
        # On an HTTPS site, 443 is the site itself and 80 exists to redirect to
        # it. Both are the website working as intended, not exposures.
        from tools.port_scanner import WEB_SERVICE_PORTS
        skip = WEB_SERVICE_PORTS if urlparse(state["repo_url"]).scheme == "https" else frozenset()
        port_findings = scan_ports(host, skip_ports=skip, cdn=meta.get("cdn"))

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

        if meta.get("static_host"):
            logs.append(f"[Scanner] Host is {meta['static_host']} — response headers "
                        f"cannot be set here, remediation must go through a proxy or a "
                        f"host that supports header rules")

        return {
            "repo_path": "",
            "tech_stack": {"type": "website", "url": state["repo_url"],
                           "cdn": meta.get("cdn"),
                           "static_host": meta.get("static_host")},
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
    # Models sometimes wrap the array in an object, e.g. {"vulnerabilities": [...]}
    if isinstance(llm_vulns, dict):
        llm_vulns = next(
            (v for v in llm_vulns.values() if isinstance(v, list)), []
        )
    if not isinstance(llm_vulns, list):
        llm_vulns = []

    degraded = False
    if not llm_vulns and other_findings:
        # The scanners found real issues but the LLM gave us nothing usable.
        # Report the raw findings rather than an inaccurate "no vulnerabilities".
        llm_vulns = _vulns_from_raw_findings(other_findings)
        degraded = True
        logger.warning(
            "vuln_analyzer: LLM returned no usable vulnerabilities for %d raw "
            "findings — falling back to deterministic mapping",
            len(other_findings),
        )

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
    if degraded:
        logs.append(
            f"[VulnAnalyzer] LLM enrichment unavailable — reported "
            f"{len(llm_vulns)} findings directly from Semgrep/Bandit"
        )

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

    parsed = _parse_json(response.content, [])
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        parsed = []

    # Keep only entries that describe a vulnerability this scan actually found.
    # A model that hallucinates VULN-042 would otherwise put an exploit in the
    # report with nothing to click through to.
    target_ids = {v["id"] for v in targets}
    exploits = [
        e for e in parsed
        if isinstance(e, dict) and e.get("vuln_id") in target_ids
    ]

    # The log used to count the parsed reply, so a failed parse announced
    # "Analyzed 0 critical/high vulnerabilities" on a report that displayed a
    # HIGH finding and a patch for it — the pipeline looked like it disagreed
    # with itself. Every target is now accounted for: enriched by the model
    # where that worked, described from the OWASP category where it did not.
    covered = {e["vuln_id"] for e in exploits}
    unenriched = [v for v in targets if v["id"] not in covered]
    exploits.extend(_exploit_from_vuln(v) for v in unenriched)
    exploits.sort(key=lambda e: _SEVERITY_RANK.get(
        next((v["severity"] for v in targets if v["id"] == e["vuln_id"]), ""), 99))

    easy = sum(1 for e in exploits if e.get("exploitability") == "EASY")
    logs = [
        f"[ExploitReasoner] Analyzed {len(exploits)}/{len(targets)} critical/high vulnerabilities",
        f"[ExploitReasoner] {easy} are trivially exploitable (EASY)",
    ]
    if unenriched:
        logs.append(
            f"[ExploitReasoner] LLM enrichment unavailable for {len(unenriched)} "
            f"finding(s) — attack context taken from the OWASP category"
        )

    return {
        "exploits": exploits,
        "status": "patching",
        "agent_logs": logs,
    }


# ══════════════════════════════════════════════════════════════
#  Node: Fix Suggester
# ══════════════════════════════════════════════════════════════

def fix_suggester_node(state: ScanState) -> dict:
    """Generates code patches for the most severe vulnerabilities."""
    targets = [v for v in state["vulnerabilities"] if v["severity"] in ("CRITICAL", "HIGH", "MEDIUM")]

    if not targets:
        return {
            "patches": [],
            "status": "reporting",
            "agent_logs": ["[FixSuggester] Nothing to patch."],
        }

    # This loop costs one LLM call per vulnerability. A repo with 40+ findings
    # would otherwise mean 40 sequential calls: minutes of wall time on a local
    # model, and enough requests to trip a free-tier cloud rate limit. Patch the
    # most severe findings first and cap the rest.
    total_targets = len(targets)
    targets = sorted(
        targets, key=lambda v: _SEVERITY_RANK.get(v.get("severity"), 99)
    )[:_MAX_PATCH_TARGETS]

    patches = []
    logs = []
    if total_targets > len(targets):
        logs.append(
            f"[FixSuggester] {total_targets} patchable findings — generating "
            f"patches for the {len(targets)} most severe "
            f"(raise MAX_PATCH_TARGETS to change)"
        )

    # A website scan never sees source code. Asking for a code patch anyway makes
    # the model invent a codebase: scanning a site fronted by a CDN produced a
    # Flask snippet "fixing" cookies for a company that does not run Flask. With
    # no source to diff, the honest deliverable is configuration guidance.
    is_website = state.get("tech_stack", {}).get("type") == "website"

    if is_website:
        system_prompt = """You are a web security remediation agent.
You are advising on a LIVE WEBSITE. You have NOT seen its source code and you
do not know its language, framework or server software.

Never invent source code, file paths, or a framework. Give the concrete
configuration directive that fixes the issue, for the common web servers.

Return a single JSON object:
{
  "vuln_id": "VULN-001",
  "file": "the affected URL",
  "remediation": "the exact header or config directive to set",
  "explanation": "what this fixes and where to apply it (web server, CDN or app config)"
}
Output only valid JSON. No markdown."""
    else:
        system_prompt = """You are a secure code fix agent.
Generate a targeted code patch for the vulnerability provided.
Return a single JSON object:
{
  "vuln_id": "VULN-001",
  "file": "path/to/file.py",
  "original_code": "the vulnerable snippet",
  "patched_code": "the fixed snippet",
  "explanation": "what changed and why it fixes the vulnerability"
}
Output only valid JSON. No markdown."""

    static_host = state.get("tech_stack", {}).get("static_host")

    for vuln in targets:
        # When the host cannot set response headers, the remediation is a known
        # fact about the platform, not something to ask a model about. Left to
        # the LLM it answered "add the following header in the GitHub Pages
        # settings", which is a setting that does not exist.
        canned = _header_remediation_for_static_host(vuln, static_host)
        if canned:
            patches.append(canned)
            logs.append(f"[FixSuggester] {vuln['id']} cannot be fixed on "
                        f"{static_host} — gave the platform-level remediation")
            continue

        response = invoke_llm([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Fix this vulnerability:\n{json.dumps(vuln, indent=2)}"),
        ])

        patch = _parse_json(response.content, None)
        if isinstance(patch, dict) and is_website:
            # Guarantee no fabricated diff reaches the report, whatever the
            # model returned. The UI hides empty diff blocks.
            patch.pop("original_code", None)
            patch.pop("patched_code", None)
            patch.setdefault("vuln_id", vuln.get("id", ""))
            patch.setdefault("file", vuln.get("file", ""))
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
    vulns = state.get("vulnerabilities", [])
    critical = [v for v in vulns if v["severity"] == "CRITICAL"]
    high = [v for v in vulns if v["severity"] == "HIGH"]

    # Scored here, before the model is asked for anything, so the number is a
    # fact about the findings rather than an opinion about them.
    risk = compute_risk(vulns)

    response = invoke_llm([
        SystemMessage(content="""You are a security report writer.
Produce an executive summary for a security audit.

The risk score has already been calculated from the severity counts. Do not
restate it, dispute it, or invent one of your own — describe what was found.

Return a JSON object:
{
  "executive_summary": "2-3 sentences for a non-technical stakeholder",
  "key_recommendations": ["top 3 action items, ordered by priority"]
}
Output only valid JSON. No markdown."""),
        HumanMessage(content=f"""Repository: {state['repo_url']}
Tech stack: {state.get('tech_stack', {})}
Total vulnerabilities: {len(vulns)}
Critical: {len(critical)}, High: {len(high)}
Assessed risk: {risk['overall_risk']} ({risk['risk_score']}/100)
Top findings: {json.dumps(vulns[:5], indent=2)}"""),
    ])

    summary = _parse_json(response.content, {
        "executive_summary": "Security scan completed. Review findings for details.",
        "key_recommendations": ["Review and patch all CRITICAL and HIGH findings immediately."],
    })
    if not isinstance(summary, dict):
        summary = {"executive_summary": "Security scan completed. Review findings for details."}

    # Authoritative, whatever the model returned.
    summary["risk_score"] = risk["risk_score"]
    summary["overall_risk"] = risk["overall_risk"]
    summary["risk_breakdown"] = {
        "counts": risk["counts"],
        "contributions": risk["contributions"],
        "weights": _SEVERITY_WEIGHT,
        "band_caps": _SEVERITY_BAND_CAP,
        "floor_applied": risk["floor_applied"],
        "method": (
            "score = sum over severities of min(count * weight, band cap), "
            "raised to the floor for the most severe finding, capped at 100"
        ),
    }

    # Normalise key_recommendations — local models sometimes return objects
    # ...as {"priority": 1, "action_item": "..."} among others.
    recs = summary.get("key_recommendations", [])
    summary["key_recommendations"] = [
        r if isinstance(r, str)
        else (r.get("action_item") or r.get("recommendation")
              or r.get("action") or r.get("text") or str(r))
        for r in (recs if isinstance(recs, list) else [])
        if r
    ]
    # ...and sometimes omit the key entirely. An empty recommendations section
    # under a list of findings reads as "nothing to do here".
    if not summary["key_recommendations"] and vulns:
        summary["key_recommendations"] = _recommendations_from_vulns(vulns)

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
            "[ReportGenerator] Severity counts: "
            + ", ".join(f"{sev} {risk['counts'][sev]}" for sev in _VALID_SEVERITIES),
            "[ReportGenerator] Score contributions: "
            + ", ".join(f"{sev} +{risk['contributions'][sev]}" for sev in _VALID_SEVERITIES)
            + (f", floor {risk['floor_applied']}" if risk["floor_applied"] else ""),
            f"[ReportGenerator] Risk score: {summary['risk_score']}/100 (calculated, not model-generated)",
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
