"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import FaceMonitor from "@/components/examguard/FaceMonitor"
import { useWebSocket } from "@/lib/ws"
import { getExamSession } from "@/lib/api"

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"

const SAMPLE_QUESTIONS = [
  {
    n: 1,
    text: "Explain the time complexity of QuickSort in the average and worst case. Why is the average case O(n log n) while the worst case is O(n²)?",
  },
  {
    n: 2,
    text: "What is a deadlock? Describe the four necessary Coffman conditions for a deadlock to occur and explain one prevention strategy for each.",
  },
  {
    n: 3,
    text: "Write pseudocode for Dijkstra's shortest path algorithm. Analyse its time complexity using a min-heap and an adjacency list representation.",
  },
]

export default function StudentExamPage({ params }: { params: { id: string } }) {
  const { id: examId } = params
  const wsUrl = `${WS_BASE}/ws/exam/${examId}`

  const { status, send } = useWebSocket(wsUrl)

  const [currentQ,    setCurrentQ]    = useState(0)
  const [answers,     setAnswers]     = useState<Record<number, string>>({})
  const [timeLeft,    setTimeLeft]    = useState(60 * 60)
  const [tabCount,    setTabCount]    = useState(0)
  const [submitted,   setSubmitted]   = useState(false)
  const [terminated,  setTerminated]  = useState(false)

  const TAB_LIMIT = 5

  // Fetch real duration from session on mount
  useEffect(() => {
    getExamSession(examId).then((s) => setTimeLeft(s.duration_minutes * 60)).catch(() => {})
  }, [examId])

  const lastKeystroke = useRef<number>(Date.now())
  const keystrokeCount = useRef(0)
  const wpmSamples    = useRef<number[]>([])

  // ── Auto-terminate on tab limit ───────────────────────────
  useEffect(() => {
    if (tabCount >= TAB_LIMIT && !submitted && !terminated) {
      send({ type: "end_exam", timestamp: Date.now() / 1000 })
      setTerminated(true)
    }
  }, [tabCount, submitted, terminated, send])

  // ── Countdown ────────────────────────────────────────────
  useEffect(() => {
    if (submitted || terminated) return
    const t = setInterval(() => setTimeLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [submitted, terminated])

  function formatTime(s: number) {
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
  }

  // ── Tab visibility tracking ───────────────────────────────
  useEffect(() => {
    if (submitted || terminated || status !== "open") return

    function onVisibilityChange() {
      const ts = Date.now() / 1000
      const evType = document.hidden ? "hidden" : "visible"
      send({ type: "tab_event", event_type: evType, timestamp: ts })
      if (document.hidden) setTabCount((c) => c + 1)
    }

    function onBlur() {
      send({ type: "tab_event", event_type: "blur", timestamp: Date.now() / 1000 })
    }

    document.addEventListener("visibilitychange", onVisibilityChange)
    window.addEventListener("blur", onBlur)
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange)
      window.removeEventListener("blur", onBlur)
    }
  }, [status, submitted, terminated, send])

  // ── Keystroke tracking ────────────────────────────────────
  function handleKeydown() {
    const now = Date.now()
    const gap = now - lastKeystroke.current
    keystrokeCount.current += 1

    if (gap > 0 && gap < 2000) {
      const wpm = (1 / (gap / 1000)) * 60 / 5
      wpmSamples.current.push(Math.min(wpm, 300))
    }

    lastKeystroke.current = now

    // Flush keystroke stats every 20 keystrokes
    if (keystrokeCount.current % 20 === 0 && wpmSamples.current.length > 0) {
      const samples = wpmSamples.current
      const avg = samples.reduce((a, b) => a + b, 0) / samples.length
      const std = Math.sqrt(samples.map((x) => (x - avg) ** 2).reduce((a, b) => a + b, 0) / samples.length)
      send({
        type: "keystroke_stats",
        avg_wpm: Math.round(avg),
        std_wpm: Math.round(std),
        pause_count: samples.filter((v) => v < 5).length,
        burst_count: samples.filter((v) => v > 120).length,
        total_keystrokes: keystrokeCount.current,
        timestamp: Date.now() / 1000,
      })
      wpmSamples.current = []
    }
  }

  // ── Copy-paste detection ──────────────────────────────────
  function handlePaste(e: React.ClipboardEvent) {
    const len = e.clipboardData.getData("text").length
    send({ type: "copy_paste", content_length: len, timestamp: Date.now() / 1000 })
  }

  // ── Face event forwarding ─────────────────────────────────
  const onFaceEvent = useCallback(
    (faceCount: number, confidence: number) => {
      if (status === "open") {
        send({ type: "face_event", face_count: faceCount, confidence, timestamp: Date.now() / 1000 })
      }
    },
    [status, send],
  )

  // ── Phone detection — unused (YOLOv8 backend now handles it) ─
  const onPhoneEvent = useCallback((_confidence: number) => {}, [])

  // ── Send video frame to backend for YOLOv8 phone detection ──
  const sendFrame = useCallback(
    ({ jpeg_b64 }: { jpeg_b64: string }) => {
      if (status === "open") {
        send({ type: "video_frame", image: jpeg_b64, timestamp: Date.now() / 1000 })
      }
    },
    [status, send],
  )

  // ── Submit ────────────────────────────────────────────────
  function handleSubmit() {
    send({ type: "end_exam", timestamp: Date.now() / 1000 })
    setSubmitted(true)
  }

  if (terminated) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6 bg-[#f8f9fc]">
        <div className="w-16 h-16 rounded-full bg-red-100 border-2 border-red-400 flex items-center justify-center mb-5">
          <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-red-600 mb-2">Exam Terminated</h2>
        <p className="text-slate-600 text-sm max-w-sm leading-relaxed">
          Your exam has been automatically terminated due to <strong>repeated tab switching ({TAB_LIMIT}+ times)</strong>.
          This session has been flagged and the invigilator has been notified.
        </p>
        <div className="mt-5 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 max-w-sm">
          Tab switches detected: <strong>{tabCount}</strong> — limit is {TAB_LIMIT}
        </div>
        <p className="mt-5 text-xs font-mono text-slate-400">Session: {examId}</p>
      </div>
    )
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6">
        <div className="w-14 h-14 rounded-full bg-sentinel-green/10 border border-sentinel-green/30 flex items-center justify-center mb-4">
          <svg className="w-7 h-7 text-sentinel-green" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        </div>
        <h2 className="text-2xl font-bold mb-2">Exam Submitted</h2>
        <p className="text-sentinel-muted text-sm max-w-sm">
          Your responses have been saved. The invigilator will receive an AI integrity report shortly.
        </p>
        <p className="mt-4 text-xs font-mono text-sentinel-muted">Session: {examId}</p>
      </div>
    )
  }

  const q = SAMPLE_QUESTIONS[currentQ]

  return (
    <div className="min-h-screen bg-[#f8f9fc] text-slate-800 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 flex items-center gap-4 px-6 py-3 bg-white border-b border-slate-200 shadow-sm">
        <div className="flex-1">
          <h1 className="text-sm font-semibold text-slate-700">Proctored Examination</h1>
          <p className="text-xs text-slate-400 font-mono">Session: {examId}</p>
        </div>

        {/* Timer */}
        <div className={`font-mono text-lg font-bold tabular-nums ${timeLeft < 300 ? "text-red-500" : "text-slate-700"}`}>
          {formatTime(timeLeft)}
        </div>

        {/* Monitoring indicator */}
        <div className="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-full px-3 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Monitored
        </div>

        {/* Hidden camera feed */}
        <div className="w-20 rounded-lg overflow-hidden">
          <FaceMonitor onFaceEvent={onFaceEvent} onPhoneEvent={onPhoneEvent} sendFrame={sendFrame} active={status === "open"} />
        </div>
      </header>

      {/* Body */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-10">
        {/* Question nav */}
        <div className="flex gap-2 mb-8">
          {SAMPLE_QUESTIONS.map((sq, i) => (
            <button
              key={i}
              onClick={() => setCurrentQ(i)}
              className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
                i === currentQ
                  ? "bg-indigo-600 text-white"
                  : answers[i]
                  ? "bg-indigo-100 text-indigo-700"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {/* Question */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full">
              Question {q.n}
            </span>
            <span className="text-xs text-slate-400">10 marks</span>
          </div>
          <p className="text-slate-700 leading-relaxed">{q.text}</p>
        </div>

        {/* Answer */}
        <textarea
          rows={12}
          value={answers[currentQ] ?? ""}
          onChange={(e) => setAnswers((a) => ({ ...a, [currentQ]: e.target.value }))}
          onKeyDown={handleKeydown}
          onPaste={handlePaste}
          placeholder="Write your answer here…"
          className="w-full px-5 py-4 bg-white border border-slate-200 rounded-2xl text-sm leading-relaxed
                     text-slate-800 placeholder:text-slate-400 resize-none shadow-sm
                     focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100
                     transition-all"
        />

        {/* Navigation */}
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => setCurrentQ((q) => Math.max(0, q - 1))}
            disabled={currentQ === 0}
            className="px-5 py-2 text-sm rounded-xl border border-slate-200 text-slate-600
                       hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            ← Previous
          </button>

          {currentQ < SAMPLE_QUESTIONS.length - 1 ? (
            <button
              onClick={() => setCurrentQ((q) => q + 1)}
              className="px-5 py-2 text-sm rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
            >
              Next →
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              className="px-6 py-2 text-sm rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 font-medium transition-colors"
            >
              Submit Exam
            </button>
          )}
        </div>
      </main>

      {/* Warning banner — top-right corner, away from question area and camera */}
      {tabCount > 0 && (
        <div className={`fixed top-20 right-4 max-w-xs flex items-start gap-2
                        text-xs rounded-xl px-4 py-2.5 shadow-lg z-50 transition-colors
                        ${tabCount >= TAB_LIMIT - 1
                          ? "bg-red-50 border border-red-400 text-red-700 font-semibold"
                          : "bg-yellow-50 border border-yellow-300 text-yellow-800"}`}>
          <span className="mt-0.5 shrink-0">{tabCount >= TAB_LIMIT - 1 ? "⚠️" : "⚠"}</span>
          <span>
            {tabCount >= TAB_LIMIT - 1
              ? `WARNING: ${tabCount}/${TAB_LIMIT} tab switches — one more will terminate your exam!`
              : `Tab switching detected (${tabCount}×) — this session is being monitored.`}
          </span>
        </div>
      )}
    </div>
  )
}
