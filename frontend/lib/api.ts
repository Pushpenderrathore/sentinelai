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
