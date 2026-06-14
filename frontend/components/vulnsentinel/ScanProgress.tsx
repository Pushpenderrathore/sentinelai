"use client"

import { useEffect, useRef, useState, useCallback } from "react"

// ─── Types ────────────────────────────────────────────────────────────────────

type AgentStatus = "pending" | "running" | "done" | "error"

interface AgentState {
  key: string
  label: string
  description: string
  status: AgentStatus
  message: string
  progress: number
}

interface SSEEvent {
  agent: string
  status: "running" | "done" | "error"
  message: string
  progress: number
}

interface ScanProgressProps {
  scanId: string
  onComplete?: () => void
  onRetry?: () => void
}

// ─── Constants ────────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

const AGENT_PIPELINE: { key: string; label: string; description: string }[] = [
  { key: "orchestrator",     label: "Orchestrator",     description: "Plans scan strategy" },
  { key: "scanner_agent",    label: "Scanner Agent",    description: "Clones repo · runs Semgrep + Bandit" },
  { key: "vuln_analyzer",    label: "Vuln Analyzer",    description: "Maps findings to OWASP & CVEs" },
  { key: "exploit_reasoner", label: "Exploit Reasoner", description: "Assesses real-world exploitability" },
  { key: "fix_suggester",    label: "Fix Suggester",    description: "Generates code patches" },
]

// ─── Sub-components ───────────────────────────────────────────────────────────

function SpinnerRing() {
  return (
    <svg
      className="w-6 h-6 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle
        cx="12" cy="12" r="9"
        stroke="#1e1e2e"
        strokeWidth="3"
      />
      <path
        d="M12 3a9 9 0 0 1 9 9"
        stroke="#00d4ff"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}

function CheckCircle() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" fill="#00d4ff" />
      <path
        d="M7 12.5l3.5 3.5 6.5-7"
        stroke="#0d1117"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function ErrorCircle() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" fill="#ff3366" />
      <path
        d="M8 8l8 8M16 8l-8 8"
        stroke="#0d1117"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

function PendingCircle() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="#2a2a3a" strokeWidth="2" />
    </svg>
  )
}

function StepIcon({ status }: { status: AgentStatus }) {
  switch (status) {
    case "running": return <SpinnerRing />
    case "done":    return <CheckCircle />
    case "error":   return <ErrorCircle />
    default:        return <PendingCircle />
  }
}

