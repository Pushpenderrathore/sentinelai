interface Vulnerability {
  id: string
  file: string
  line: number
  severity: string
  category: string
  description: string
  cve?: string | null
  // port scan extras
  port?: number
  service?: string
  banner?: string
  cwes?: string[]
  all_cves?: string[]
  recommendation?: string
}

interface Patch {
  vuln_id: string
  file: string
  original_code: string
  patched_code: string
  explanation: string
}

const SEVERITY_PILL: Record<string, string> = {
  CRITICAL: "pill-critical",
  HIGH:     "pill-high",
  MEDIUM:   "pill-medium",
  LOW:      "pill-low",
}

export default function VulnCard({ vuln, patch }: { vuln: Vulnerability; patch?: Patch }) {
  const pill       = SEVERITY_PILL[vuln.severity] ?? "pill-low"
  const isPortScan = vuln.id?.startsWith("PORT-")
  
  const severityLevel = {
    CRITICAL: "Critical severity - requires immediate attention",
    HIGH: "High severity vulnerability",
    MEDIUM: "Medium severity issue",
    LOW: "Low severity finding"
  } as Record<string, string>

  return (
    <article 
      className="border border-sentinel-border/80 bg-gradient-to-br from-sentinel-surface to-sentinel-surface/50 rounded-xl p-4 space-y-3 animate-slide-in transition-all duration-300 hover:border-sentinel-border hover:shadow-lg hover:shadow-cyan-500/10"
      role="article"
      aria-label={`${vuln.severity} severity vulnerability in ${vuln.category}`}
    >

      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span 
            className={`text-xs px-2.5 py-1 rounded-full font-mono font-semibold ${pill}`}
            role="status"
            aria-label={severityLevel[vuln.severity] || "Unknown severity"}
          >
            {vuln.severity}
          </span>
          <span className="text-xs text-sentinel-muted font-mono" aria-label={`Vulnerability ID: ${vuln.id}`}>{vuln.id}</span>

          {/* Port badge */}
          {isPortScan && vuln.port && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 font-mono" aria-label={`Port ${vuln.port} running ${vuln.service}`}>
              {vuln.port}/{vuln.service}
            </span>
          )}

          {/* Primary CVE */}
          {vuln.cve && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono" aria-label={`CVE: ${vuln.cve}`}>
              {vuln.cve}
            </span>
          )}
        </div>
        <span className="text-xs text-sentinel-muted shrink-0 font-semibold" aria-label={`Category: ${vuln.category}`}>{vuln.category}</span>
      </div>

      {/* Description */}
      <p className="text-sm text-slate-300 leading-relaxed">{vuln.description}</p>

      {/* Port-specific details */}
      {isPortScan && (
        <div className="space-y-3">

          {/* Banner */}
          {vuln.banner && vuln.banner !== "—" && (
            <div className="text-xs font-mono bg-black/30 border border-sentinel-border rounded-lg px-3 py-2">
              <span className="text-sentinel-muted mr-2 font-semibold">Service Banner:</span>
              <span className="text-slate-300">{vuln.banner}</span>
            </div>
          )}

          {/* All CVEs */}
          {vuln.all_cves && vuln.all_cves.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-sentinel-muted font-mono uppercase tracking-wider font-semibold">Known CVEs ({vuln.all_cves.length})</p>
              <div className="flex flex-wrap gap-1.5">
                {vuln.all_cves.map((cve) => (
                  <a 
                    key={cve} 
                    href={`https://cve.mitre.org/cgi-bin/cvename.cgi?name=${cve}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono hover:bg-blue-500/20 transition-colors"
                    aria-label={`CVE ${cve} - click for details`}
                  >
                    {cve}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* CWEs */}
          {vuln.cwes && vuln.cwes.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-sentinel-muted font-mono uppercase tracking-wider font-semibold">Related CWEs ({vuln.cwes.length})</p>
              <div className="flex flex-wrap gap-1.5">
                {vuln.cwes.map((cwe) => (
                  <span key={cwe} className="text-xs px-2.5 py-1 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20 font-mono" aria-label={`CWE: ${cwe}`}>
                    {cwe.split(" ")[0]}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          {vuln.recommendation && (
            <div className="p-3 rounded-lg bg-sentinel-green/10 border border-sentinel-green/20">
              <p className="text-xs text-sentinel-green font-semibold">
                <span className="mr-2">✓</span>Recommended Fix:
              </p>
              <p className="text-xs text-sentinel-green/80 mt-1">{vuln.recommendation}</p>
            </div>
          )}
        </div>
      )}

      {/* File / location (non-port findings) */}
      {!isPortScan && (
        <div className="flex items-center gap-2 text-xs font-mono text-sentinel-muted p-2.5 rounded-lg bg-white/5">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <span className="truncate" aria-label="File path">{vuln.file}</span>
          {vuln.line > 0 && (
            <>
              <span className="text-slate-600">:</span>
              <span className="shrink-0" aria-label={`Line ${vuln.line}`}>{vuln.line}</span>
            </>
          )}
        </div>
      )}

      {/* Patch */}
      {patch && (
        <details className="group">
          <summary className="text-xs text-sentinel-green cursor-pointer select-none flex items-center gap-1.5 hover:underline font-semibold py-1 px-2 rounded-lg hover:bg-sentinel-green/10 transition-colors" role="button" aria-expanded="false">
            <svg className="w-4 h-4 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
            </svg>
            <span>View Suggested Patch</span>
          </summary>
          <div className="mt-3 space-y-2 text-xs font-mono" role="region" aria-label="Code patch">
            <div>
              <div className="text-red-400/70 mb-1 font-semibold flex items-center gap-1">
                <span>✕</span> Original Code
              </div>
              <pre className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 text-red-400 overflow-x-auto whitespace-pre-wrap break-all">
                {patch.original_code}
              </pre>
            </div>
            <div>
              <div className="text-green-400/70 mb-1 font-semibold flex items-center gap-1">
                <span>✓</span> Patched Code
              </div>
              <pre className="bg-green-500/5 border border-green-500/20 rounded-lg p-3 text-green-400 overflow-x-auto whitespace-pre-wrap break-all">
                {patch.patched_code}
              </pre>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
              <p className="text-sentinel-muted font-semibold mb-1">Explanation:</p>
              <p className="text-slate-300">{patch.explanation}</p>
            </div>
          </div>
        </details>
      )}
    </article>
  )
}
