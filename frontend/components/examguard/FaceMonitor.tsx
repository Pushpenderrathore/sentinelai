"use client"

import { useEffect, useRef, useState } from "react"

interface Props {
  onFaceEvent:   (faceCount: number, confidence: number) => void
  onPhoneEvent?: (confidence: number) => void
  active: boolean
}

type ModelStatus = "loading" | "ready" | "error"

// ── Canvas-based phone screen detector ──────────────────────────────────────
// Phone screens are distinctly bright and rectangular. This works without any
// ML model, loads instantly, and is highly reliable for webcam detection.
function detectPhoneScreen(video: HTMLVideoElement): number {
  if (video.readyState < 2) return 0

  // Downsample to 80×60 for speed (still enough for region detection)
  const W = 80, H = 60
  const offscreen = document.createElement("canvas")
  offscreen.width = W
  offscreen.height = H
  const ctx = offscreen.getContext("2d", { willReadFrequently: true })
  if (!ctx) return 0

  ctx.drawImage(video, 0, 0, W, H)
  const { data } = ctx.getImageData(0, 0, W, H)

  // Build luminance grid
  const lum = new Float32Array(W * H)
  for (let i = 0; i < W * H; i++) {
    const p = i * 4
    lum[i] = 0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2]
  }

  // Adaptive threshold: pixels brighter than (median + 0.45 * range)
  const sorted = Float32Array.from(lum).sort()
  const median  = sorted[Math.floor(sorted.length / 2)]
  const max     = sorted[sorted.length - 1]
  const range   = max - median
  if (range < 40) return 0  // scene too uniformly lit — no phone screen visible

  const threshold = median + range * 0.45

  // Find bounding box of bright pixels
  let minX = W, maxX = 0, minY = H, maxY = 0, brightCount = 0
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (lum[y * W + x] > threshold) {
        brightCount++
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
    }
  }

  const bboxW = maxX - minX + 1
  const bboxH = maxY - minY + 1
  if (bboxW < 4 || bboxH < 4) return 0

  // Fill ratio: how rectangular is the bright region? (phone screen = very high)
  const fillRatio = brightCount / (bboxW * bboxH)
  if (fillRatio < 0.45) return 0   // too scattered — not a solid screen

  // Aspect ratio: phone screens are 1.5:1 to 2.5:1 (portrait or landscape)
  const ar = Math.max(bboxW, bboxH) / Math.min(bboxW, bboxH)
  if (ar < 1.3 || ar > 3.2) return 0

  // Area ratio: phone screen should be 4–40% of frame
  const areaRatio = brightCount / (W * H)
  if (areaRatio < 0.03 || areaRatio > 0.45) return 0

  // Confidence score 0–1
  const confidence = Math.min(1, fillRatio * areaRatio * 12)
  return confidence
}

