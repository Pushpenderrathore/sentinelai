"use client"

import { useState } from "react"

// jsPDF is imported dynamically inside handleClick so it never runs during SSR.
// (Next.js evaluates "use client" modules on the server for the initial HTML pass;
// jsPDF calls browser-only APIs at module-load time and silently breaks there.)
type JsPDFType = import("jspdf").jsPDF

// ─── Types (mirrored from the scan results page) ──────────────────────────────

interface Vuln {
  id: string
  file: string
  line: number
  severity: string
  category: string
  description: string
  cve?: string | null
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

export interface ScanReport {
  repo_url: string
  vulnerabilities: Vuln[]
  patches: Patch[]
  summary: {
    executive_summary: string
    risk_score: number
    overall_risk: string
    key_recommendations: string[]
  }
}

// ─── Palette (dark theme, matches app) ───────────────────────────────────────

const C = {
  bg:        [13,  17,  23]  as [number, number, number],   // #0d1117
  surface:   [17,  17,  24]  as [number, number, number],   // #111118
  border:    [30,  30,  46]  as [number, number, number],   // #1e1e2e
  cyan:      [0,   188, 212] as [number, number, number],   // #00bcd4
  cyanDim:   [0,   100, 120] as [number, number, number],
  white:     [226, 232, 240] as [number, number, number],   // slate-200
  muted:     [100, 116, 139] as [number, number, number],   // slate-500
  green:     [0,   255, 136] as [number, number, number],   // #00ff88
  red:       [255, 51,  102] as [number, number, number],   // #ff3366
  orange:    [251, 146, 60]  as [number, number, number],   // orange-400
  yellow:    [250, 204, 21]  as [number, number, number],   // yellow-400
  blue:      [96,  165, 250] as [number, number, number],   // blue-400
} as const

const SEV_COLOR: Record<string, [number, number, number]> = {
  CRITICAL: C.red,
  HIGH:     C.orange,
  MEDIUM:   C.yellow,
  LOW:      C.blue,
}

// ─── PDF helpers ──────────────────────────────────────────────────────────────

const PAGE_W   = 210   // A4 mm
const PAGE_H   = 297
const MARGIN_X = 18
const CONTENT_W = PAGE_W - MARGIN_X * 2

/** Fill the entire page with the dark background. */
function fillBackground(doc: JsPDFType) {
  doc.setFillColor(...C.bg)
  doc.rect(0, 0, PAGE_W, PAGE_H, "F")
}

/** Add a new page, fill background, reset y cursor to top margin. */
function newPage(doc: JsPDFType): number {
  doc.addPage()
  fillBackground(doc)
  return 20
}

/** Draw a horizontal rule. */
function rule(doc: JsPDFType, y: number, color = C.border) {
  doc.setDrawColor(...color)
  doc.setLineWidth(0.2)
  doc.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)
}

/**
 * Render `text` with word-wrap, respecting a max line count.
 * Returns the y position after the last line.
 */
function wrappedText(
  doc: JsPDFType,
  text: string,
  x: number,
  y: number,
  {
    maxWidth   = CONTENT_W,
    lineHeight = 5,
    maxLines   = 0,
    color      = C.white,
    fontSize   = 9,
  }: {
    maxWidth?:   number
    lineHeight?: number
    maxLines?:   number
    color?:      [number, number, number]
    fontSize?:   number
  } = {}
): number {
  doc.setFontSize(fontSize)
  doc.setTextColor(...color)
  const lines = doc.splitTextToSize(text, maxWidth) as string[]
  const visible = maxLines > 0 ? lines.slice(0, maxLines) : lines
  if (maxLines > 0 && lines.length > maxLines) {
    visible[maxLines - 1] = visible[maxLines - 1].replace(/\.?\s*$/, "…")
  }
  doc.text(visible, x, y)
  return y + visible.length * lineHeight
}

