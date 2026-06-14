"use client"

import { useEffect, useMemo, useState } from "react"
import AgentFeed from "@/components/vulnsentinel/AgentFeed"
import VulnCard from "@/components/vulnsentinel/VulnCard"
import { useWebSocket } from "@/lib/ws"

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"

const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
const SEV_COLORS: Record<string, string> = {
  CRITICAL: "text-sentinel-red",
  HIGH:     "text-orange-400",
  MEDIUM:   "text-yellow-400",
  LOW:      "text-blue-400",
}

interface Vuln  { id: string; file: string; line: number; severity: string; category: string; description: string; cve?: string | null }
interface Patch { vuln_id: string; file: string; original_code: string; patched_code: string; explanation: string }
interface Report {
  repo_url: string
  vulnerabilities: Vuln[]
  patches: Patch[]
  summary: { executive_summary: string; risk_score: number; overall_risk: string; key_recommendations: string[] }
}

export default function ScanDashboard({ params }: { params: { id: string } }) {
  const { id: scanId } = params
  const wsUrl = `${WS_BASE}/ws/${scanId}`

  const [logs, setLogs]       = useState<string[]>([])
  const [report, setReport]   = useState<Report | null>(null)
  const [activeNode, setActiveNode] = useState<string>("")

  const { status } = useWebSocket(wsUrl, (msg) => {
    if (msg.type === "update") {
      const newLogs = (msg.logs as string[]) ?? []
      setLogs((prev) => [...prev, ...newLogs])
      setActiveNode(msg.node as string)
    }
    if (msg.type === "done") {
      setReport(msg.report as Report)
      setActiveNode("")
    }
    if (msg.type === "error") {
      setLogs((prev) => [...prev, `[ERROR] ${msg.message as string}`])
      setActiveNode("")
    }
  })

  const isRunning = status === "open" && !report

  const patchMap = useMemo(() => {
    const m: Record<string, Patch> = {}
    report?.patches?.forEach((p) => { m[p.vuln_id] = p })
    return m
  }, [report])

  const sortedVulns = useMemo(
    () => [...(report?.vulnerabilities ?? [])].sort(
      (a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity)
    ),
    [report]
  )

  const sevCounts = useMemo(() => {
    const c: Record<string, number> = {}
    sortedVulns.forEach((v) => { c[v.severity] = (c[v.severity] ?? 0) + 1 })
    return c
  }, [sortedVulns])

  return (
    <div className="flex flex-col h-screen bg-sentinel-bg overflow-hidden">
      {/* Top bar */}
      <header className="shrink-0 flex items-center gap-3 px-4 sm:px-5 py-3 border-b border-sentinel-border bg-sentinel-surface overflow-x-auto">
        <a href="/scan" className="text-sentinel-muted hover:text-white transition-colors text-sm font-semibold shrink-0">
          ← VulnSentinel
        </a>
        <span className="text-sentinel-border">·</span>
        <span className="text-xs font-mono text-sentinel-muted shrink-0">scan/{scanId}</span>

        <div className="ml-auto flex items-center gap-2 sm:gap-4 shrink-0">
          {/* WS status */}
          <span className={`flex items-center gap-1.5 text-xs font-mono ${
            status === "open" ? "text-sentinel-green" :
            status === "closed" ? "text-sentinel-muted" :
            "text-sentinel-red"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              status === "open"   ? "bg-sentinel-green animate-pulse" :
              status === "closed" ? "bg-sentinel-muted" : "bg-sentinel-red"
            }`} />
            <span className="hidden sm:inline">{status.toUpperCase()}</span>
          </span>

          {/* Active node */}
          {activeNode && (
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-sentinel-cyan/10 text-sentinel-cyan border border-sentinel-cyan/20 animate-pulse truncate">
              {activeNode.replace("_", " ")}
            </span>
          )}

          {/* Risk badge */}
          {report?.summary && (
            <span className={`text-xs font-mono px-2 py-0.5 rounded-full border shrink-0 ${
              report.summary.overall_risk === "CRITICAL" ? "pill-critical" :
              report.summary.overall_risk === "HIGH"     ? "pill-high"     :
              report.summary.overall_risk === "MEDIUM"   ? "pill-medium"   : "pill-low"
            }`}>
              {report.summary.overall_risk} · {report.summary.risk_score}
            </span>
          )}
        </div>
      </header>

      {/* Main split - responsive */}
      <div className="flex flex-1 overflow-hidden gap-0 flex-col lg:flex-row">
        {/* Left: agent feed - hidden on mobile, full width on tablet/desktop */}
        <div className="hidden lg:block w-full lg:w-1/2 p-3 sm:p-4 overflow-hidden border-b lg:border-b-0 lg:border-r border-sentinel-border">
          <AgentFeed logs={logs} isRunning={isRunning} />
        </div>

        {/* Right: findings */}
        <div className="flex flex-col w-full lg:w-1/2 overflow-hidden">

          {/* Stats bar - responsive grid */}
          <div className="shrink-0 grid grid-cols-2 lg:grid-cols-4 gap-0 border-b border-sentinel-border">
            {SEV_ORDER.map((sev) => (
              <div key={sev} className="text-center py-2 sm:py-3 border-r border-sentinel-border last:border-r-0">
                <div className={`text-lg sm:text-xl font-bold font-mono ${SEV_COLORS[sev]}`}>
                  {sevCounts[sev] ?? (report ? "0" : "—")}
                </div>
                <div className="text-xs text-sentinel-muted mt-0.5">{sev}</div>
              </div>
            ))}
          </div>

          {/* Summary */}
          {report?.summary && (
            <div className="shrink-0 p-3 sm:p-4 border-b border-sentinel-border bg-sentinel-surface/50 space-y-2">
              <p className="text-sm text-slate-300 leading-relaxed">{report.summary.executive_summary}</p>
              {report.summary.key_recommendations?.length > 0 && (
                <ul className="space-y-1">
                  {report.summary.key_recommendations.map((r: unknown, i: number) => {
                    const text = typeof r === "string" ? r
                      : typeof r === "object" && r !== null
                        ? (r as Record<string, unknown>).recommendation
                          ?? (r as Record<string, unknown>).text
                          ?? JSON.stringify(r)
                        : String(r)
                    return (
                      <li key={i} className="text-xs text-sentinel-muted flex gap-2">
                        <span className="text-sentinel-green shrink-0">▸</span>
                        <span>{text as string}</span>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}

          {/* Vuln list */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3">
            {!report && isRunning && (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-24 rounded-xl bg-sentinel-surface border border-sentinel-border animate-pulse" />
                ))}
              </div>
            )}

            {!report && !isRunning && status === "closed" && logs.length === 0 && (
              <p className="text-sentinel-muted text-sm text-center mt-8">Connecting to scan…</p>
            )}

            {sortedVulns.map((v) => (
              <VulnCard key={v.id} vuln={v} patch={patchMap[v.id]} />
            ))}

            {report && sortedVulns.length === 0 && (
              <div className="flex flex-col items-center justify-center h-40 text-center">
                <div className="w-10 h-10 rounded-full bg-sentinel-green/10 border border-sentinel-green/30 flex items-center justify-center mb-3">
                  <svg className="w-5 h-5 text-sentinel-green" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                  </svg>
                </div>
                <p className="text-sentinel-green font-medium">No vulnerabilities found</p>
                <p className="text-sentinel-muted text-sm mt-1">Repository looks clean.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile-only agent feed footer */}
      <div className="lg:hidden shrink-0 border-t border-sentinel-border bg-sentinel-surface p-3 max-h-48">
        <div className="flex items-center gap-2 mb-2 text-xs font-mono text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-sentinel-green animate-pulse" />
          Agent Feed ({logs.length} lines)
        </div>
        <div className="overflow-y-auto max-h-40 text-xs font-mono text-slate-300 space-y-0.5 pr-2">
          {logs.slice(-5).map((log, i) => (
            <div key={i} className="text-sentinel-muted">{log}</div>
          ))}
        </div>
      </div>
    </div>
  )
}
