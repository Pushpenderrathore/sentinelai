"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { startScan } from "@/lib/api"

function detectScanType(url: string): "github" | "website" | null {
  if (!url.trim()) return null
  try {
    const parsed = new URL(url.startsWith("http") ? url : `https://${url}`)
    if (parsed.hostname === "github.com") {
      // Must have owner/repo path (at least 2 non-empty segments)
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
  ["○", "Orchestrator",     "Plans scan strategy for the repository"],
  ["○", "Scanner Agent",    "Clones repo · runs Semgrep + Bandit"],
  ["○", "Vuln Analyzer",   "Maps findings to OWASP categories & CVEs"],
  ["○", "Exploit Reasoner", "Assesses real-world exploitability"],
  ["○", "Fix Suggester",    "Generates code patches per vulnerability"],
]

const WEBSITE_AGENTS = [
  ["○", "Orchestrator",     "Plans HTTP security audit strategy"],
  ["○", "Scanner Agent",    "Checks headers, SSL, cookies, exposed files, CORS"],
  ["○", "Vuln Analyzer",   "Maps findings to OWASP categories & CVEs"],
  ["○", "Exploit Reasoner", "Assesses exploitability of each issue"],
  ["○", "Fix Suggester",    "Generates remediation guidance"],
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
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <a href="/" className="absolute top-6 left-6 text-sentinel-muted hover:text-white text-sm flex items-center gap-1.5 transition-colors">
        ← Home
      </a>

      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="mb-10 text-center">
          <div className="inline-block text-sentinel-cyan mb-4">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-2">VulnSentinel</h1>
          <p className="text-sentinel-muted text-sm">
            Paste a <span className="text-slate-300">GitHub repo URL</span> or any <span className="text-slate-300">website URL</span>.
            Five agents will audit it autonomously.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
              {scanType === "github" ? (
                <svg className="w-4 h-4 text-sentinel-cyan" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577v-2.165c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.63-5.37-12-12-12z"/>
                </svg>
              ) : scanType === "website" ? (
                <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253"/>
                </svg>
              ) : (
                <svg className="w-4 h-4 text-sentinel-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
                </svg>
              )}
            </div>

            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="github.com/owner/repo  or  example.com"
              className="w-full pl-11 pr-4 py-3.5 bg-sentinel-surface border border-sentinel-border rounded-xl
                         text-sm font-mono placeholder:text-sentinel-muted
                         focus:outline-none focus:border-sentinel-cyan/50 focus:ring-1 focus:ring-sentinel-cyan/20
                         transition-colors"
            />

            {/* Scan type badge */}
            {scanType && (
              <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none">
                <span className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
                  scanType === "github"
                    ? "text-sentinel-cyan border-sentinel-cyan/30 bg-sentinel-cyan/10"
                    : "text-purple-400 border-purple-400/30 bg-purple-400/10"
                }`}>
                  {scanType === "github" ? "GitHub Repo" : "Website"}
                </span>
              </div>
            )}
          </div>

          {validationErr && <p className="text-yellow-400 text-sm px-1">{validationErr}</p>}
          {error && <p className="text-sentinel-red text-sm px-1">{error}</p>}

          <button
            type="submit"
            disabled={loading || !url.trim() || !!validationErr}
            className="w-full py-3.5 rounded-xl font-medium text-sm
                       bg-sentinel-cyan text-black
                       hover:bg-sentinel-cyan/90 active:scale-[0.98]
                       disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all duration-150"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Starting scan…
              </span>
            ) : "Launch Security Scan"}
          </button>
        </form>

        {/* What happens next */}
        <div className="mt-10 border border-sentinel-border rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs text-sentinel-muted font-mono uppercase tracking-wider">What happens next</p>
            {scanType && (
              <span className={`text-xs font-mono ${scanType === "github" ? "text-sentinel-cyan" : "text-purple-400"}`}>
                {scanType === "github" ? "Static Analysis Mode" : "HTTP Security Mode"}
              </span>
            )}
          </div>
          {agents.map(([icon, name, desc]) => (
            <div key={name as string} className="flex items-center gap-3 text-sm">
              <span className="text-base w-6 text-center">{icon}</span>
              <span className="text-slate-300 font-medium w-40">{name}</span>
              <span className="text-sentinel-muted">{desc}</span>
            </div>
          ))}
        </div>

        {/* Example targets */}
        <div className="mt-4 flex flex-wrap gap-2 justify-center">
          {[
            { label: "OWASP Mutillidae", url: "https://github.com/webpwnized/mutillidae" },
            { label: "WebGoat", url: "https://github.com/WebGoat/WebGoat" },
            { label: "example.com", url: "https://example.com" },
          ].map(({ label, url: exUrl }) => (
            <button
              key={label}
              onClick={() => setUrl(exUrl)}
              className="text-xs font-mono px-3 py-1.5 rounded-lg border border-sentinel-border
                         text-sentinel-muted hover:text-white hover:border-slate-500 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </main>
  )
}