/** Small pill badge (filled rectangle + text). Returns right edge x. */
function pill(
  doc: JsPDFType,
  label: string,
  x: number,
  y: number,
  bg: [number, number, number],
  fg: [number, number, number] = C.bg,
): number {
  doc.setFontSize(7)
  const tw = doc.getTextWidth(label)
  const pw = tw + 4
  const ph = 4.5
  doc.setFillColor(...bg)
  doc.roundedRect(x, y - 3.2, pw, ph, 1, 1, "F")
  doc.setTextColor(...fg)
  doc.text(label, x + 2, y)
  return x + pw + 2
}

/** Outlined pill (for ID / CVE chips). Returns right edge x. */
function pillOutline(
  doc: JsPDFType,
  label: string,
  x: number,
  y: number,
  color: [number, number, number],
): number {
  doc.setFontSize(7)
  const tw = doc.getTextWidth(label)
  const pw = tw + 4
  const ph = 4.5
  doc.setDrawColor(...color)
  doc.setLineWidth(0.15)
  doc.roundedRect(x, y - 3.2, pw, ph, 1, 1, "S")
  doc.setTextColor(...color)
  doc.text(label, x + 2, y)
  return x + pw + 2
}

// ─── Page builders ────────────────────────────────────────────────────────────

function buildCoverPage(doc: JsPDFType, report: ScanReport, scanId: string) {
  fillBackground(doc)

  const vulns = report.vulnerabilities ?? []
  const overall = report.summary?.overall_risk ?? "UNKNOWN"
  const score   = report.summary?.risk_score   ?? 0

  // ── Cyan accent bar left edge
  doc.setFillColor(...C.cyan)
  doc.rect(0, 0, 3, PAGE_H, "F")

  // ── Shield icon (simple polygon approximation via lines)
  const sx = MARGIN_X + 8
  const sy = 38
  const shieldColor: [number, number, number] = C.cyan
  doc.setDrawColor(...shieldColor)
  doc.setLineWidth(0.8)
  // Shield: top arc approximated with lines
  doc.lines(
    [[10,0],[10,0],[0,6],[0,6],[-10,0],[-10,0],[-10,12],[-10,12],[0,12],[0,12],[10,12],[10,12],[10,0]],
    sx, sy, [1, 1], "S"
  )
  // checkmark inside shield
  doc.setLineWidth(0.6)
  doc.line(sx + 4, sy + 10, sx + 6, sy + 13)
  doc.line(sx + 6, sy + 13, sx + 16, sy + 5)

  // ── Product name
  doc.setFontSize(28)
  doc.setTextColor(...C.white)
  doc.setFont("helvetica", "bold")
  doc.text("VulnSentinel", MARGIN_X + 25, sy + 8)

  doc.setFontSize(11)
  doc.setFont("helvetica", "normal")
  doc.setTextColor(...C.cyan)
  doc.text("Security Scan Report", MARGIN_X + 25, sy + 16)

  // ── Divider
  rule(doc, sy + 24, C.cyan)

  // ── Metadata table
  let y = sy + 36
  const labelX  = MARGIN_X
  const valueX  = MARGIN_X + 38

  const rows: [string, string][] = [
    ["Target",     report.repo_url],
    ["Scan ID",    scanId],
    ["Generated",  new Date().toUTCString()],
    ["Total Findings", String(vulns.length)],
  ]

  for (const [label, value] of rows) {
    doc.setFontSize(8)
    doc.setFont("helvetica", "bold")
    doc.setTextColor(...C.muted)
    doc.text(label.toUpperCase(), labelX, y)

    doc.setFont("helvetica", "normal")
    doc.setTextColor(...C.white)
    const wrapped = doc.splitTextToSize(value, CONTENT_W - 38) as string[]
    doc.text(wrapped, valueX, y)
    y += Math.max(wrapped.length * 5, 6) + 2
  }

  // ── Risk score block
  y += 6
  rule(doc, y, C.border)
  y += 10

  const riskColor = SEV_COLOR[overall] ?? C.muted

  // Large risk score circle
  doc.setFillColor(...riskColor)
  doc.circle(MARGIN_X + 18, y + 14, 16, "F")
  doc.setFontSize(18)
  doc.setFont("helvetica", "bold")
  doc.setTextColor(...C.bg)
  const scoreStr = String(score)
  const scoreW   = doc.getTextWidth(scoreStr)
  doc.text(scoreStr, MARGIN_X + 18 - scoreW / 2, y + 16.5)
  doc.setFontSize(7)
  doc.setTextColor(...C.bg)
  const outOf = "/100"
  doc.text(outOf, MARGIN_X + 18 - doc.getTextWidth(outOf) / 2, y + 22)

  doc.setFontSize(20)
  doc.setFont("helvetica", "bold")
  doc.setTextColor(...riskColor)
  doc.text(`${overall} RISK`, MARGIN_X + 42, y + 12)

  doc.setFontSize(9)
  doc.setFont("helvetica", "normal")
  doc.setTextColor(...C.muted)
  doc.text("Overall risk assessment based on severity distribution and exploitability.", MARGIN_X + 42, y + 20)

  // ── Severity distribution boxes
  y += 44
  rule(doc, y, C.border)
  y += 8

  doc.setFontSize(8)
  doc.setFont("helvetica", "bold")
  doc.setTextColor(...C.muted)
  doc.text("SEVERITY BREAKDOWN", MARGIN_X, y)
  y += 6

  const sevOrder = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const
  const sevCounts: Record<string, number> = {}
  for (const v of vulns) sevCounts[v.severity] = (sevCounts[v.severity] ?? 0) + 1

  const boxW  = (CONTENT_W - 9) / 4
  const boxH  = 20

  sevOrder.forEach((sev, i) => {
    const bx = MARGIN_X + i * (boxW + 3)
    const color = SEV_COLOR[sev]
    const count = sevCounts[sev] ?? 0

    // Box background tint (dim the color manually to avoid alpha API)
    doc.setFillColor(
      Math.round(C.bg[0] * 0.85 + color[0] * 0.15),
      Math.round(C.bg[1] * 0.85 + color[1] * 0.15),
      Math.round(C.bg[2] * 0.85 + color[2] * 0.15),
    )
    doc.roundedRect(bx, y, boxW, boxH, 2, 2, "F")

    // Border
    doc.setDrawColor(...color)
    doc.setLineWidth(0.2)
    doc.roundedRect(bx, y, boxW, boxH, 2, 2, "S")

    // Count
    doc.setFontSize(16)
    doc.setFont("helvetica", "bold")
    doc.setTextColor(...color)
    const cStr = String(count)
    doc.text(cStr, bx + boxW / 2 - doc.getTextWidth(cStr) / 2, y + 12)

    // Label
    doc.setFontSize(6.5)
    doc.setFont("helvetica", "normal")
    doc.setTextColor(...C.muted)
    doc.text(sev, bx + boxW / 2 - doc.getTextWidth(sev) / 2, y + 18)
  })

  y += boxH + 12

  // ── Executive summary
  if (report.summary?.executive_summary) {
    rule(doc, y, C.border)
    y += 8
    doc.setFontSize(8)
    doc.setFont("helvetica", "bold")
    doc.setTextColor(...C.muted)
    doc.text("EXECUTIVE SUMMARY", MARGIN_X, y)
    y += 6
    y = wrappedText(doc, report.summary.executive_summary, MARGIN_X, y, {
      color:      C.white,
      fontSize:   9,
      lineHeight: 5,
      maxLines:   8,
    })
  }

  // ── Key recommendations
  const recs = report.summary?.key_recommendations ?? []
  if (recs.length > 0 && y < PAGE_H - 50) {
    y += 8
    rule(doc, y, C.border)
    y += 8
    doc.setFontSize(8)
    doc.setFont("helvetica", "bold")
    doc.setTextColor(...C.muted)
    doc.text("KEY RECOMMENDATIONS", MARGIN_X, y)
    y += 6

    for (const rec of recs.slice(0, 5)) {
      const text = typeof rec === "string" ? rec
        : typeof rec === "object" && rec !== null
          ? (rec as Record<string, unknown>).recommendation as string
            ?? (rec as Record<string, unknown>).text as string
            ?? JSON.stringify(rec)
          : String(rec)

      if (y > PAGE_H - 20) break
      doc.setFontSize(7)
      doc.setTextColor(...C.cyan)
      doc.text("▸", MARGIN_X, y)
      y = wrappedText(doc, text, MARGIN_X + 5, y, {
        maxWidth:   CONTENT_W - 5,
        color:      C.white,
        fontSize:   8.5,
        lineHeight: 5,
        maxLines:   3,
      })
      y += 2
    }
  }

  // ── Footer
  doc.setFontSize(7)
  doc.setTextColor(...C.muted)
  doc.text("Generated by VulnSentinel · Confidential", MARGIN_X, PAGE_H - 10)
  doc.text("Page 1", PAGE_W - MARGIN_X - doc.getTextWidth("Page 1"), PAGE_H - 10)
}

