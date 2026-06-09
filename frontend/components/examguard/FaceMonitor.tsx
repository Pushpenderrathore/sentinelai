"use client"

import { useEffect, useRef, useState } from "react"

interface Props {
  onFaceEvent:  (faceCount: number, confidence: number) => void
  onPhoneEvent?: (confidence: number) => void
  active: boolean
}

type ModelStatus = "loading" | "ready" | "error"

export default function FaceMonitor({ onFaceEvent, onPhoneEvent, active }: Props) {
  const videoRef    = useRef<HTMLVideoElement>(null)
  const canvasRef   = useRef<HTMLCanvasElement>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [camError,     setCamError]     = useState<string | null>(null)
  const [streaming,    setStreaming]     = useState(false)
  const [modelStatus,  setModelStatus]  = useState<ModelStatus>("loading")
  const [faceCount,    setFaceCount]    = useState<number | null>(null)
  const [phoneVisible, setPhoneVisible] = useState(false)

  // Load face-api + coco-ssd models once
  useEffect(() => {
    if (!active) return
    let cancelled = false

    async function loadModels() {
      try {
        const faceapi = await import("@vladmandic/face-api")
        await faceapi.nets.tinyFaceDetector.loadFromUri("/models")
        // Load coco-ssd (lazy — doesn't block face detection)
        await import("@tensorflow-models/coco-ssd")
        if (!cancelled) setModelStatus("ready")
      } catch (e) {
        console.error("model load failed:", e)
        if (!cancelled) setModelStatus("error")
      }
    }

    loadModels()
    return () => { cancelled = true }
  }, [active])

  // Start webcam once model is ready
  useEffect(() => {
    if (!active || modelStatus !== "ready") return
    let stream: MediaStream | null = null

    navigator.mediaDevices
      .getUserMedia({ video: { width: 320, height: 240, facingMode: "user" } })
      .then((s) => {
        stream = s
        if (videoRef.current) {
          videoRef.current.srcObject = s
          videoRef.current.play()
          setStreaming(true)
        }
      })
      .catch(() => setCamError("Camera access denied"))

    return () => {
      stream?.getTracks().forEach((t) => t.stop())
      setStreaming(false)
    }
  }, [active, modelStatus])

  // Run detection every 3 s once streaming
  useEffect(() => {
    if (!streaming || modelStatus !== "ready") return

    // Load coco-ssd detector once and reuse
    let cocoDetector: Awaited<ReturnType<typeof import("@tensorflow-models/coco-ssd")["load"]>> | null = null
    import("@tensorflow-models/coco-ssd").then((m) => m.load()).then((d) => { cocoDetector = d })

    async function detect() {
      if (!videoRef.current) return

      try {
        // ── Face detection ──────────────────────────────────────
        const faceapi = await import("@vladmandic/face-api")
        const detections = await faceapi.detectAllFaces(
          videoRef.current,
          new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 })
        )

        const count = detections.length
        const bestScore = count > 0
          ? Math.max(...detections.map((d) => d.score))
          : 0

        setFaceCount(count)
        onFaceEvent(count, parseFloat(bestScore.toFixed(2)))

        // ── Phone detection ─────────────────────────────────────
        let phoneScore = 0
        if (cocoDetector) {
          const objects = await cocoDetector.detect(videoRef.current)
          const phones  = objects.filter((o) => o.class === "cell phone")
          if (phones.length > 0) {
            phoneScore = Math.max(...phones.map((p) => p.score))
            setPhoneVisible(true)
            if (onPhoneEvent) onPhoneEvent(parseFloat(phoneScore.toFixed(2)))
          } else {
            setPhoneVisible(false)
          }
        }

        // ── Draw bounding boxes ─────────────────────────────────
        if (canvasRef.current && videoRef.current) {
          const dims = {
            width:  videoRef.current.videoWidth  || 320,
            height: videoRef.current.videoHeight || 240,
          }
          faceapi.matchDimensions(canvasRef.current, dims)
          const resized = faceapi.resizeResults(detections, dims)
          const ctx = canvasRef.current.getContext("2d")
          if (ctx) {
            ctx.clearRect(0, 0, dims.width, dims.height)

            // Face boxes
            resized.forEach((d) => {
              const { x, y, width, height } = d.box
              const color = count === 1 ? "#22d3ee" : count === 0 ? "#f87171" : "#fb923c"
              ctx.strokeStyle = color
              ctx.lineWidth   = 2
              ctx.strokeRect(x, y, width, height)
              ctx.fillStyle = color
              ctx.font = "11px monospace"
              ctx.fillText(`${(d.score * 100).toFixed(0)}%`, x + 4, y - 4)
            })

            // Phone boxes (red)
            if (cocoDetector) {
              const objects = await cocoDetector.detect(videoRef.current)
              objects
                .filter((o) => o.class === "cell phone")
                .forEach(({ bbox }) => {
                  const [x, y, w, h] = bbox
                  ctx.strokeStyle = "#ef4444"
                  ctx.lineWidth   = 2
                  ctx.strokeRect(x, y, w, h)
                  ctx.fillStyle = "#ef4444"
                  ctx.font = "11px monospace"
                  ctx.fillText("📱 phone", x + 4, y - 4)
                })
            }
          }
        }
      } catch (e) {
        console.warn("Detection frame failed:", e)
      }
    }

    intervalRef.current = setInterval(detect, 3000)
    detect()

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [streaming, modelStatus, onFaceEvent, onPhoneEvent])

  // ── Render ───────────────────────────────────────────────────

  if (camError) {
    return (
      <div className="aspect-video rounded-xl bg-sentinel-surface border border-sentinel-border flex flex-col items-center justify-center gap-2">
        <svg className="w-8 h-8 text-sentinel-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"/>
        </svg>
        <p className="text-sentinel-muted text-xs">{camError}</p>
      </div>
    )
  }

  const faceStatusColor =
    faceCount === null ? "text-sentinel-muted" :
    faceCount === 1    ? "text-sentinel-green"  :
    faceCount === 0    ? "text-sentinel-red"    : "text-orange-400"

  const faceStatusText =
    faceCount === null ? "—" :
    faceCount === 0    ? "No face" :
    faceCount === 1    ? "1 face" : `${faceCount} faces (!)`

  return (
    <div className="space-y-1">
      <div className="relative aspect-video rounded-xl overflow-hidden bg-black border border-sentinel-border">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full h-full object-cover scale-x-[-1]"
        />

        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full scale-x-[-1] pointer-events-none"
        />

        {!streaming && modelStatus === "loading" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-sentinel-surface">
            <svg className="w-5 h-5 animate-spin text-sentinel-muted" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <p className="text-xs text-sentinel-muted font-mono">Loading AI model…</p>
          </div>
        )}

        {modelStatus === "error" && (
          <div className="absolute inset-0 flex items-center justify-center bg-sentinel-surface">
            <p className="text-xs text-sentinel-red font-mono">Face model failed to load</p>
          </div>
        )}

        {streaming && (
          <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-black/60 rounded-full px-2 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-sentinel-green animate-pulse" />
            <span className="text-[10px] font-mono text-sentinel-green">LIVE</span>
          </div>
        )}

        {streaming && faceCount !== null && (
          <div className="absolute bottom-2 left-2 bg-black/60 rounded-full px-2 py-1">
            <span className={`text-[10px] font-mono ${faceStatusColor}`}>{faceStatusText}</span>
          </div>
        )}

        {/* Phone warning badge */}
        {streaming && phoneVisible && (
          <div className="absolute top-2 left-2 bg-red-600/90 rounded-full px-2 py-1 animate-pulse">
            <span className="text-[10px] font-mono text-white">📱 PHONE</span>
          </div>
        )}
      </div>
    </div>
  )
}
