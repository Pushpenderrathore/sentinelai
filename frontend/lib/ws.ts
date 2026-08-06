"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export type WSStatus = "connecting" | "open" | "closed" | "error"

export interface WSMessage {
  type: string
  [key: string]: unknown
}

/**
 * Generic WebSocket hook.
 * - `url` — full WebSocket URL (use a secure `wss` scheme in production);
 *   pass null to skip connection
 * - `onMessage` — optional callback for every non-ping message
 */
export function useWebSocket(
  url: string | null,
  onMessage?: (msg: WSMessage) => void,
) {
  const [status, setStatus]     = useState<WSStatus>("connecting")
  const [messages, setMessages] = useState<WSMessage[]>([])
  const wsRef  = useRef<WebSocket | null>(null)
  const cbRef  = useRef(onMessage)
  cbRef.current = onMessage

  useEffect(() => {
    if (!url) return
    const ws = new WebSocket(url)
    wsRef.current = ws
    setStatus("connecting")

    ws.onopen    = () => setStatus("open")
    ws.onclose   = () => setStatus("closed")
    ws.onerror   = () => setStatus("error")
    ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data)
      if (msg.type === "ping" || msg.type === "pong") return
      setMessages((prev) => [...prev, msg])
      cbRef.current?.(msg)
    }

    return () => { ws.close(); wsRef.current = null }
  }, [url])

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const reset = useCallback(() => setMessages([]), [])

  return { status, messages, send, reset }
}