function buildVulnPages(doc: JsPDFType, report: ScanReport) {
  const vulns   = [...(report.vulnerabilities ?? [])].sort((a, b) => {
    const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    return order.indexOf(a.severity) - order.indexOf(b.severity)
  })
  const patchMap: Record<string, Patch> = {}
  for (const p of report.patches ?? []) patchMap[p.vuln_id] = p

  if (vulns.length === 0) {
    let y = newPage(doc)

    // Cyan left bar
    doc.setFillColor(...C.cyan)
    doc.rect(0, 0, 3, PAGE_H, "F")

    doc.setFontSize(16)
    doc.setFont("helvetica", "bold")
    doc.setTextColor(...C.green)
    doc.text("No Vulnerabilities Found", MARGIN_X, y + 20)

    doc.setFontSize(10)
    doc.setFont("helvetica", "normal")
    doc.setTextColor(...C.muted)
    doc.text("The scanned target returned no security findings.", MARGIN_X, y + 32)

    footer(doc, 2)
    return
  }

  let pageNum = 2
  let y = newPage(doc)

  // Cyan left bar on first vuln page
  doc.setFillColor(...C.cyan)
  doc.rect(0, 0, 3, PAGE_H, "F")

  // Section header
  doc.setFontSize(13)
  doc.setFont("helvetica", "bold")
  doc.setTextColor(...C.cyan)
  doc.text("Vulnerability Findings", MARGIN_X, y)
  y += 4
  rule(doc, y, C.cyan)
  y += 8

  for (let i = 0; i < vulns.length; i++) {
    const v     = vulns[i]
    const patch = patchMap[v.id]

    // Estimate card height to decide if we need a new page
    const descLines = (doc.splitTextToSize(v.description, CONTENT_W - 6) as string[]).length
    const fixLines  = patch?.explanation
      ? Math.min((doc.splitTextToSize(patch.explanation, CONTENT_W - 6) as string[]).length, 5)
      : 0
    const cardHeight = 8 + descLines * 5 + (v.file ? 6 : 0) + (patch ? fixLines * 5 + 16 : 0) + 8

    if (y + cardHeight > PAGE_H - 16) {
      footer(doc, pageNum)
      pageNum++
      y = newPage(doc)
      doc.setFillColor(...C.cyan)
      doc.rect(0, 0, 3, PAGE_H, "F")
    }

    // ── Card background
    doc.setFillColor(...C.surface)
    doc.roundedRect(MARGIN_X, y - 2, CONTENT_W, cardHeight, 2, 2, "F")

    // Left severity stripe
    const sc = SEV_COLOR[v.severity] ?? C.muted
    doc.setFillColor(...sc)
    doc.roundedRect(MARGIN_X, y - 2, 2.5, cardHeight, 1, 1, "F")

    // Card border
    doc.setDrawColor(...C.border)
    doc.setLineWidth(0.15)
    doc.roundedRect(MARGIN_X, y - 2, CONTENT_W, cardHeight, 2, 2, "S")

    const cx = MARGIN_X + 6
    y += 2

    // Row 1: severity pill + ID chip + CVE chip + category (right-aligned)
    let px = cx
    px = pill(doc, v.severity, px, y, sc, C.bg)
    px = pillOutline(doc, v.id, px, y, C.muted)
    if (v.cve) px = pillOutline(doc, v.cve, px, y, C.blue)

    // Category right-aligned
    doc.setFontSize(7.5)
    doc.setFont("helvetica", "normal")
    doc.setTextColor(...C.muted)
    const catW = doc.getTextWidth(v.category)
    doc.text(v.category, PAGE_W - MARGIN_X - catW, y)

    y += 5

    // Row 2: description (max 10 lines)
    y = wrappedText(doc, v.description, cx, y, {
      maxWidth:   CONTENT_W - 6,
      color:      C.white,
      fontSize:   9,
      lineHeight: 5,
      maxLines:   10,
    })

    // Row 3: file path (non-port)
    if (v.file) {
      y += 2
      doc.setFontSize(7.5)
      doc.setFont("helvetica", "normal")
      doc.setTextColor(...C.muted)
      const loc = v.line > 0 ? `${v.file}:${v.line}` : v.file
      doc.text(loc, cx, y)
      y += 5
    }

    // Row 4: port info
    if (v.port) {
      y += 1
      doc.setFontSize(7.5)
      doc.setTextColor(...C.muted)
      doc.text(`Port: ${v.port}/${v.service ?? ""}`, cx, y)
      y += 5
    }

    // Row 5: patch explanation
    if (patch?.explanation) {
      y += 1
      doc.setFontSize(7.5)
      doc.setFont("helvetica", "bold")
      doc.setTextColor(...C.green)
      doc.text("Suggested Fix", cx, y)
      y += 4
      y = wrappedText(doc, patch.explanation, cx, y, {
        maxWidth:   CONTENT_W - 6,
        color:      [150, 200, 150],
        fontSize:   8,
        lineHeight: 5,
        maxLines:   5,
      })
    }

    y += 8 // gap between cards
  }

  footer(doc, pageNum)
}

