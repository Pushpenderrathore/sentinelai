"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  type TrustState,
  type ViolationType,
  initialTrustState,
  applyViolation,
  applyRecovery,
  RECOVERY_INTERVAL_S,
} from "@/lib/trustScore"

/**
 * Maintains a student's trust state on the client.
 *
 * - `registerViolation(type)` deducts points and records the event.
 * - A background interval grants recovery (+1) for every RECOVERY_INTERVAL_S of
 *   clean time (no violation since the last recovery/violation).
 *
 * The hook is the single source of truth for the score; the exam page reads
 * `state` to drive auto-actions and to emit `trust_update` over the WebSocket.
 */
export function useTrustScore() {
  const [state, setState] = useState<TrustState>(initialTrustState)

  // Wall-clock of the last violation OR last recovery tick — recovery only
  // fires when a full clean interval has elapsed since this moment.
  const lastActivity = useRef<number>(Date.now())

  const registerViolation = useCallback((type: ViolationType, ts?: number) => {
    lastActivity.current = Date.now()
    setState((s) => applyViolation(s, type, ts ?? Date.now() / 1000))
  }, [])

  useEffect(() => {
    const id = setInterval(() => {
      const elapsed = (Date.now() - lastActivity.current) / 1000
      if (elapsed >= RECOVERY_INTERVAL_S) {
        lastActivity.current = Date.now()
        setState((s) => applyRecovery(s))
      }
    }, 1000)
    return () => clearInterval(id)
  }, [])

  return { state, registerViolation }
}
