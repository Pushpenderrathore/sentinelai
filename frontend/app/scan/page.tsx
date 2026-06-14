"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { startScan } from "@/lib/api"
import Link from "next/link"

function detectScanType(url: string): "github" | "website" | null {
  if (!url.trim()) return null
  try {
    const parsed = new URL(url.startsWith("http") ? url : `https://${url}`)
    if (parsed.hostname === "github.com") {
      const segments = parsed.pathname.split("/").filter(Boolean)
      return segments.length >= 2 ? "github" : null
    }
    return "website"
  } catch {
    return null
  }
}

function getValidationError(url: string): string | null {
  if (!url.trim()) return null
  try {
    const parsed = new URL(url.startsWith("http") ? url : `https://${url}`)
    if (parsed.hostname === "github.com") {
      const segments = parsed.pathname.split("/").filter(Boolean)
      if (segments.length < 2) return "Enter a full GitHub repo URL (e.g. github.com/owner/repo)"
    }
    return null
  } catch {
    return "Invalid URL"
  }
}

const GITHUB_AGENTS = [
  { name: "Orchestrator",     desc: "Plans scan strategy for the repository" },
  { name: "Scanner Agent",    desc: "Clones repo · runs Semgrep + Bandit" },
  { name: "Vuln Analyzer",   desc: "Maps findings to OWASP categories & CVEs" },
  { name: "Exploit Reasoner", desc: "Assesses real-world exploitability" },
  { name: "Fix Suggester",    desc: "Generates code patches per vulnerability" },
]

const WEBSITE_AGENTS = [
  { name: "Orchestrator",     desc: "Plans HTTP security audit strategy" },
  { name: "Scanner Agent",    desc: "Checks headers, SSL, cookies, exposed files, CORS" },
  { name: "Vuln Analyzer",   desc: "Maps findings to OWASP categories & CVEs" },
  { name: "Exploit Reasoner", desc: "Assesses exploitability of each issue" },
  { name: "Fix Suggester",    desc: "Generates remediation guidance" },
]

export default function ScanPage() {
  const router = useRouter()
  const [url, setUrl]         = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState("")

  const scanType      = detectScanType(url)
  const validationErr = getValidationError(url)
  const agents        = scanType === "website" ? WEBSITE_AGENTS : GITHUB_AGENTS

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!url.trim() || validationErr) return
    setLoading(true)
    setError("")
    try {
      const target = url.startsWith("http") ? url : `https://${url}`
      const { scan_id } = await startScan(target)
      router.push(`/scan/${scan_id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start scan")
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen px-4 sm:px-6 py-8 sm:py-12 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl opacity-20" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl opacity-20" />
      </div>

      {/* Scan history link */}
      <Link href="/history" className="absolute top-6 right-6 z-10 text-xs font-mono text-slate-400 hover:text-cyan-400 border border-white/10 hover:border-cyan-400/40 rounded-lg px-3 py-1.5 transition-colors">
        Scan History
      </Link>

      <div className="relative z-10 max-w-2xl mx-auto">
        {/* Header */}
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-cyan-400 mb-8 transition-colors">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to home
        </Link>

        <div className="mb-12">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
              </svg>
            </div>
            <div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white mb-1">VulnSentinel</h1>
              <p className="text-sm text-slate-400">Autonomous vulnerability scanning powered by AI agents</p>
            </div>
          </div>
          <p className="text-slate-400 max-w-lg">
            Enter any GitHub repository or website URL. Our multi-agent system will autonomously conduct a comprehensive security audit, identifying vulnerabilities, analyzing exploitability, and suggesting patches.
          </p>
        </div>

        {/* Main form card */}
        <form onSubmit={handleSubmit} className="glass-card p-6 sm:p-8 mb-8 space-y-4">
          {/* URL Input */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">Target URL</label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                {scanType === "github" ? (
                  <svg className="w-5 h-5 text-cyan-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577v-2.165c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.63-5.37-12-12-12z"/>
                  </svg>
                ) : scanType === "website" ? (
                  <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253"/>
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
                  </svg>
                )}
              </div>

              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="github.com/owner/repo  or  https://example.com"
                className="input-glass !pl-11 !pr-32"
              />

              {scanType && (
                <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none">
                  <span className={`text-xs font-mono px-3 py-1.5 rounded-lg border ${
                    scanType === "github"
                      ? "text-cyan-300 border-cyan-500/30 bg-cyan-500/10"
                      : "text-purple-300 border-purple-500/30 bg-purple-500/10"
                  }`}>
                    {scanType === "github" ? "GitHub Repo" : "Website"}
                  </span>
                </div>
              )}
            </div>

            {validationErr && (
              <p className="text-yellow-400 text-xs font-medium mt-2 flex items-center gap-1">
                <span>⚠️</span> {validationErr}
              </p>
            )}
            {error && (
              <p className="text-red-400 text-xs font-medium mt-2 flex items-center gap-1">
                <span>✕</span> {error}
              </p>
            )}
          </div>

          {/* Quick examples */}
          <div className="pt-2">
            <p className="text-xs text-slate-500 font-medium mb-2">Try these:</p>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "OWASP Mutillidae", url: "https://github.com/webpwnized/mutillidae" },
                { label: "WebGoat", url: "https://github.com/WebGoat/WebGoat" },
                { label: "example.com", url: "https://example.com" },
              ].map(({ label, url: exUrl }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setUrl(exUrl)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-300
                           hover:bg-white/10 hover:border-white/20 hover:text-white
                           transition-all duration-300"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Submit button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={loading || !url.trim() || !!validationErr}
              className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Initializing scan...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                  </svg>
                  Launch Security Scan
                </>
              )}
            </button>
          </div>
        </form>

        {/* Agent pipeline visualization */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 flex items-center justify-center text-xs">🤖</span>
            Multi-Agent Pipeline
          </h3>

          <div className="space-y-3">
            {agents.map((agent, idx) => (
              <div key={agent.name} className="flex gap-3 animate-in" style={{ animationDelay: `${idx * 0.1}s` }}>
                {/* Step number */}
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-500/30 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-bold text-cyan-400">{idx + 1}</span>
                </div>

                {/* Connector line */}
                {idx < agents.length - 1 && (
                  <div className="absolute left-[19px] top-[calc(100%)] w-0.5 h-6 bg-gradient-to-b from-cyan-500/50 to-transparent" />
                )}

                {/* Agent info */}
                <div className="flex-grow">
                  <p className="text-sm font-semibold text-white">{agent.name}</p>
                  <p className="text-xs text-slate-400">{agent.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 pt-6 border-t border-white/10">
            <p className="text-xs text-slate-400 flex items-start gap-2">
              <span className="mt-0.5">💡</span>
              <span>Each agent specializes in a specific phase of the security audit. Results are synthesized into comprehensive findings with remediation guidance.</span>
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
