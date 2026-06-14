const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? "Request failed")
  }
  return res.json()
}

// ── VulnSentinel ───────────────────────────────────────────────

export const startScan = (repo_url: string) =>
  req<{ scan_id: string; ws_url: string; status: string }>("/api/scan", {
    method: "POST",
    body: JSON.stringify({ repo_url }),
  })

export const getReport = (scan_id: string) =>
  req<Record<string, unknown>>(`/api/report/${scan_id}`)

export const listScans = () =>
  req<{ scan_id: string; repo_url: string; status: string; started_at: number }[]>("/api/scans")

export interface ScanSummaryRecord {
  scan_id:      string
  timestamp:    number
  scan_date:    string
  risk_score:   number
  overall_risk: string
  total_vulns:  number
  severity:     { critical: number; high: number; medium: number; low: number }
}

export interface ScanHistoryRecord {
  scan_id:         string
  domain:          string
  repo_url:        string
  scan_date:       string
  timestamp:       number
  total_vulns:     number
  severity:        { critical: number; high: number; medium: number; low: number }
  risk_score:      number
  overall_risk:    string
  vulnerabilities: unknown[]
  patches:         unknown[]
  summary:         Record<string, unknown>
}

export interface DomainHistory {
  domain:      string
  scan_count:  number
  latest_scan: ScanHistoryRecord
  scans:       ScanSummaryRecord[]
}

export interface ScanComparison {
  scan_a:      ScanSummaryRecord
  scan_b:      ScanSummaryRecord
  score_delta: number
  vuln_delta:  number
  fixed_count: number
  new_count:   number
  fixed_vulns: unknown[]
  new_vulns:   unknown[]
}

export const listScanHistory    = () => req<ScanHistoryRecord[]>("/api/scans/history")
export const listHistoryDomains = () => req<DomainHistory[]>("/api/scans/history/domains")
export const getDomainHistory   = (domain: string) => req<ScanHistoryRecord[]>(`/api/scans/history/domain/${encodeURIComponent(domain)}`)
export const getScanHistory     = (scan_id: string) => req<ScanHistoryRecord>(`/api/scans/history/${scan_id}`)
export const compareScans       = (a: string, b: string) => req<ScanComparison>(`/api/scans/history/compare/${a}/${b}`)

export const deleteScanHistory = (scan_id: string) =>
  fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/scans/history/${scan_id}`, {
    method: "DELETE",
  }).then((r) => { if (!r.ok && r.status !== 204) throw new Error("Delete failed") })

// ── ExamGuard ─────────────────────────────────────────────────

export const createExamSession = (data: {
  student_id: string
  student_name: string
  exam_name: string
  duration_minutes: number
}) =>
  req<{ exam_id: string; ws_url: string; status: string }>("/api/exam/session", {
    method: "POST",
    body: JSON.stringify(data),
  })

export const getExamSession = (exam_id: string) =>
  req<{ exam_id: string; student_name: string; exam_name: string; duration_minutes: number; status: string }>(
    `/api/exam/session/${exam_id}`,
  )

export const triggerAnalysis = (exam_id: string) =>
  req<{ exam_id: string; status: string; ws_url: string }>(`/api/exam/${exam_id}/analyze`, {
    method: "POST",
  })

export const getExamReport = (exam_id: string) =>
  req<Record<string, unknown>>(`/api/exam/report/${exam_id}`)
