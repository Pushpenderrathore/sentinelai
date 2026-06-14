"use client"

import { useEffect, useState } from "react"

interface Props {
  /** Bump this key (e.g. a counter) each time you want a toast to appear. */
  triggerKey: number
  message: string
  /** Auto-dismiss after this many ms (default 6000). */
  duration?: number
  tone?: "warning" | "critical"
}

/**
 * Transient toast shown to the student when their trust score crosses a
 * threshold. Re-fires whenever `triggerKey` changes. Styled for the student
 * exam page (light surface), not the dark host theme.
 */
export default function WarningToast({ triggerKey, message, duration = 6000, tone = "warning" }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (triggerKey <= 0) return
    setVisible(true)
    const t = setTimeout(() => setVisible(false), duration)
    return () => clearTimeout(t)
  }, [triggerKey, duration])

  if (!visible) return null

  const palette =
    tone === "critical"
      ? "bg-red-600 text-white border-red-700"
      : "bg-amber-50 text-amber-900 border-amber-300"

  return (
    <div
      role="alert"
      className={`fixed top-5 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-3
                  max-w-md rounded-xl border px-5 py-3 shadow-lg
                  animate-slide-in ${palette}`}
    >
      <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
      <p className="text-sm font-medium leading-snug">{message}</p>
    </div>
  )
}