export default function FaceMonitor({ onFaceEvent, onPhoneEvent, active }: Props) {
  const videoRef    = useRef<HTMLVideoElement>(null)
  const canvasRef   = useRef<HTMLCanvasElement>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mpDetectorRef   = useRef<any>(null)
  const mpLoadingRef    = useRef(false)
  const onPhoneEventRef = useRef(onPhoneEvent)
  const onFaceEventRef  = useRef(onFaceEvent)

  useEffect(() => { onPhoneEventRef.current = onPhoneEvent }, [onPhoneEvent])
  useEffect(() => { onFaceEventRef.current  = onFaceEvent  }, [onFaceEvent])

  const [camError,     setCamError]     = useState<string | null>(null)
  const [streaming,    setStreaming]     = useState(false)
  const [modelStatus,  setModelStatus]  = useState<ModelStatus>("loading")
  const [faceCount,    setFaceCount]    = useState<number | null>(null)
  const [phoneVisible, setPhoneVisible] = useState(false)
  const [mpReady,      setMpReady]      = useState(false)

  // ── Load face-api once ─────────────────────────────────────
  useEffect(() => {
    if (!active) return
    let cancelled = false
    async function loadFace() {
      try {
        const faceapi = await import("@vladmandic/face-api")
        await faceapi.nets.tinyFaceDetector.loadFromUri("/models")
        if (!cancelled) setModelStatus("ready")
      } catch (e) {
        console.error("[FaceMonitor] face-api load failed:", e)
        if (!cancelled) setModelStatus("error")
      }
    }
    loadFace()
    return () => { cancelled = true }
  }, [active])

  // ── Load MediaPipe EfficientDet (secondary, enhances accuracy) ──
  useEffect(() => {
    if (!active || mpDetectorRef.current || mpLoadingRef.current) return
    mpLoadingRef.current = true

    async function loadMediaPipe() {
      try {
        const { ObjectDetector, FilesetResolver } = await import("@mediapipe/tasks-vision")
        const vision = await FilesetResolver.forVisionTasks("/mediapipe/wasm")
        mpDetectorRef.current = await ObjectDetector.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: "/mediapipe/efficientdet_lite0.tflite",
            delegate: "CPU",
          },
          scoreThreshold: 0.25,
          runningMode: "VIDEO",
        })
        setMpReady(true)
        console.log("[PhoneDetect] MediaPipe EfficientDet ready ✓")
      } catch (e) {
        console.error("[PhoneDetect] MediaPipe load failed (canvas detector still active):", e)
        mpLoadingRef.current = false
      }
    }
    loadMediaPipe()
  }, [active])

  // ── Start webcam once face model is ready ─────────────────
  useEffect(() => {
    if (!active || modelStatus !== "ready") return
    let stream: MediaStream | null = null

    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480, facingMode: "user" } })
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

  // ── Detection loop ─────────────────────────────────────────
  useEffect(() => {
    if (!streaming || modelStatus !== "ready") return

    // Consecutive-frame counter to avoid single-frame false positives
    let consecutivePhoneFrames = 0

    async function detect() {
      if (!videoRef.current) return
      try {
        const faceapi = await import("@vladmandic/face-api")

        // ── Face detection ─────────────────────────────
        const detections = await faceapi.detectAllFaces(
          videoRef.current,
          new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 }),
        )
        const count     = detections.length
        const bestScore = count > 0 ? Math.max(...detections.map((d) => d.score)) : 0
        setFaceCount(count)
        onFaceEventRef.current(count, parseFloat(bestScore.toFixed(2)))

        // ── Phone detection (canvas brightness + MediaPipe) ─
        type PhoneBox = { bbox: [number, number, number, number]; score: number }
        let phones: PhoneBox[] = []
        let canvasScore = 0

        // Primary: canvas brightness/rectangle detector (instant, no model needed)
        canvasScore = detectPhoneScreen(videoRef.current)
        if (canvasScore > 0.15) {
          phones.push({ bbox: [0, 0, 0, 0], score: canvasScore })
          console.log(`[PhoneDetect] canvas detector: score=${canvasScore.toFixed(3)}`)
        }

        // Secondary: MediaPipe EfficientDet (when loaded)
        if (mpDetectorRef.current && videoRef.current.readyState >= 2) {
          try {
            const result = mpDetectorRef.current.detectForVideo(videoRef.current, performance.now())
            for (const det of result.detections) {
              for (const cat of det.categories) {
                if (cat.categoryName === "cell phone" || cat.categoryName === "remote") {
                  const b = det.boundingBox
                  phones.push({ bbox: [b.originX, b.originY, b.width, b.height], score: cat.score })
                  console.log(`[PhoneDetect] MediaPipe: ${cat.categoryName} @ ${cat.score.toFixed(2)}`)
                  break
                }
              }
            }
          } catch { /* MediaPipe not yet ready or frame timing issue */ }
        }

        // Require 2 consecutive frames to confirm (reduces false positives)
        if (phones.length > 0) {
          consecutivePhoneFrames++
        } else {
          consecutivePhoneFrames = 0
        }

        const confirmed = consecutivePhoneFrames >= 2

        if (confirmed) {
          setPhoneVisible(true)
          const best = Math.max(...phones.map((p) => p.score))
          onPhoneEventRef.current?.(parseFloat(best.toFixed(2)))
        } else {
          setPhoneVisible(false)
        }

        // ── Draw overlays ──────────────────────────────
        if (canvasRef.current && videoRef.current) {
          const dims = {
            width:  videoRef.current.videoWidth  || 640,
            height: videoRef.current.videoHeight || 480,
          }
          faceapi.matchDimensions(canvasRef.current, dims)
          const resized = faceapi.resizeResults(detections, dims)
          const ctx = canvasRef.current.getContext("2d")
          if (ctx) {
            ctx.clearRect(0, 0, dims.width, dims.height)

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

            // Draw phone bounding boxes from MediaPipe (canvas detector has no box)
            phones
              .filter((p) => p.bbox[2] > 0)
              .forEach(({ bbox }) => {
                const [x, y, w, h] = bbox
                ctx.strokeStyle = "#ef4444"
                ctx.lineWidth   = 2
                ctx.strokeRect(x, y, w, h)
                ctx.fillStyle = "#ef4444"
                ctx.font = "bold 11px monospace"
                ctx.fillText("PHONE", x + 4, y - 4)
              })
          }
        }
      } catch (e) {
        console.warn("[FaceMonitor] detection frame failed:", e)
      }
    }

    intervalRef.current = setInterval(detect, 1500)
    detect()
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [streaming, modelStatus])

  // ── Render ────────────────────────────────────────────────

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
        <video ref={videoRef} muted playsInline className="w-full h-full object-cover scale-x-[-1]" />
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full scale-x-[-1] pointer-events-none" />

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

        {streaming && !mpReady && (
          <div className="absolute bottom-2 right-2 bg-black/60 rounded-full px-2 py-1">
            <span className="text-[10px] font-mono text-yellow-400">📱 enhancing…</span>
          </div>
        )}

        {streaming && phoneVisible && (
          <div className="absolute top-2 left-2 bg-red-600/90 rounded-full px-2 py-1 animate-pulse">
            <span className="text-[10px] font-mono text-white">📱 PHONE</span>
          </div>
        )}
      </div>
    </div>
  )
}