function AgentRow({ agent, isLast }: { agent: AgentState; isLast: boolean }) {
  const isRunning = agent.status === "running"
  const isDone    = agent.status === "done"
  const isError   = agent.status === "error"
  const isPending = agent.status === "pending"

  return (
    <div className="relative flex gap-4">
      {/* Vertical connector line */}
      {!isLast && (
        <div
          className="absolute left-3 top-7 w-px h-full -translate-x-px"
          style={{
            background: isDone
              ? "linear-gradient(to bottom, #00d4ff55, #00d4ff22)"
              : "#1e1e2e",
            transition: "background 0.6s ease",
          }}
        />
      )}

      {/* Icon column */}
      <div className="relative z-10 shrink-0 pt-0.5">
        <StepIcon status={agent.status} />
      </div>

      {/* Content column */}
      <div
        className="flex-1 pb-7 min-w-0"
        style={{
          transition: "opacity 0.3s ease",
          opacity: isPending ? 0.45 : 1,
        }}
      >
        {/* Row background pulse when running */}
        <div
          className="rounded-lg px-3 py-2 -mx-3 transition-all duration-500"
          style={{
            background: isRunning
              ? "rgba(0, 212, 255, 0.05)"
              : "transparent",
            boxShadow: isRunning
              ? "0 0 0 1px rgba(0, 212, 255, 0.15)"
              : "none",
          }}
        >
          {/* Agent name + description */}
          <div className="flex items-baseline gap-2 flex-wrap">
            <span
              className="font-mono text-sm font-semibold transition-colors duration-300"
              style={{
                color: isRunning ? "#ffffff"
                     : isDone    ? "#cbd5e1"
                     : isError   ? "#ff3366"
                     : "#64748b",
              }}
            >
              {agent.label}
            </span>
            <span
              className="text-xs transition-colors duration-300"
              style={{ color: isError ? "#ff336688" : "#64748b" }}
            >
              {agent.description}
            </span>

            {/* Live progress badge */}
            {isRunning && agent.progress > 0 && (
              <span
                className="ml-auto text-xs font-mono tabular-nums"
                style={{ color: "#00d4ff99" }}
              >
                {agent.progress}%
              </span>
            )}
          </div>

          {/* Live message */}
          {(isRunning || isError) && agent.message && (
            <div
              className="mt-1.5 font-mono text-[11px] leading-relaxed break-all"
              style={{
                color: isError ? "#ff336699" : "#00d4ff88",
                animation: isRunning ? "fadeIn 0.3s ease-out" : undefined,
              }}
            >
              <span style={{ color: isRunning ? "#00d4ff44" : "#ff336644" }}>
                {isRunning ? "▶ " : "✕ "}
              </span>
              {agent.message}
            </div>
          )}

          {/* Done message (last one) */}
          {isDone && agent.message && (
            <div
              className="mt-1 font-mono text-[11px]"
              style={{ color: "#00d4ff55" }}
            >
              ✓ {agent.message}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ScanProgress({ scanId, onComplete, onRetry }: ScanProgressProps) {
  const [agents, setAgents] = useState<AgentState[]>(
    AGENT_PIPELINE.map((a) => ({ ...a, status: "pending", message: "", progress: 0 }))
  )
  const [overallProgress, setOverallProgress] = useState(0)
  const [errorBanner, setErrorBanner]         = useState<string | null>(null)
  const [allDone, setAllDone]                 = useState(false)
  const [connectionState, setConnectionState] = useState<"connecting" | "live" | "closed" | "error">("connecting")

  const esRef           = useRef<EventSource | null>(null)
  const reconnectTimer  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectCount  = useRef(0)
  const isMounted       = useRef(true)
  const resultsRef      = useRef<HTMLDivElement | null>(null)

  // Stable ref so callbacks don't go stale
  const agentsRef = useRef(agents)
  agentsRef.current = agents

  // ── SSE connection ──────────────────────────────────────────

  const connect = useCallback(() => {
    if (!isMounted.current) return

    // Close any existing connection
    esRef.current?.close()

    const url = `${API_BASE}/api/scan/progress?id=${encodeURIComponent(scanId)}`
    const es = new EventSource(url)
    esRef.current = es
    setConnectionState("connecting")

    es.onopen = () => {
      if (!isMounted.current) return
      reconnectCount.current = 0
      setConnectionState("live")
    }

    es.onmessage = (e: MessageEvent) => {
      if (!isMounted.current) return
      try {
        const event: SSEEvent = JSON.parse(e.data)
        handleEvent(event)
      } catch {
        // non-JSON heartbeat — ignore
      }
    }

    es.onerror = () => {
      if (!isMounted.current) return
      es.close()

      // Don't reconnect if scan finished
      if (allDoneRef.current) {
        setConnectionState("closed")
        return
      }

      setConnectionState("error")

      // Exponential backoff: 2s, 4s, 8s, 16s, cap at 30s
      const delay = Math.min(2000 * Math.pow(2, reconnectCount.current), 30_000)
      reconnectCount.current += 1

      reconnectTimer.current = setTimeout(() => {
        if (isMounted.current && !allDoneRef.current) connect()
      }, delay)
    }
  }, [scanId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Need a ref to `allDone` inside the closure without re-creating `connect`
  const allDoneRef = useRef(false)
  allDoneRef.current = allDone

  const handleEvent = useCallback((event: SSEEvent) => {
    setAgents((prev) => {
      const next = prev.map((a) => {
        if (a.key !== event.agent) return a
        return {
          ...a,
          status:   event.status,
          message:  event.message ?? a.message,
          progress: event.progress ?? a.progress,
        }
      })

      // Recompute overall progress from per-agent progress values
      const total = next.reduce((sum, a) => {
        if (a.status === "done")    return sum + 100
        if (a.status === "running") return sum + (a.progress ?? 0)
        return sum
      }, 0)
      const computed = Math.round(total / next.length)
      setOverallProgress(computed)

      // Check if all done or any errored
      const anyError = next.some((a) => a.status === "error")
      const allComplete = next.every((a) => a.status === "done")

      if (anyError && event.status === "error") {
        setErrorBanner(event.message || "An agent encountered an error.")
        esRef.current?.close()
        setConnectionState("closed")
      }

      if (allComplete) {
        setOverallProgress(100)
        setAllDone(true)
        allDoneRef.current = true
        esRef.current?.close()
        setConnectionState("closed")
      }

      return next
    })
  }, [])

  // ── Auto-scroll on completion ───────────────────────────────

  useEffect(() => {
    if (!allDone) return
    const timer = setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      onComplete?.()
    }, 1500)
    return () => clearTimeout(timer)
  }, [allDone, onComplete])

  // ── Lifecycle ───────────────────────────────────────────────

  useEffect(() => {
    isMounted.current = true
    connect()
    return () => {
      isMounted.current = false
      esRef.current?.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  // ─── Derived display values ─────────────────────────────────

  const doneCount    = agents.filter((a) => a.status === "done").length
  const runningAgent = agents.find((a) => a.status === "running")

  // ─── Render ─────────────────────────────────────────────────

  return (
    <div
      className="w-full rounded-2xl overflow-hidden"
      style={{
        background:  "#0d1117",
        border:      "1px solid #1e1e2e",
        fontFamily:  "'JetBrains Mono', Menlo, Monaco, Consolas, monospace",
      }}
    >
      {/* ── Header ── */}
      <div
        className="flex items-center justify-between px-5 py-3.5"
        style={{ borderBottom: "1px solid #1e1e2e", background: "#0d1117" }}
      >
        <div className="flex items-center gap-2.5">
          {/* macOS traffic lights */}
          <span className="w-3 h-3 rounded-full" style={{ background: "#ff3366" }} />
          <span className="w-3 h-3 rounded-full" style={{ background: "#ffb800" }} />
          <span className="w-3 h-3 rounded-full" style={{ background: "#00ff88" }} />
          <span className="ml-3 text-xs" style={{ color: "#64748b" }}>
            scan-progress
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Live / connecting indicator */}
          <span className="flex items-center gap-1.5 text-xs" style={{ color: "#64748b" }}>
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background: connectionState === "live"       ? "#00ff88"
                          : connectionState === "error"      ? "#ff3366"
                          : connectionState === "connecting" ? "#ffb800"
                          : "#64748b",
                animation: connectionState === "live" ? "pulse 2s infinite" : undefined,
                boxShadow: connectionState === "live" ? "0 0 6px #00ff8888" : undefined,
              }}
            />
            {connectionState === "live"       ? "LIVE"
           : connectionState === "error"      ? "RECONNECTING"
           : connectionState === "connecting" ? "CONNECTING"
           : "CLOSED"}
          </span>

          {/* Step counter */}
          <span className="text-xs font-mono" style={{ color: "#64748b" }}>
            {doneCount}/{AGENT_PIPELINE.length} agents
          </span>
        </div>
      </div>

      {/* ── Overall progress bar ── */}
      <div className="px-5 pt-4 pb-2">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs" style={{ color: "#64748b" }}>
            {allDone
              ? "Scan complete"
              : runningAgent
              ? runningAgent.label
              : "Initialising…"}
          </span>
          <span
            className="text-xs font-mono tabular-nums"
            style={{
              color: allDone ? "#00ff88" : "#00d4ff",
              transition: "color 0.5s",
            }}
          >
            {overallProgress}%
          </span>
        </div>

        {/* Track */}
        <div
          className="w-full rounded-full overflow-hidden"
          style={{ height: "4px", background: "#1e1e2e" }}
        >
          <div
            style={{
              height:     "100%",
              width:      `${overallProgress}%`,
              background: allDone
                ? "linear-gradient(90deg, #00d4ff, #00ff88)"
                : "linear-gradient(90deg, #00d4ff, #0099bb)",
              transition: "width 0.6s cubic-bezier(0.4,0,0.2,1), background 0.5s",
              borderRadius: "9999px",
              boxShadow: overallProgress > 0 ? "0 0 8px rgba(0,212,255,0.5)" : "none",
            }}
          />
        </div>
      </div>

      {/* ── Error banner ── */}
      {errorBanner && (
        <div
          className="mx-5 mt-3 rounded-xl px-4 py-3 flex items-start gap-3"
          style={{
            background: "rgba(255,51,102,0.08)",
            border:     "1px solid rgba(255,51,102,0.25)",
            animation:  "fadeIn 0.3s ease-out",
          }}
        >
          <svg
            className="w-4 h-4 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="none"
            style={{ color: "#ff3366" }}
          >
            <circle cx="10" cy="10" r="9" stroke="currentColor" strokeWidth="1.5" />
            <path d="M10 6v4M10 13.5v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium mb-1" style={{ color: "#ff3366" }}>
              Scan error
            </p>
            <p className="text-xs break-words" style={{ color: "#ff336699" }}>
              {errorBanner}
            </p>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg transition-all duration-150 active:scale-95"
              style={{
                background: "rgba(255,51,102,0.12)",
                border:     "1px solid rgba(255,51,102,0.3)",
                color:      "#ff3366",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,51,102,0.2)"
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,51,102,0.12)"
              }}
            >
              Retry Scan
            </button>
          )}
        </div>
      )}

      {/* ── Agent stepper ── */}
      <div className="px-5 pt-5 pb-2">
        {agents.map((agent, i) => (
          <AgentRow key={agent.key} agent={agent} isLast={i === agents.length - 1} />
        ))}
      </div>

      {/* ── All done banner ── */}
      {allDone && (
        <div
          className="mx-5 mb-5 rounded-xl px-4 py-3 flex items-center gap-3"
          style={{
            background: "rgba(0,255,136,0.06)",
            border:     "1px solid rgba(0,255,136,0.2)",
            animation:  "fadeIn 0.5s ease-out",
          }}
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="9" fill="rgba(0,255,136,0.15)" stroke="#00ff88" strokeWidth="1.5" />
            <path d="M6.5 10.5l2.5 2.5 4.5-5" stroke="#00ff88" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="text-xs" style={{ color: "#00ff88" }}>
            All agents complete · scrolling to results…
          </p>
        </div>
      )}

      {/* Scroll anchor — page integrates results below this */}
      <div ref={resultsRef} />
    </div>
  )
}
