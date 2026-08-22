# SentinelAI - Autonomous Threat Detection Platform

> **FAR AWAY 2026 · Team Zen Hackers · Theme: Agentic & Autonomous Systems**

[![Release](https://img.shields.io/github/v/release/Pushpenderrathore/sentinelai?label=release)](https://github.com/Pushpenderrathore/sentinelai/releases/latest)
[![CI](https://github.com/Pushpenderrathore/sentinelai/actions/workflows/ci.yml/badge.svg)](https://github.com/Pushpenderrathore/sentinelai/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/Pushpenderrathore/sentinelai)](LICENSE)

![FAR AWAY 2026 - India's Biggest International Hackathon](docs/screenshots/faraway-theme.jpg)

SentinelAI is a multi-agent AI platform that detects threats autonomously - in **source code** and in **online exams** - without requiring human intervention. Two real-world problems. One agentic engine.

**Current release: [v1.0.0](https://github.com/Pushpenderrathore/sentinelai/releases/tag/v1.0.0)** - both scan modes working end to end, 332 tests, six-job CI. The running API reports its own version at `GET /health`.

---

## Table of Contents

- [Modules](#modules)
- [Why the findings can be trusted](#why-the-findings-can-be-trusted)
- [Data retention](#data-retention)
- [ML Integration](#ml-integration)
- [Demo](#demo)
- [VulnSentinel - Screenshots](#-vulnsentinel---screenshots)
- [ExamGuard - Screenshots](#-examguard---screenshots)
- [Sample Scan Results](#vulnsentinel---dual-scan-mode)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Run](#setup--run)
  - [Prerequisites](#prerequisites)
  - [Backend](#1---backend)
  - [Configuration reference](#configuration-reference)
  - [Offline / Ollama fallback](#offline--ollama-fallback-optional)
  - [Frontend](#2---frontend)
- [How It Works](#how-it-works)
  - [VulnSentinel - 6-Agent Pipeline](#vulnsentinel---6-agent-pipeline-github--website)
  - [Website Scanner Checks](#website-scanner-checks)
  - [Port Scanner - CVE/CWE Mapping](#port-scanner---cvecwe-mapping)
- [Testing & CI](#testing--ci)
- [FAQ](#faq)
  - [ExamGuard - Two-Phase System](#examguard---two-phase-system)
  - [Real-time Alert Thresholds](#real-time-alert-thresholds-examguard)
- [WebSocket Message Protocol](#websocket-message-protocol)
- [API Reference](#api-reference)
- [Team](#team)
- [License](#license)

---

## Modules

### 🔍 VulnSentinel - Autonomous Code & Website Security Auditor
Paste a **GitHub repository URL** or any **live website URL**. Six specialised agents run as a LangGraph pipeline: an Orchestrator plans the audit, a Scanner routes to the right engine - Semgrep and Bandit static analysis for repos, HTTP security checks for websites - and the remaining four map findings to OWASP Top 10 and CVEs, reason about real-world exploitability, generate patches or remediation guidance, and compile the report. All without a human in the loop.

The agents enrich the findings; they do not decide them. The risk score is calculated from the evidence, so a rescan reproduces it. See [Why the findings can be trusted](#why-the-findings-can-be-trusted).

### 🎓 ExamGuard - AI-Powered Exam Integrity Monitor
A proctoring system that monitors online exams in real time using tab-switch detection, webcam face analysis, **mobile phone detection**, and keystroke dynamics. Immediate rule-based alerts fire the moment suspicious behaviour is detected. Exams are **automatically terminated** after 5 tab switches. When the exam ends, a second agent pipeline performs deep behavioural analysis and generates an integrity report with a verdict.

---

## Why the findings can be trusted

A security tool is only worth as much as its output is defensible. These are the guarantees v1.0.0 makes, each of them visible in the live agent log during a scan.

**The risk score is calculated, not written by the model.** It comes from the severity counts: weighted counts, a per-severity cap so a long tail of LOW findings cannot add up to a crisis, and a floor from the worst finding so a single CRITICAL is not diluted away. The report carries the arithmetic, so anyone can check it:

```
[ReportGenerator] Severity counts: CRITICAL 0, HIGH 0, MEDIUM 2, LOW 4
[ReportGenerator] Score contributions: CRITICAL +0, HIGH +0, MEDIUM +16, LOW +8, floor 15
[ReportGenerator] Risk score: 24/100 (calculated, not model-generated)
```

The same findings always produce the same score, on Groq or on a local Ollama model. Fix something and rescan, and the number goes down.

**The model enriches findings; it cannot invent or suppress them.** The scanner's output is the finding set. The LLM adds OWASP category, CVE context and prose, and its severity is only accepted where the source is inference rather than measurement. Semgrep, Bandit and HTTP header checks keep their own severity, because those are facts a reviewer can reproduce with the same tools. A failed model call costs enrichment, never findings - and the log says so.

**Findings describe evidence, not assumptions.** Redirects are followed and reported at their destination. A CSP delivered by meta tag counts as applied; one set to report-only is reported as unenforced rather than missing. A header that the host physically cannot set is labelled with that constraint instead of advice you cannot act on. Bot-challenge pages are detected and refused rather than graded.

**Patches are diffed against the real file.** On a repository scan the flagged line is read from the clone, so a patch can never claim to change code that is not there.

**Port scanning requires authorisation.** Ports are probed only against hosts named in `AUTHORISED_SCAN_TARGETS`, and nothing is authorised by default. HTTP checks are unaffected.

### What it does not do

Website mode is a passive configuration and exposure audit. It reads headers, cookies, TLS and known paths; it never sends an attack payload, so it does not find SQL injection, XSS or broken access control in a running app. Code-level vulnerabilities are the repository scanner's job, via Semgrep and Bandit.

---

## Data retention

A scan report is a liability as well as an asset. It is a list of the ways into
a system, written down and kept. So SentinelAI treats a report as something with
a lifecycle rather than a row that lives forever, and it will tell you exactly
what happened when you ask for one to go away.

**A scan does not live in one place.** Its row sits in `scan_history.json`, its
findings can be offloaded to a cold archive file, a repository scan leaves a
clone in a temp workspace, and a running scan also holds an in-process session.
"Delete this scan" therefore touches several stores, and any of them can
succeed, refuse, or fail on its own.

**So every operation answers with a receipt**, one line per store plus a single
completion signal:

| Signal | Meaning |
|--------|---------|
| `complete` | Every store reached its intended end state. |
| `partial` | The operation ran, but scan data is still retained somewhere on purpose. |
| `blocked` | A legal hold or a running scan refused it. Nothing changed. |
| `unresolved` | A store failed, or a store disagrees with the ledger. |

Those four are not decoration. A delete is **`partial`**, not `complete`,
because the findings are kept so it can be undone. A purge under legal hold is
**`blocked`**, and the receipt names the hold and its reason. Purging findings
while keeping the score row is **`partial`**, and the receipt says which half
survived and why.

```
purge · 55667788 → PARTIAL
  complete            Findings payload    9 findings, their patches and the executive summary erased.
  retained            History record      Score, severity counts and scan date kept so this site's
                                          risk trend stays continuous. No vulnerability detail remains.
  retained_by_policy  Audit tombstone     Tombstone written to the ledger: scan id, domain and payload
                                          hash a8c1e7630e38. It proves the erasure happened and
                                          contains no finding data.
```

**The claim is checkable.** `GET /api/retention/scans/{id}/verify` ignores the
ledger and goes back to the stores themselves - the history file, the archive
directory, the temp workspace, the in-process registry - and reports what is
actually there. If a clone survived a purge, verification says `unresolved` and
names the path. A tool that reports its own erasure without checking is asking
to be believed; this one produces the evidence.

**The record cannot be quietly rewritten.** Every operation is appended to
`retention_audit.jsonl`, and each entry carries the hash of the entry before it.
Editing or removing any past entry breaks every hash after it, which
`GET /api/retention/audit` reports as `unresolved`.

**The schedule runs itself.** Scans are archived, then trashed, then purged on
the thresholds in `.env`. `POST /api/retention/sweep` defaults to a dry run, and
`as_of` evaluates the plan at a future date, so the whole schedule can be shown
without waiting for it. A sweep that archives four scans and is refused on a
fifth reports `partial` and names the fifth.

The console is at **`/retention`**.

---

## ML Integration

- Client-side ML models power real-time exam monitoring - face detection and mobile-phone detection run live in the browser
- Client-side inference keeps sensitive video data local and trims latency for face and mobile-phone analysis
- Browser-based models (TensorFlow.js / COCO-SSD / MediaPipe / face-api) run directly in the app for fast, responsive results
- LLM-based reasoning powers VulnSentinel's vulnerability analysis and ExamGuard's post-session integrity reports with remediation guidance
- Real-time integrity alerts are rule-based and handled by the backend

---

## Demo

> 📹 **Demo video:** *(add link after recording)*

### Try it yourself

The demo target is **OWASP Juice Shop**, a deliberately vulnerable application published to be tested, so no question of authorisation arises.

```bash
# Recommended: run it locally, so the demo does not depend on anyone's uptime.
# Map to 8080 - url_guard only permits ports 80, 443, 8080 and 8443.
docker run --rm -p 8080:3000 bkimminich/juice-shop
```

Then set `ALLOW_PRIVATE_TARGETS=true` in `backend/.env` and scan `http://localhost:8080/`.

> Scanning `localhost` also port scans **your own machine**, so anything you happen to be running shows up. Those findings say so in their own text - *"listening on this machine's loopback interface... describes the host running the scan, not an internet exposure"* - and are graded accordingly, rather than claiming your local database is exposed to the world.

> The public instance at `demo.owasp-juice.shop` also works, but it is a free Heroku dyno and goes down regularly - it returned `503 Application Error` twice while this section was being written. If it is down, SentinelAI says so rather than grading the error page:
>
> ```
> Target returned HTTP 503, so no security assessment was performed. The response
> is a server error page, not the application, and its headers are not the
> application's headers.
> ```

When the app is healthy, two of the findings can be verified in a second browser tab while the scan is still on screen:

| Finding | Check it |
|---------|----------|
| `Directory listing exposed: /ftp` | `/ftp` is a browsable directory. `acquisitions.md` inside it opens with *"This document is confidential"* |
| `Prometheus metrics exposed publicly` | `/metrics` serves ~26 KB of internal telemetry with no authentication |

Then read the score off the agent log rather than taking it on trust:

```
[VulnAnalyzer] 7 findings kept the scanner's severity (deterministic checks, not model judgement)
[ReportGenerator] Severity counts: CRITICAL 0, HIGH 3, MEDIUM 1, LOW 3
[ReportGenerator] Score contributions: CRITICAL +0, HIGH +60, MEDIUM +8, LOW +6, floor 40
[ReportGenerator] Risk score: 74/100 (calculated, not model-generated)
```

Add 60, 8 and 6 and you get the score. Scan twice and it is identical, on Groq or offline on Ollama, because it is arithmetic over the findings rather than something the model wrote.

**Against the public instance the port scan refuses to run**, because Juice Shop invites application testing but its hosting provider did not:

```
[Scanner] Port scan skipped - demo.owasp-juice.shop is not an authorised scan
          target. Port scanning a host you do not control is unauthorised
          testing, so it is off by default.
```

A local container is your own machine, so `ALLOW_PRIVATE_TARGETS=true` authorises it and the port scan runs. See [Port Scanner](#port-scanner---cvecwe-mapping).

**Home - SentinelAI module selector**
![SentinelAI Home](docs/screenshots/home2.png)

---

## 🔍 VulnSentinel - Screenshots

**Scan input page - auto-detects GitHub repo or live website URL**
![VulnSentinel Scan Input](docs/screenshots/vulnsentinel-scan-input.png)

**Live agent feed - website scan of Pushpenderrathore.github.io**
![VulnSentinel GitHub.io Scan](docs/screenshots/vulnsentinel-github-scan.png)

**Live agent feed + findings dashboard - example.com website scan**
![VulnSentinel Live Results](docs/screenshots/vulnsentinel-live-results.png)

---

## 🎓 ExamGuard - Screenshots

**Create a monitored exam session**
![ExamGuard Create Session](docs/screenshots/examguard-create.png)

**Student exam view - live webcam, timer, and Monitored badge**
![ExamGuard Student View](docs/screenshots/examguard-student.png)

**Exam submitted - AI integrity report generated for invigilator**
![ExamGuard Submitted](docs/screenshots/examguard-submitted.png)

**Invigilator monitor dashboard - AI agent pipeline running, SUSPICIOUS verdict (60/100)**
![ExamGuard Monitor Analysis](docs/screenshots/examguard-monitor-analysis.png)

**Invigilator monitor dashboard - idle state, 100/100 CLEAN score**
![ExamGuard Monitor Idle](docs/screenshots/examguard-monitor-idle.png)

---

### VulnSentinel - Dual scan mode

#### GitHub Repo Scan - OWASP Mutillidae (18 vulnerabilities)

```
Risk Score: 85/100 · Overall Risk: CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL  12   HIGH  4   MEDIUM  2   LOW  0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[CRITICAL] A03 Injection  - Command injection via exec() in content-security-policy.php:119
[CRITICAL] A03 Injection  - User data flows into SQL string in edit-account-profile.php:125
[CRITICAL] A07 Sec Misc   - Snyk API Key leaked in .github/workflows/scan-with-snyk-code.yml
[CRITICAL] A07 Sec Misc   - Hardcoded JWT token in src/includes/hints/jwt-hint.inc:46
[HIGH]     A03 Injection  - shell_exec() with unsanitised $domain in dns-lookup.php:165
[HIGH]     A05 Sec Misc   - SSL verification disabled in RemoteFileHandler.php:62
... + 12 more  · 16 auto-generated patches
```

#### Website Scan - brcmcet.edu.in (8 vulnerabilities)

```
Risk Score: 60/100 · Overall Risk: MEDIUM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL   0   HIGH  2   MEDIUM  3   LOW  3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HIGH]   A02 Cryptographic Failures    - Missing Strict-Transport-Security header
[HIGH]   A05 Security Misconfiguration - Missing Content-Security-Policy header
[MEDIUM] A05 Security Misconfiguration - Missing X-Frame-Options (clickjacking risk)
[MEDIUM] A05 Security Misconfiguration - Missing X-Content-Type-Options header
[MEDIUM] A05 Security Misconfiguration - PHPSESSID cookie missing Secure & HttpOnly flags
[LOW]    A05 Security Misconfiguration - Missing Referrer-Policy header
[LOW]    A05 Security Misconfiguration - Missing Permissions-Policy header
[LOW]    A05 Security Misconfiguration - Server header discloses Apache version
· 5 auto-generated remediation patches
```

### ExamGuard - Real-time proctoring demo

```
[00:12] ⚠  WARNING  Tab switch detected (1/3)
[00:34] ⚠  WARNING  Tab switch detected (2/3)
[00:41] 🚨 CRITICAL Face absent > 30 s continuous
[00:55] 📱 WARNING  Mobile phone detected in camera (conf 87%)
[01:02] ⚠  WARNING  Copy-paste event detected (1/2)
[01:15] 📱 CRITICAL Repeated phone use detected (2×)
[01:44] 🚨 CRITICAL Tab switch threshold reached (5) - exam auto-terminated

Exam auto-terminated after 5 tab switches
Post-session analysis complete
Integrity Score: 42/100 · Verdict: FLAGGED 🚨
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js 14 Frontend                         │
│   / (home)  ·  /scan  ·  /scan/[id]  ·  /exam/[id]  ·         │
│   /exam/[id]/monitor                                            │
└───────────────────┬─────────────────────────────────────────────┘
                    │  REST + WebSocket
┌───────────────────▼─────────────────────────────────────────────┐
│                  FastAPI Backend  (main.py)                      │
├──────────────────────────┬──────────────────────────────────────┤
│   VulnSentinel           │   ExamGuard                          │
│   POST /api/scan         │   POST /api/exam/session             │
│   WS   /ws/{scan_id}     │   GET  /api/exam/session/{id}        │
│   GET  /api/report/{id}  │   WS   /ws/exam/{id}  (bidir)        │
│   GET  /api/scans        │   WS   /ws/exam/{id}/monitor         │
│                          │   POST /api/exam/{id}/analyze        │
│                          │   WS   /ws/exam/{id}/analysis        │
│                          │   GET  /api/exam/report/{id}         │
│                          │   GET  /api/exam/sessions            │
├──────────────────────────┴──────────────────────────────────────┤
│              LangGraph Agent Pipelines                           │
│                                                                  │
│  VulnSentinel                         ExamGuard                  │
│  ┌──────────────────────────┐         ┌─────────────────────┐   │
│  │ orchestrator             │         │ session_monitor      │   │
│  │ → scanner ─┬─ GitHub     │         │ → behavior_analyzer  │   │
│  │            │  (Semgrep+  │         │ → anomaly_scorer     │   │
│  │            │   Bandit)   │         │ → alert_generator    │   │
│  │            └─ Website    │         │ → report_generator   │   │
│  │               (HTTP scan)│         └─────────────────────┘   │
│  │ → vuln_analyzer          │                                    │
│  │ → exploit_reasoner       │                                    │
│  │ → fix_suggester          │                                    │
│  │ → report_generator       │                                    │
│  └──────────────────────────┘                                    │
│  LLM: Groq (primary) → Ollama offline fallback (auto-switch)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM (primary) | Llama 3.3 70B via [Groq](https://console.groq.com) (free tier, cloud) |
| LLM (offline fallback) | Any local model via [Ollama](https://ollama.com) - auto-switches on rate-limit |
| Backend | Python 3.11 · FastAPI · WebSockets |
| Repo scanning | Semgrep · Bandit (static analysis) |
| Website scanning | HTTP headers · SSL · CORS · cookie · file exposure · port scan (CVE/CWE) |
| Frontend | Next.js 14 · TypeScript · Tailwind CSS |
| Real-time | Native WebSocket (browser ↔ server) |
| Face detection | `@vladmandic/face-api` (TinyFaceDetector - runs in-browser) |
| Phone detection | `@tensorflow-models/coco-ssd` (MobileNet V2 - runs in-browser, "cell phone" class) |

---

## Project Structure

```
sentinelai/
├── backend/
│   ├── main.py                     # FastAPI app - all routes & WebSocket endpoints
│   ├── agents/
│   │   ├── llm_router.py           # Groq-first LLM router with Ollama offline fallback
│   │   ├── state.py                # ScanState TypedDict
│   │   └── orchestrator.py         # VulnSentinel 6-node LangGraph graph
│   ├── exam_agents/
│   │   ├── exam_state.py           # ExamSession TypedDict
│   │   ├── exam_pipeline.py        # ExamGuard 5-node LangGraph graph
│   │   └── event_rules.py          # Rule-based instant alert thresholds
│   ├── tools/
│   │   ├── git_cloner.py           # Repo clone + tech stack detection
│   │   ├── bandit_runner.py        # Python static analysis
│   │   ├── semgrep_runner.py       # Multi-language static analysis
│   │   ├── website_scanner.py      # HTTP security checks (headers, SSL, cookies, exposed files)
│   │   ├── port_scanner.py         # Port scan - 25 ports, CVE/CWE risk mapping
│   │   └── owasp_data.py           # OWASP Top 10 2021 knowledge base
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx                # Homepage - module selector
    │   ├── scan/
    │   │   ├── page.tsx            # Repo URL input
    │   │   └── [id]/page.tsx       # Live scan dashboard (split-pane)
    │   └── exam/
    │       ├── page.tsx            # Create exam session (with quick-fill examples)
    │       ├── [id]/page.tsx       # Student exam view - proctored, auto-terminates at 5 tab switches
    │       └── [id]/monitor/page.tsx  # Invigilator dashboard - live alerts + AI report
    ├── components/
    │   ├── vulnsentinel/
    │   │   ├── AgentFeed.tsx       # Terminal-style live log stream
    │   │   └── VulnCard.tsx        # Vuln card with collapsible patch diff
    │   └── examguard/
    │       ├── AlertFeed.tsx       # Real-time alert stream
    │       ├── FaceMonitor.tsx     # Webcam feed + face detection + phone detection
    │       └── IntegrityScore.tsx  # Animated circular integrity gauge
    └── lib/
        ├── ws.ts                   # useWebSocket hook
        └── api.ts                  # Typed API client
```

---

## Setup & Run

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Semgrep](https://semgrep.dev/docs/getting-started/) - `pip install semgrep`
- [Bandit](https://bandit.readthedocs.io/) - `pip install bandit`
- Groq API key (free) → [console.groq.com](https://console.groq.com)
- (Optional) [Ollama](https://ollama.com/download) for offline/fallback mode

### 1 - Backend

```bash
cd backend

# Configure environment
cp .env.example .env
# Edit .env - set GROQ_API_KEY=gsk_...  (free at console.groq.com)

# Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start server
bash run.sh
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

#### Configuration reference

Everything has a working default; `backend/.env.example` documents each one. The ones worth knowing:

| Variable | Default | What it controls |
|----------|---------|------------------|
| `GROQ_API_KEY` | *(unset)* | Cloud inference. Missing or rate-limited, the router falls back to Ollama rather than failing the scan |
| `AUTHORISED_SCAN_TARGETS` | *(empty)* | Hosts whose ports may be probed. Empty means no host is port scanned |
| `ALLOW_PRIVATE_TARGETS` | `false` | Allows scanning localhost and private IPs. Also authorises them for port scanning |
| `SCAN_INCLUDE_TESTS` | `false` | Include findings from test directories. Off by default: test code is unsafe by design, and the excluded count is always logged |
| `MAX_PATCH_TARGETS` | `10` | Patch generation is one LLM call per finding, so it is capped |
| `MAX_ENRICHED_FINDINGS` | `25` | How many findings fit one enrichment prompt. The rest are still reported, with the scanner's own severity |
| `SEMGREP_RULES_PATH` | *(unset)* | Local rule checkout. Without it Semgrep uses `--config auto`, which needs network access |
| `OLLAMA_NUM_CTX` | `8192` | Ollama's own default of 2048 truncates the JSON answer mid-string on a grounded prompt |

### Offline / Ollama fallback (optional)

SentinelAI works fully offline using a local Ollama model. No internet or API key required.

```bash
# 1 - Install Ollama
#     macOS:   brew install ollama
#     Linux:   curl -fsSL https://ollama.com/install.sh | sh
#     Windows: download from https://ollama.com/download

# 2 - Pull a model (one-time download)
ollama pull llama3          # 4.7 GB - recommended
# ollama pull mistral       # 4.4 GB - good alternative
# ollama pull phi3          # 2.3 GB - lighter, faster

# 3 - Ollama runs as a background service on port 11434 automatically
#     No extra config needed - SentinelAI detects it automatically.
```

Add to `backend/.env` if you want to customise the model:

```env
OLLAMA_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

**How the fallback works:**

| Situation | Active LLM | Agent feed shows |
|-----------|-----------|-----------------|
| Groq working normally | Groq · Llama 3.3 70B | `LLM: Groq / llama-3.3-70b-versatile` |
| Groq rate-limited (429) | Ollama · llama3 | `LLM: Ollama / llama3 (offline)` |
| No internet at all | Ollama · llama3 | `LLM: Ollama / llama3 (offline)` |
| Groq recovers after 30 min | Groq (auto-retry) | `LLM: Groq / llama-3.3-70b-versatile` |

The switch is automatic - no restart needed. The active model is logged in the agent feed at the start of every scan.

### 2 - Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

For a deployed frontend, point it at your backend:

```env
# frontend/.env.production
NEXT_PUBLIC_API_URL=https://api.your-domain.com
NEXT_PUBLIC_WS_URL=wss://api.your-domain.com
```

### Production deployment

Set `ENV=production` in `backend/.env` - `run.sh` then runs uvicorn without
auto-reload and with `WORKERS` worker processes. Key hardening knobs
(all in `backend/.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | CORS allow-list for the frontend |
| `MAX_CONCURRENT_SCANS` | `3` | Scans beyond this get HTTP 429 |
| `SCAN_TIMEOUT_SECS` | `600` | Hard kill for a stuck scan pipeline |
| `ANALYSIS_TIMEOUT_SECS` | `300` | Hard kill for a stuck exam analysis |
| `SESSION_TTL_SECS` | `86400` | Finished scans/sessions purged from memory after this |
| `ALLOW_PRIVATE_TARGETS` | `false` | SSRF guard - private/loopback/metadata IPs are blocked unless explicitly enabled for lab use |

Notes:
- Scan targets are DNS-resolved and rejected if they point at private,
  loopback, link-local, or cloud-metadata addresses (SSRF protection).
- Cloned repos are deleted from the temp dir as soon as a scan finishes.
- State is in-process memory: run a single backend instance (`WORKERS=1`)
  unless you move scan/session state to Redis or a database - with multiple
  workers, WebSocket connections may land on a worker that doesn't hold the
  session.

---

## How It Works

### VulnSentinel - 6-Agent Pipeline (GitHub + Website)

VulnSentinel accepts two target types - auto-detected from the URL:

| Target | Scanner used |
|--------|-------------|
| `github.com/owner/repo` | Clone → Semgrep + Bandit static analysis |
| Any website URL | HTTP security checks (headers, SSL, cookies, exposed files, CORS) |

```
User pastes GitHub repo URL or website URL
        │
   [Orchestrator]  Auto-detects target type · plans scan strategy with LLM
        │
   [Scanner]       GitHub → clone + Semgrep + Bandit
                   Website → security headers · SSL cert · cookie flags ·
                             exposed files (/.env, /.git, /wp-config…) ·
                             CORS · server info disclosure
        │
   [Vuln Analyzer]     Enriches findings with OWASP + CVE context.
                       Cannot add, drop or re-rate what the scanner found
        │
   [Exploit Reasoner]  Explains how each HIGH/CRITICAL vuln can be exploited in the real world.
                       Every target is accounted for, from OWASP data if the model fails
        │
   [Fix Suggester]     Code patches diffed against the real file, or HTTP remediation config.
                       States the platform limit when the host cannot apply the fix
        │
   [Report Generator]  Executive summary · calculated risk score · full JSON report
        │
   Results streamed live to the browser via WebSocket
```

#### Website scanner checks

| Check | What it finds | How it avoids false positives |
|-------|--------------|-------------------------------|
| Security headers | Missing CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy | A CSP or Referrer-Policy in a `<meta>` tag counts as applied. A report-only CSP is reported as unenforced, not missing. HSTS is skipped on plain HTTP, where browsers ignore it |
| Transport security | HTTP instead of HTTPS · HSTS max-age too short · SSL cert expiry | Graded on the URL actually served, so a site that redirects to HTTPS is not called unencrypted |
| Cookie security | Missing `Secure`, `HttpOnly`, `SameSite` | Graded per attribute: missing `Secure` on HTTPS is MEDIUM, an absent `SameSite` is LOW because browsers default it to Lax |
| CORS | Wildcard `Access-Control-Allow-Origin: *` | HIGH only with credentials, MEDIUM when the response sets cookies, otherwise LOW - a wildcard on public content discloses nothing |
| Dangerous methods | TRACE, PUT, DELETE enabled | Read from the `Allow` header |
| Sensitive file exposure | `/.env`, `/.git/config`, `/wp-config.php`, `/phpinfo.php`, `/phpmyadmin`, backup SQL files, Swagger UI | Each path has a body-signature validator, and a soft-404 baseline is captured first, so a catch-all 200 is not a finding |
| Modern exposures | Prometheus `/metrics`, Spring Boot `/actuator` and `/actuator/env`, Go `/debug/pprof`, Laravel Telescope, Symfony profiler, `.svn` metadata | Same signature validation |
| Browsable directories | Open listings at `/ftp`, `/files`, `/uploads`, `/backup` | Recognised by the markers Apache, nginx, Express `serve-index`, Python `http.server` and IIS emit |
| Info disclosure | `Server` and `X-Powered-By` revealing stack details | Only a version is reported: every site sends a `Server` header, and "nginx" alone maps to no CVE |
| Anti-bot detection | Challenge and block pages (HTTP 999, `cf-mitigated`, DataDome, Incapsula) | The scan stops and reports the block instead of grading a page real users never see |

### Port Scanner - CVE/CWE Mapping

> **Authorised targets only.** Reading a website's headers is what any browser does. Connecting to 25 of its ports is not, and against a host you do not control it is unauthorised testing. Ports are therefore probed only against hosts listed in `AUTHORISED_SCAN_TARGETS`, and **nothing is authorised by default**. HTTP checks always run, so declining to port scan never costs the assessment. Authorisation is checked against the host that actually served the response, so a redirect cannot carry the scan onto a third party.
>
> ```bash
> AUTHORISED_SCAN_TARGETS=staging.example.com,*.internal.example.com
> ```
>
> Exact match, with `*.` for subdomains. `*.example.com` covers `api.example.com` but not `example.com` itself. Loopback and private addresses follow the existing `ALLOW_PRIVATE_TARGETS` flag.

When an authorised website URL is scanned, VulnSentinel also performs a parallel port scan across 25 common ports. Each open port is matched against a built-in risk database - no external API calls needed.

| Port | Service | Severity | Key CVEs |
|------|---------|----------|---------|
| 445 | SMB | CRITICAL | CVE-2017-0144 EternalBlue, CVE-2020-0796 SMBGhost |
| 3389 | RDP | CRITICAL | CVE-2019-0708 BlueKeep, CVE-2019-1182 DejaBlue |
| 6379 | Redis | CRITICAL | CVE-2022-0543 Lua RCE - no auth by default |
| 9200 | Elasticsearch | CRITICAL | CVE-2014-3120 RCE - no auth by default |
| 27017 | MongoDB | CRITICAL | CVE-2013-4650 - no auth by default |
| 3306 | MySQL | CRITICAL | CVE-2012-2122 auth bypass |
| 5432 | PostgreSQL | CRITICAL | CVE-2019-9193 RCE via COPY |
| 23 | Telnet | CRITICAL | Cleartext credentials (CWE-319) |
| 21 | FTP | HIGH | CVE-2010-4221, cleartext transfer |
| 22 | SSH | MEDIUM | CVE-2024-6387 regreSSHion |

Each open port appears as a VulnCard in the findings panel showing: port badge, all CVEs, CWE chips, and a fix recommendation.

### ExamGuard - Two-Phase System

**Phase 1 - Real-time (during exam)**
```
Browser detects event (tab switch / face absent / phone in frame / copy-paste)
        │
   WebSocket → event_rules.py
        │
   Rule threshold crossed? → immediate_alert fanned out to invigilator monitor instantly
        │
   Tab switches reach 5? → exam auto-terminated, student sees "Exam Terminated" screen
```

**Phase 2 - Deep analysis (after exam ends)**
```
POST /api/exam/{id}/analyze
        │
   [Session Monitor]    Validates session · computes statistics
        │
   [Behavior Analyzer]  LLM identifies suspicious patterns across the full event log
        │
   [Anomaly Scorer]     Scores each category 0-100 for suspicion level
        │
   [Alert Generator]    Produces prioritised, actionable alerts for the invigilator
        │
   [Report Generator]   Integrity score + CLEAN / SUSPICIOUS / FLAGGED verdict + narrative
        │
   Streamed live to invigilator dashboard via WebSocket
```

### Real-time Alert Thresholds (ExamGuard)

| Trigger | Threshold | Severity |
|---------|-----------|----------|
| Tab switches | 3× | WARNING |
| Tab switches | 5× | CRITICAL + **exam auto-terminated** |
| Face absent | 10 s continuous | WARNING |
| Face absent | 30 s continuous | CRITICAL |
| Multiple faces detected | 2 faces | WARNING |
| Multiple faces detected | 3+ faces | CRITICAL |
| Mobile phone in camera | 1st detection | WARNING |
| Mobile phone in camera | 2nd+ detection | CRITICAL |
| Copy-paste events | 2× | WARNING |
| Copy-paste events | 5× | CRITICAL |

### Mobile Phone Detection

The webcam feed is analysed every 3 seconds using two parallel in-browser ML models:

| Model | Purpose | Size |
|-------|---------|------|
| `@vladmandic/face-api` TinyFaceDetector | Face counting & presence | ~190 KB |
| `@tensorflow-models/coco-ssd` MobileNet V2 | Object detection - "cell phone" class | ~3 MB |

Both models run entirely client-side (WebGL) with no cloud API calls. When a phone is detected:
- A red **📱 PHONE** badge flashes on the camera overlay in the student view
- A `phone_detected` WebSocket event is sent to the backend
- The backend fans out an immediate alert to the invigilator monitor
- The "Phone Detected" counter increments in the Activity Stats panel

---

## WebSocket Message Protocol

### VulnSentinel (`/ws/{scan_id}`)
```jsonc
// Server → Client
{ "type": "update", "node": "vuln_analyzer", "logs": ["..."], "status": "exploiting", "scan_id": "a1b2c3" }
{ "type": "done",   "scan_id": "a1b2c3", "report": { ... } }
{ "type": "error",  "scan_id": "a1b2c3", "message": "..." }
{ "type": "ping" }
```

### ExamGuard event socket (`/ws/exam/{exam_id}`)
```jsonc
// Client → Server
{ "type": "tab_event",       "event_type": "blur",    "timestamp": 1234567890.0 }
{ "type": "face_event",      "face_count": 0,          "confidence": 0.95, "timestamp": 1234567890.0 }
{ "type": "phone_detected",  "confidence": 0.87,       "timestamp": 1234567890.0 }
{ "type": "keystroke_stats", "avg_wpm": 67,             "pause_count": 1, ... }
{ "type": "copy_paste",      "content_length": 342,    "timestamp": 1234567890.0 }
{ "type": "end_exam",        "timestamp": 1234567890.0 }

// Server → Client
{ "type": "immediate_alert", "severity": "CRITICAL", "title": "Mobile Phone Detected", "message": "...", "recommended_action": "..." }
{ "type": "exam_ended" }
```

### ExamGuard monitor socket (`/ws/exam/{exam_id}/monitor`)
```jsonc
// Server → Client  (fan-out of all immediate alerts + exam lifecycle events)
{ "type": "immediate_alert", "severity": "WARNING", "title": "...", "message": "...", "recommended_action": "..." }
{ "type": "exam_ended",      "exam_id": "a1b2c3" }
```

---

## API Reference

### VulnSentinel

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/scan` | Start a scan · returns `scan_id` + `ws_url` |
| `WS` | `/ws/{scan_id}` | Stream real-time agent progress |
| `GET` | `/api/report/{scan_id}` | Fetch completed report |
| `GET` | `/api/scans` | List all scans |

### Retention

Every destructive endpoint returns a receipt: one result per store, plus a single
outcome of `complete`, `partial`, `blocked` or `unresolved`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/retention/policy` | Schedule, state counts, ledger health |
| `GET` | `/api/retention/scans` | Inventory with state, hold and next due action |
| `POST` | `/api/retention/scans/{id}/archive` | Offload findings to the cold archive |
| `POST` | `/api/retention/scans/{id}/restore` | Undo a delete, rehydrate an archive |
| `POST` | `/api/retention/scans/{id}/trash` | Reversible delete |
| `POST` | `/api/retention/scans/{id}/purge` | Irreversible erasure · `?mode=full\|payload` |
| `POST` | `/api/retention/scans/{id}/hold` | Legal hold · blocks every destructive step |
| `DELETE` | `/api/retention/scans/{id}/hold` | Release the hold |
| `GET` | `/api/retention/scans/{id}/verify` | Re-check every store for residue |
| `POST` | `/api/retention/sweep` | Apply the policy · `?dry_run` `?as_of` |
| `GET` | `/api/retention/audit` | Hash-chained ledger of every operation |

`DELETE /api/scans/history/{id}` now routes into the lifecycle as a reversible
delete and returns a receipt rather than a bare `204`.

### ExamGuard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/exam/session` | Create exam session · returns `exam_id` |
| `GET` | `/api/exam/session/{exam_id}` | Fetch session info (duration, student name, status) |
| `WS` | `/ws/exam/{exam_id}` | Bidirectional student event stream |
| `WS` | `/ws/exam/{exam_id}/monitor` | Invigilator fan-out stream (alerts + exam lifecycle) |
| `POST` | `/api/exam/{exam_id}/analyze` | Trigger post-session LangGraph analysis |
| `WS` | `/ws/exam/{exam_id}/analysis` | Stream analysis agent progress |
| `GET` | `/api/exam/report/{exam_id}` | Fetch integrity report |
| `GET` | `/api/exam/sessions` | List all sessions |

---

## Testing & CI

```bash
cd backend && pytest          # 332 tests
ruff check .                  # lint
```

Most of the suite is regression tests written from real incidents: a scan that reported a repository clean because the model prefixed its JSON with a sentence of prose, a HIGH "missing CSP" against a site with one of the strictest policies on the web, a patch that quoted a line of code which was not in the file. Each one is now a named test explaining what went wrong.

Every push and pull request runs six jobs:

| Job | What it gates |
|-----|---------------|
| Backend (3.11, 3.12) | `ruff` correctness rules and the full pytest suite |
| Frontend build | `tsc --noEmit` and a production Next.js build |
| Security self-scan | Bandit at MEDIUM and above, blocking. A security tool that ships insecure code is not credible |
| Dependency audit | `npm audit` and `pip-audit`, advisory |
| API smoke test | Boots the API with **no** API key and asserts `/health` - a missing key must degrade to the local model, not crash |
| Release version consistency | Tags only: the tag must match `backend/main.py`, `package.json` and the lockfile |

Tags matching `v*` build the same pipeline, so every release has a verified build behind it.

---

## FAQ

**Isn't this just a wrapper around an LLM?**
The model cannot add a finding, remove one, change a severity, or set the risk score. It explains attack vectors, maps findings to OWASP and CVE, and writes the prose. If it fails completely, every finding is still reported at the scanner's own severity and the log says enrichment was unavailable. A model failure costs you the explanation, never a vulnerability.

**How do I know the risk score isn't invented?**
It is printed as arithmetic in the agent log - the per-severity contributions and the floor that produced it - and stored in the report as `summary.risk_breakdown`. The same findings give the same number on Groq or on a local Ollama model. Rescan and check.

**You scanned OWASP Juice Shop and didn't find its SQL injection.**
Correct, and deliberate. Website mode is a passive configuration and exposure audit: it reads headers, cookies, TLS and known paths, and never sends an attack payload. Code-level vulnerabilities are the repository scanner's job, through Semgrep and Bandit. Active application testing is on the roadmap, for authorised targets only.

**What stops someone pointing this at a site they don't own?**
Port scanning refuses unless the host is listed in `AUTHORISED_SCAN_TARGETS`, which is empty by default, and the refusal is written into the scan log. The check runs against the host that actually answered, so a redirect cannot carry the scan onto a third party. HTTP checks are ordinary requests, the same ones a browser makes.

**What happens if the API key is missing, rate-limited, or the internet is down?**
The router falls back to a local Ollama model. A CI job boots the API with no key at all and asserts `/health` still answers, because a missing key used to crash every scan.

**Why did my scan return no findings at all?**
Three cases are reported rather than scored: the target refused automated scanning (a bot challenge), the target returned a server error, or it could not be reached. In each case the log says no assessment was performed. That is not the same as a clean result, and the tool does not present it as one.

**Are the findings comparable between scans?**
Yes, and that is the point. The score is a function of the findings, the findings come from deterministic checks, and history pages plot the score over time so a fix shows up as a drop.

---

## Team

**Team Zen Hackers** - FAR AWAY 2026

| Name | Role |
|------|------|
| Saee Nikam | Team Lead |
| Pushpender Singh | Backend · Agent Pipelines |
| Vaibhav Haval | Frontend · UI/UX |
| Shreya Magadum | ML · Integration |
| Sonika Kaswan | QA · Presentation |

---

## License

MIT - built for FAR AWAY 2026. Not for production use without security review.
