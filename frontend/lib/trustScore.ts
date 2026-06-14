// ──────────────────────────────────────────────────────────────────────────────
// Trust Score system — pure logic (no React, no DOM).
//
// Every student starts at 100. Violations deduct points; clean time recovers
// them slowly. Score is clamped to [0, 100]. All detection happens browser-side
// (face-api / coco-ssd / DOM listeners) — this module only turns detected
// violations into a score and decides which auto-actions should fire.
// ──────────────────────────────────────────────────────────────────────────────

export type ViolationType =
  | "phone"
  | "face_missing"
  | "multiple_faces"
  | "tab_switch"
  | "window_blur"
  | "copy_paste"

/** Point deduction per violation type (per spec). */
export const DEDUCTIONS: Record<ViolationType, number> = {
  phone:          15,
  face_missing:   10,
  multiple_faces: 20,
  tab_switch:     8,
  window_blur:    5,
  copy_paste:     5,
}

/** Human-readable labels for UI + PDF. */
export const VIOLATION_LABELS: Record<ViolationType, string> = {
  phone:          "Phone detected",
  face_missing:   "Face missing",
  multiple_faces: "Multiple faces",
  tab_switch:     "Tab switch",
  window_blur:    "Window blur",
  copy_paste:     "Copy-paste attempt",
}

// ── Recovery ──────────────────────────────────────────────────────────────────

/** +1 point for every this-many seconds with no violations. */
export const RECOVERY_INTERVAL_S = 30
export const RECOVERY_POINTS = 1

// ── Auto-action thresholds ────────────────────────────────────────────────────

export const WARN_THRESHOLD      = 60  // < 60 → warn the student (toast)
export const HOST_PING_THRESHOLD = 40  // < 40 → ping the host dashboard
export const TERMINATE_THRESHOLD = 20  // < 20 → auto-terminate the exam
export const PHONE_FLAG_COUNT    = 3   // 3 phone detections → auto-flag for review

// ── Status buckets (drive dashboard colors + filtering) ───────────────────────

export type TrustStatus = "clean" | "warning" | "critical" | "terminated"

export const STATUS_META: Record<
  TrustStatus,
  { label: string; dot: string; text: string; ring: string; emoji: string }
> = {
  clean:      { label: "Clean",          dot: "bg-sentinel-green", text: "text-sentinel-green", ring: "stroke-sentinel-green", emoji: "🟢" },
  warning:    { label: "Warning",        dot: "bg-yellow-400",     text: "text-yellow-400",     ring: "stroke-yellow-400",     emoji: "🟡" },
  critical:   { label: "Critical",       dot: "bg-sentinel-red",   text: "text-sentinel-red",   ring: "stroke-sentinel-red",   emoji: "🔴" },
  terminated: { label: "Auto-terminated", dot: "bg-sentinel-muted", text: "text-sentinel-muted", ring: "stroke-sentinel-muted", emoji: "⚫" },
}

/**
 * Map a score to a status bucket.
 *   >= 80          → clean
 *   60–79          → warning
 *   < 60           → critical
 * `terminated` is tracked separately (a terminated student keeps its status
 * regardless of score), so pass `terminated` to override.
 */
export function statusFromScore(score: number, terminated = false): TrustStatus {
  if (terminated) return "terminated"
  if (score >= 80) return "clean"
  if (score >= WARN_THRESHOLD) return "warning"
  return "critical"
}

// ── Per-student trust state ───────────────────────────────────────────────────

export interface ViolationEvent {
  type: ViolationType
  label: string
  ts: number          // epoch seconds
  deduction: number
}

export interface TrustState {
  score: number
  counts: Record<ViolationType, number>
  events: ViolationEvent[]   // full timeline, newest last
  flagged: boolean           // auto-flagged for post-exam review
  terminated: boolean
}

export function initialTrustState(): TrustState {
  return {
    score: 100,
    counts: { phone: 0, face_missing: 0, multiple_faces: 0, tab_switch: 0, window_blur: 0, copy_paste: 0 },
    events: [],
    flagged: false,
    terminated: false,
  }
}

const clamp = (n: number) => Math.max(0, Math.min(100, n))

/**
 * Apply one violation to a trust state, returning a NEW state (immutable).
 * Also records the event in the timeline and updates auto-flag bookkeeping.
 */
export function applyViolation(
  state: TrustState,
  type: ViolationType,
  ts: number = Date.now() / 1000,
): TrustState {
  const deduction = DEDUCTIONS[type]
  const counts = { ...state.counts, [type]: state.counts[type] + 1 }
  const event: ViolationEvent = { type, label: VIOLATION_LABELS[type], ts, deduction }
  const flagged = state.flagged || counts.phone >= PHONE_FLAG_COUNT
  const score = clamp(state.score - deduction)
  return {
    ...state,
    score,
    counts,
    events: [...state.events, event],
    flagged,
    terminated: state.terminated || score < TERMINATE_THRESHOLD,
  }
}

/** Apply one recovery tick (called every RECOVERY_INTERVAL_S of clean time). */
export function applyRecovery(state: TrustState): TrustState {
  if (state.terminated || state.score >= 100) return state
  return { ...state, score: clamp(state.score + RECOVERY_POINTS) }
}

/** Top-N violation types by count, for compact alert cards. */
export function topViolations(state: TrustState, n = 3): ViolationEvent[] {
  // Most-recent occurrence of each distinct violation, newest first.
  const seen = new Map<ViolationType, ViolationEvent>()
  for (const e of state.events) seen.set(e.type, e)
  return [...seen.values()].sort((a, b) => b.ts - a.ts).slice(0, n)
}
