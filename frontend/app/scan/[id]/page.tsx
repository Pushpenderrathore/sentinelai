"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import AgentFeed from "@/components/vulnsentinel/AgentFeed"
import VulnCard from "@/components/vulnsentinel/VulnCard"
import ScanProgress from "@/components/vulnsentinel/ScanProgress"
import ExportPDFButton from "@/components/vulnsentinel/ExportPDFButton"
import { useWebSocket } from "@/lib/ws"
import { useRouter } from "next/navigation"

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
  const router = useRouter()
  const resultsRef = useRef<HTMLDivElement>(null)

  const [logs, setLogs]           = useState<string[]>([])
  const [report, setReport]       = useState<Report | null>(null)
  const [activeNode, setActiveNode] = useState<string>("")
  const [scanDone, setScanDone]   = useState(false)

  const { status } = useWebSocket(wsUrl, (msg) => {
    if (msg.type === "update") {
      const newLogs = (msg.logs as string[]) ?? []
      setLogs((prev) => [...prev, ...newLogs])
      setActiveNode(msg.node as string)
    }
    if (msg.type === "done") {
      setReport(msg.report as Report)
      setActiveNode("")
      setScanDone(true)
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
      <header className="shrink-0 flex items-center gap-3 px-5 py-3 border-b border-sentinel-border bg-sentinel-surface">
        <a href="/scan" className="text-sentinel-muted hover:text-white transition-colors text-sm">
          ← VulnSentinel
        </a>
        <span className="text-sentinel-border">·</span>
        <span className="text-xs font-mono text-sentinel-muted">scan/{scanId}</span>

        <div className="ml-auto flex items-center gap-4">
          {/* History button — always visible */}
          <a href="/history"
             className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-sentinel-cyan/10
                        text-sentinel-cyan border border-sentinel-cyan/30 hover:bg-sentinel-cyan/20
                        transition-colors font-medium shrink-0">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Scan History
          </a>
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
            {status.toUpperCase()}
          </span>

          {/* Active node */}
          {activeNode && (
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-sentinel-cyan/10 text-sentinel-cyan border border-sentinel-cyan/20 animate-pulse">
              {activeNode.replace("_", " ")}
            </span>
          )}

          {/* Risk badge */}
          {report?.summary && (
            <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
              report.summary.overall_risk === "CRITICAL" ? "pill-critical" :
              report.summary.overall_risk === "HIGH"     ? "pill-high"     :
              report.summary.overall_risk === "MEDIUM"   ? "pill-medium"   : "pill-low"
            }`}>
              {report.summary.overall_risk} RISK · {report.summary.risk_score}/100
            </span>
          )}
        </div>
      </header>

      {/* Main split */}
      <div className="flex flex-1 overflow-hidden gap-0">
        {/* Left: ScanProgress (while running) → AgentFeed (always) */}
        <div className="w-[55%] flex flex-col overflow-hidden">
          {/* ScanProgress panel — visible until scan completes, then collapses */}
          <div
            className="shrink-0 overflow-hidden transition-all duration-700"
            style={{
              maxHeight: scanDone ? "0px" : "100%",
              opacity:   scanDone ? 0 : 1,
              padding:   scanDone ? "0" : undefined,
            }}
          >
            <div className="p-4">
              <ScanProgress
                scanId={scanId}
                onComplete={() => {
                  resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
                }}
                onRetry={() => router.push("/scan")}
              />
            </div>
          </div>

          {/* AgentFeed — always mounted, fills remaining height */}
          <div className="flex-1 p-4 overflow-hidden" style={{ minHeight: 0 }}>
            <AgentFeed logs={logs} isRunning={isRunning} />
          </div>
        </div>

        {/* Right: findings */}
        <div className="w-[45%] flex flex-col border-l border-sentinel-border overflow-hidden">

          {/* Results action bar — prominent, only after scan completes */}
          {report && (
            <>
              <div className="shrink-0 flex items-center justify-between gap-3 px-4 py-2.5 border-b border-sentinel-border bg-sentinel-surface/60">
                <div className="flex items-center gap-2 min-w-0">
                  <svg className="w-4 h-4 text-sentinel-cyan shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                  </svg>
                  <span className="text-sm font-medium text-white truncate">Scan Report</span>
                  <span className="text-xs font-mono text-sentinel-muted shrink-0">
                    {report.vulnerabilities?.length ?? 0} findings
                  </span>
                </div>
                <ExportPDFButton report={report} scanId={scanId} />
              </div>
              {/* Saved-to-history notice */}
              <div className="shrink-0 flex items-center gap-2 px-4 py-1.5 border-b border-sentinel-border
                              bg-sentinel-green/5 text-sentinel-green text-xs">
                <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
                This scan has been saved to history.
                <a href="/history" className="underline hover:text-white transition-colors ml-1">View all scans →</a>
              </div>
            </>
          )}

          {/* Stats bar */}
          <div className="shrink-0 flex gap-0 border-b border-sentinel-border">
            {SEV_ORDER.map((sev) => (
              <div key={sev} className="flex-1 text-center py-3 border-r border-sentinel-border last:border-r-0">
                <div className={`text-xl font-bold font-mono ${SEV_COLORS[sev]}`}>
                  {sevCounts[sev] ?? (report ? "0" : "—")}
                </div>
                <div className="text-xs text-sentinel-muted mt-0.5">{sev}</div>
              </div>
            ))}
          </div>

          {/* Summary */}
          {report?.summary && (
            <div className="shrink-0 p-4 border-b border-sentinel-border bg-sentinel-surface/50 space-y-2">
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

          {/* Scroll anchor — ScanProgress triggers scroll here on completion */}
          <div ref={resultsRef} />

          {/* Vuln list */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
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
    </div>
  )
}
