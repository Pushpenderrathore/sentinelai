# SentinelAI - Presentation Outline
### FAR AWAY 2026 · 15 Slides · Theme: Agentic & Autonomous Systems

---

## Slide-by-slide breakdown

---

### Slide 1 - Cover
**Visual:** Full-bleed dark background. SentinelAI logo centred. Subtle animated grid or circuit lines behind it.

**Content:**
```
SentinelAI
Autonomous Threat Detection - for Code & Exams

Team Zen Hackers · FAR AWAY 2026
```

**Speaker note:** Don't read the slide. Open with: *"Two problems. One autonomous engine. We'll show you both running live today."*

---

### Slide 2 - The Problem (Hook)
**Visual:** Two stark statistics, side by side. Large numbers, minimal text.

```
LEFT                              RIGHT
84%                               53%
of software releases              of online exam platforms
ship with at least one            have no reliable way to
known vulnerability               detect AI-assisted cheating

         Both go undetected until it's too late.
```

**Key message:** These aren't edge cases - they're the norm. Human review doesn't scale.

**Speaker note:** *"Security audits cost ₹10-50 lakh per engagement. Universities run thousands of exams a year with no tools to verify integrity. Both problems share a root cause - detection at scale requires intelligence, not just rules."*

---

### Slide 3 - The Insight
**Visual:** Single bold sentence centred on the slide. Nothing else.

```
Both problems are the same problem:

    detecting threats autonomously,
    without a human in the loop.
```

**Key message:** This is why one platform solves both. Agentic systems generalise.

---

### Slide 4 - Solution Overview
**Visual:** Two-panel card layout (dark theme matching the app).

```
┌─────────────────────┐    ┌─────────────────────┐
│  🔍 VulnSentinel    │    │  🎓 ExamGuard        │
│                     │    │                     │
│  Paste a GitHub URL │    │  Start an exam      │
│  ↓                  │    │  ↓                  │
│  5 AI agents audit  │    │  AI monitors in     │
│  your codebase      │    │  real time          │
│  ↓                  │    │  ↓                  │
│  CVEs · OWASP · patches  │  instant alerts + AI report
└─────────────────────┘    └─────────────────────┘

        Same LangGraph agent engine. Two domains.
```

---

### Slide 5 - LIVE DEMO 1: VulnSentinel
**Visual:** Actual running app - switch to browser here. If slides-only, use a high-quality screen recording GIF embedded.

**What to show:**
1. Paste `https://github.com/[vulnerable-demo-repo]` into the scan input
2. Watch the terminal-style agent feed light up in real time
3. Point out each agent activating: Orchestrator → Scanner → Vuln Analyzer → Exploit Reasoner → Fix Suggester → Report
4. Show a CRITICAL vulnerability card appearing with the patch diff

**One-liner caption at the bottom:**
```
Repo → 6 autonomous agents → CVEs + patches  ·  No human required
```

**Speaker note:** *"This is not a mock. This is scanning a real repository right now."*

---

### Slide 6 - How VulnSentinel Works
**Visual:** Horizontal pipeline with agent icons. Each agent has a label and one-line job description.

```
GitHub URL
    │
    ▼
🧠 Orchestrator     "Plans scan strategy via LLM reasoning"
    │
    ▼
🔍 Scanner          "Clones repo · runs Semgrep + Bandit"
    │
    ▼
⚠️  Vuln Analyzer   "Maps to OWASP Top 10 + CVEs"
    │
    ▼
💀 Exploit Reasoner "Explains real-world attack vectors"
    │
    ▼
🔧 Fix Suggester    "Generates code patches"
    │
    ▼
📄 Report Generator "Risk score · executive summary · PDF"
```

**Key message:** Each agent has a single responsibility. LangGraph routes the state between them with conditional edges - if no vulnerabilities are found, it skips directly to the report.

---

### Slide 7 - LIVE DEMO 2: ExamGuard
**Visual:** Two browser windows side by side (or recording).

**What to show:**
1. Left window: Student exam page - clean white UI, timer running, webcam thumbnail visible
2. Right window: Invigilator dashboard - dark UI, integrity score at 100
3. In the student window: switch to another tab → come back
4. In the invigilator window: WARNING alert fires instantly, score drops
5. Submit exam → click "Run Analysis" → watch the 5 LangGraph agents stream through the middle pane
6. Final verdict: SUSPICIOUS · integrity score: 72/100

**One-liner caption:**
```
Tab switch → instant alert in < 200 ms  ·  No human watching required
```

---

### Slide 8 - How ExamGuard Works
**Visual:** Two-row diagram - real-time layer on top, analysis layer below.

```
LAYER 1 - Real-time (during exam)
─────────────────────────────────────────────────────────
Browser events → WebSocket → Rule engine → Instant alert
  tab switch           ↑ no LLM         → invigilator
  face absent          fires in <200ms
  copy-paste

LAYER 2 - Deep analysis (after exam)
─────────────────────────────────────────────────────────
Session logs → LangGraph pipeline → Integrity report

  👁️  Session Monitor    "Validates & summarises event log"
  🔬 Behavior Analyzer  "LLM finds patterns across full session"
  📊 Anomaly Scorer     "Scores each category 0-100"
  🚨 Alert Generator    "Prioritised action items for invigilator"
  📄 Report Generator   "Verdict: CLEAN / SUSPICIOUS / FLAGGED"
```

**Key message:** The two-layer design is deliberate - rules fire instantly, LLM runs deep analysis. Best of both worlds.

---

### Slide 9 - Why This Is Truly Agentic
**Visual:** Side-by-side comparison table.