function footer(doc: JsPDFType, pageNum: number) {
  doc.setFontSize(7)
  doc.setTextColor(...C.muted)
  doc.text("Generated by VulnSentinel · Confidential", MARGIN_X, PAGE_H - 10)
  doc.text(`Page ${pageNum}`, PAGE_W - MARGIN_X - doc.getTextWidth(`Page ${pageNum}`), PAGE_H - 10)
}

// ─── Entry point ──────────────────────────────────────────────────────────────

async function generatePDF(report: ScanReport, scanId: string): Promise<void> {
  // Dynamic import ensures jsPDF is never evaluated during SSR.
  const { jsPDF } = await import("jspdf")

  // ONE document for the whole scan:
  //   page 1     → cover (URL, date, risk score, severity counts)
  //   page 2+    → all vulnerabilities, sorted Critical → Low
  const doc = new jsPDF({ unit: "mm", format: "a4", compress: true })
  doc.setFont("helvetica", "normal")

  buildCoverPage(doc, report, scanId)
  buildVulnPages(doc, report)

  // Filename: vulnsentinel-report-YYYY-MM-DD.pdf
  const date = new Date().toISOString().slice(0, 10)
  const filename = `vulnsentinel-report-${date}.pdf`

  // Bulletproof single-download: build a Blob and click a real anchor.
  // doc.save() relies on jsPDF's internal FileSaver path, which can fail
  // silently in some browsers / sandboxed iframes. An explicit Blob URL +
  // <a download> works everywhere and guarantees exactly one download.
  const blob = doc.output("blob") as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Release the object URL on the next tick (after the download has started).
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// ─── Button component ─────────────────────────────────────────────────────────

interface Props {
  report: ScanReport
  scanId: string
}

export default function ExportPDFButton({ report, scanId }: Props) {
  const [loading, setLoading] = useState(false)

  async function handleClick() {
    if (loading) return
    setLoading(true)
    try {
      await generatePDF(report, scanId)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 rounded-lg
                 border border-sentinel-cyan/30 text-sentinel-cyan
                 bg-sentinel-cyan/5 hover:bg-sentinel-cyan/15
                 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-all duration-150 active:scale-95"
    >
      {loading ? (
        <>
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Building PDF…
        </>
      ) : (
        <>
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
          </svg>
          Export PDF
        </>
      )}
    </button>
  )
}