```
                    API Wrapper        SentinelAI
                    ───────────        ──────────
Decision-making     One LLM call       Agents reason + route
Tool use            None               Semgrep, Bandit, Git, APIs
Memory              Stateless          LangGraph state flows
Conditional logic   Hardcoded          Graph edges adapt to findings
Parallelism         No                 Agents run where possible
Fallback paths      No                 Scanner error → skip to report
```

**Key message:** Judges specifically called out "minimal-effort AI wrappers" as what they don't want. This is not that.

---

### Slide 10 - Technical Depth
**Visual:** Three highlight callouts with short code snippets or diagrams.

```
1. Conditional Routing
   If scanner finds 0 results → skip directly to report_generator
   If vuln_analyzer finds 0 vulns → skip exploit_reasoner
   Graph adapts at runtime. Not hardcoded if-else.

2. Bidirectional WebSocket
   Browser → server: { type: "tab_event", timestamp: ... }
   Server → browser: { type: "immediate_alert", severity: "CRITICAL" }
   Rule engine evaluates in-memory. Zero LLM latency for alerts.

3. Structured LLM outputs
   Every agent returns a validated TypedDict.
   JSON parse failures fall back gracefully - scan never crashes.
```

---

### Slide 11 - Real-World Impact
**Visual:** Three impact cards with icons and numbers.

```
┌───────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│  ₹10-50 lakh      │  │  < 5 minutes       │  │  10 crore+       │
│                   │  │                    │  │                  │
│  Typical security │  │  SentinelAI scans  │  │  Students taking │
│  audit cost       │  │  a full repo end-  │  │  online exams in │
│  per engagement   │  │  to-end            │  │  India per year  │
└───────────────────┘  └────────────────────┘  └──────────────────┘

SentinelAI makes enterprise-grade security & proctoring
accessible to any developer and any institution.
```

---

### Slide 12 - Tech Stack
**Visual:** Clean logo grid, no walls of text.

```
Agent Framework    LangGraph          (stateful multi-agent graphs)
LLM                Claude claude-sonnet-4-6      (Anthropic API)
Backend            FastAPI + Python 3.11
Static Analysis    Semgrep · Bandit
Real-time          WebSocket (native browser API)
Frontend           Next.js 14 · TypeScript · Tailwind CSS
Version Control    GitHub (private repo)
```

---

### Slide 13 - What We'd Build Next
**Visual:** Roadmap with 3 phases. Keep it grounded - judges are skeptical of vague futures.

```
Next 30 days (engineering, not ideas)
───────────────────────────────────
☐ face-api.js real face detection (model files ready, hook in place)
☐ PDF report export (WeasyPrint already in requirements.txt)
☐ GitHub Actions integration - scan on every PR automatically
☐ Multi-student exam dashboard (invigilator sees all students at once)

Next 6 months
───────────────────────────────────
☐ Semgrep custom rule editor for organisation-specific policies
☐ Audio anomaly detection (phone calls, whispering)
☐ LMS integration (Moodle, Canvas API)
```

**Key message:** Future scope is specific and buildable - not a wish list.

---

### Slide 14 - Team
**Visual:** Five cards, photo placeholder, name, role, one-line skill.

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Saee Nikam  │ │  Pushpender  │ │   Vaibhav    │ │   Shreya     │ │   Sonika     │
│              │ │    Singh     │ │    Haval     │ │  Magadum     │ │   Kaswan     │
│  Team Lead   │ │  Backend &   │ │  Frontend &  │ │  ML &        │ │  QA &        │
│  Strategy    │ │  AI Agents   │ │  UI/UX       │ │  Integration │ │  Presentation│
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

                          Team Zen Hackers
```

---

### Slide 15 - Closing
**Visual:** Dark full-bleed. Minimal. GitHub link + QR code on the right. App URL on the left.

```
             SentinelAI

    github.com/Pushpenderrathore/sentinelai

    ┌─────┐
    │ QR  │   Scan to see the live repo
    └─────┘

    "The goal is not to write every line of code yourself.
     The goal is to build something meaningful."
                                    - FAR AWAY 2026 philosophy
```

**Speaker note:** *"We built both modules, end-to-end, in 7 days. The code is on GitHub. The agents are running. Thank you."*

---

## Slide Design Rules

| Rule | Why |
|------|-----|
| Dark background (`#0a0a0f`) throughout | Matches the app, looks premium |
| Max 30 words of body text per slide | Judges are reading fast |
| Every demo slide has the app running live, not a screenshot | Rules say "fake demos" are disqualifying |
| No bullet walls - use tables, diagrams, code blocks | Judges see 100+ decks; visual stands out |
| Consistent font: bold display font for headlines, mono for code | Matches the terminal aesthetic of the product |
| Include the Anthropic/LangGraph logos in the tech stack slide | Shows you're using real infrastructure |

---

## Suggested Slide Software

- **Figma Slides** - best for the dark theme + custom layout
- **Canva** - faster to produce, good templates
- **Google Slides** - easiest for team collaboration

Use the same color palette as the app:
```
Background  #0a0a0f
Surface     #111118
Border      #1e1e2e
Accent 1    #00d4ff  (cyan - VulnSentinel)
Accent 2    #a855f7  (purple - ExamGuard)
Success     #00ff88  (green - clean/safe)
Danger      #ff3366  (red - critical)
Text        #e2e8f0
```

---

## Timing (15-minute slot assumed)

| Segment | Time |
|---------|------|
| Slides 1-4 (problem + solution) | 3 min |
| Slide 5 - VulnSentinel live demo | 3 min |
| Slides 6-8 (architecture) | 3 min |
| Slide 7 - ExamGuard live demo | 3 min |
| Slides 9-15 (depth + team + close) | 3 min |
