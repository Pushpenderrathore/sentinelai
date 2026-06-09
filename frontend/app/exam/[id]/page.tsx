"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import FaceMonitor from "@/components/examguard/FaceMonitor"
import { useWebSocket } from "@/lib/ws"
import { getExamSession } from "@/lib/api"
import { QUESTION_BANK, type MCQ, type SubjectBank } from "@/lib/questionBank"

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"

const COLOR_MAP: Record<string, { badge: string; border: string; bg: string; text: string }> = {
  indigo:  { badge: "bg-indigo-100 text-indigo-700",  border: "border-indigo-300",  bg: "bg-indigo-50",  text: "text-indigo-700"  },
  red:     { badge: "bg-red-100 text-red-700",        border: "border-red-300",     bg: "bg-red-50",     text: "text-red-700"     },
  violet:  { badge: "bg-violet-100 text-violet-700",  border: "border-violet-300",  bg: "bg-violet-50",  text: "text-violet-700"  },
  amber:   { badge: "bg-amber-100 text-amber-700",    border: "border-amber-300",   bg: "bg-amber-50",   text: "text-amber-700"   },
  cyan:    { badge: "bg-cyan-100 text-cyan-700",      border: "border-cyan-300",    bg: "bg-cyan-50",    text: "text-cyan-700"    },
  teal:    { badge: "bg-teal-100 text-teal-700",      border: "border-teal-300",    bg: "bg-teal-50",    text: "text-teal-700"    },
  orange:  { badge: "bg-orange-100 text-orange-700",  border: "border-orange-300",  bg: "bg-orange-50",  text: "text-orange-700"  },
  emerald: { badge: "bg-emerald-100 text-emerald-700",border: "border-emerald-300", bg: "bg-emerald-50", text: "text-emerald-700" },
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

interface ShuffledMCQ extends MCQ {
  shuffledOptions: string[]
  correctShuffled: number
}

function prepareQuestions(bank: SubjectBank): ShuffledMCQ[] {
  return shuffle(bank.questions).map((q) => {
    const indexed = q.options.map((opt, i) => ({ opt, isCorrect: i === q.correct }))
    const shuffled = shuffle(indexed)
    return {
      ...q,
      shuffledOptions: shuffled.map((x) => x.opt) as [string, string, string, string],
      correctShuffled: shuffled.findIndex((x) => x.isCorrect),
    }
  })
}

export default function StudentExamPage({ params }: { params: { id: string } }) {
  const { id: examId } = params
  const { status, send } = useWebSocket(`${WS_BASE}/ws/exam/${examId}`)

  const [selectedSubject, setSelectedSubject] = useState<SubjectBank | null>(null)
  const [questions,   setQuestions]   = useState<ShuffledMCQ[]>([])
  const [currentQ,    setCurrentQ]    = useState(0)
  const [answers,     setAnswers]     = useState<Record<number, number>>({})  // question index → chosen option index
  const [timeLeft,    setTimeLeft]    = useState(60 * 60)
  const [tabCount,    setTabCount]    = useState(0)
  const [submitted,   setSubmitted]   = useState(false)
  const [terminated,  setTerminated]  = useState(false)

  const TAB_LIMIT = 5

  useEffect(() => {
    getExamSession(examId).then((s) => setTimeLeft(s.duration_minutes * 60)).catch(() => {})
  }, [examId])

  useEffect(() => {
    if (tabCount >= TAB_LIMIT && !submitted && !terminated) {
      send({ type: "end_exam", timestamp: Date.now() / 1000 })
      setTerminated(true)
    }
  }, [tabCount, submitted, terminated, send])

  useEffect(() => {
    if (submitted || terminated) return
    const t = setInterval(() => setTimeLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [submitted, terminated])

  function formatTime(s: number) {
    const h   = Math.floor(s / 3600)
    const m   = Math.floor((s % 3600) / 60)
    const sec = s % 60
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
  }

  useEffect(() => {
    if (!selectedSubject || submitted || terminated || status !== "open") return
    function onVisibilityChange() {
      const ts = Date.now() / 1000
      send({ type: "tab_event", event_type: document.hidden ? "hidden" : "visible", timestamp: ts })
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
  }, [selectedSubject, status, submitted, terminated, send])

  const lastKeystroke  = useRef<number>(Date.now())
  const keystrokeCount = useRef(0)
  const wpmSamples     = useRef<number[]>([])

  function handleKeydown() {
    const now = Date.now()
    const gap = now - lastKeystroke.current
    keystrokeCount.current += 1
    if (gap > 0 && gap < 2000) wpmSamples.current.push(Math.min((1 / (gap / 1000)) * 60 / 5, 300))
    lastKeystroke.current = now
    if (keystrokeCount.current % 20 === 0 && wpmSamples.current.length > 0) {
      const s   = wpmSamples.current
      const avg = s.reduce((a, b) => a + b, 0) / s.length
      const std = Math.sqrt(s.map((x) => (x - avg) ** 2).reduce((a, b) => a + b, 0) / s.length)
      send({ type: "keystroke_stats", avg_wpm: Math.round(avg), std_wpm: Math.round(std),
             pause_count: s.filter((v) => v < 5).length, burst_count: s.filter((v) => v > 120).length,
             total_keystrokes: keystrokeCount.current, timestamp: Date.now() / 1000 })
      wpmSamples.current = []
    }
  }

  const onFaceEvent = useCallback(
    (faceCount: number, confidence: number) => {
      if (status === "open") send({ type: "face_event", face_count: faceCount, confidence, timestamp: Date.now() / 1000 })
    },
    [status, send],
  )
  const onPhoneEvent = useCallback((_: number) => {}, [])
  const sendFrame = useCallback(
    ({ jpeg_b64 }: { jpeg_b64: string }) => {
      if (status === "open") send({ type: "video_frame", image: jpeg_b64, timestamp: Date.now() / 1000 })
    },
    [status, send],
  )

  function handleSelectSubject(sub: SubjectBank) {
    setSelectedSubject(sub)
    setQuestions(prepareQuestions(sub))
    setCurrentQ(0)
    setAnswers({})
  }

  function handleSubmit() {
    send({ type: "end_exam", timestamp: Date.now() / 1000 })
    setSubmitted(true)
  }

  // ── Terminated ───────────────────────────────────────────────
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
          Your exam was automatically terminated due to <strong>repeated tab switching ({TAB_LIMIT}+ times)</strong>.
          This session has been flagged.
        </p>
        <div className="mt-5 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 max-w-sm">
          Tab switches: <strong>{tabCount}</strong> — limit is {TAB_LIMIT}
        </div>
        <p className="mt-5 text-xs font-mono text-slate-400">Session: {examId}</p>
      </div>
    )
  }

  // ── Submitted — show score ────────────────────────────────────
  if (submitted) {
    const correct = questions.filter((q, i) => answers[i] === q.correctShuffled).length
    const total   = questions.length
    const pct     = total > 0 ? Math.round((correct / total) * 100) : 0
    const grade   = pct >= 90 ? "A" : pct >= 75 ? "B" : pct >= 60 ? "C" : pct >= 45 ? "D" : "F"
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center px-6 bg-[#f8f9fc]">
        <div className="w-16 h-16 rounded-full bg-emerald-100 border-2 border-emerald-400 flex items-center justify-center mb-5">
          <svg className="w-8 h-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        </div>
        <h2 className="text-2xl font-bold mb-1">Exam Submitted</h2>
        <p className="text-slate-500 text-sm mb-6">Your responses have been saved.</p>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm w-64 mb-4">
          <p className="text-5xl font-bold text-indigo-600 mb-1">{pct}%</p>
          <p className="text-slate-500 text-sm">{correct} / {total} correct</p>
          <div className={`mt-3 inline-block px-3 py-1 rounded-full text-sm font-bold
                          ${grade === "A" ? "bg-emerald-100 text-emerald-700" :
                            grade === "B" ? "bg-blue-100 text-blue-700" :
                            grade === "C" ? "bg-yellow-100 text-yellow-700" :
                            grade === "D" ? "bg-orange-100 text-orange-700" :
                                            "bg-red-100 text-red-700"}`}>
            Grade {grade}
          </div>
        </div>

        {/* Answer review */}
        <div className="w-full max-w-xl text-left space-y-3 mb-6">
          {questions.map((q, i) => {
            const chosen  = answers[i]
            const isRight = chosen === q.correctShuffled
            return (
              <div key={q.id} className={`rounded-xl border px-4 py-3 text-sm ${isRight ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
                <p className={`font-medium mb-1 ${isRight ? "text-emerald-800" : "text-red-800"}`}>
                  {isRight ? "✓" : "✗"} Q{i + 1}: {q.text}
                </p>
                {!isRight && chosen !== undefined && (
                  <p className="text-xs text-red-600">Your answer: {q.shuffledOptions[chosen]}</p>
                )}
                {!isRight && (
                  <p className="text-xs text-emerald-700 font-medium">Correct: {q.shuffledOptions[q.correctShuffled]}</p>
                )}
              </div>
            )
          })}
        </div>

        <p className="text-xs font-mono text-slate-400">Session: {examId}</p>
      </div>
    )
  }

  const cameraWidget = (
    <div className="w-20 rounded-lg overflow-hidden">
      <FaceMonitor onFaceEvent={onFaceEvent} onPhoneEvent={onPhoneEvent} sendFrame={sendFrame} active={status === "open"} />
    </div>
  )

  // ── Subject selector ─────────────────────────────────────────
  if (!selectedSubject) {
    return (
      <div className="min-h-screen bg-[#f8f9fc] flex flex-col">
        <header className="flex items-center gap-4 px-6 py-4 bg-white border-b border-slate-200 shadow-sm">
          <div className="flex-1">
            <h1 className="text-sm font-semibold text-slate-700">Proctored Examination</h1>
            <p className="text-xs text-slate-400 font-mono">Session: {examId}</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-full px-3 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Monitored
          </div>
          {cameraWidget}
        </header>

        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-10">
          <div className="mb-8 text-center">
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Select Your Subject</h2>
            <p className="text-slate-500 text-sm">
              Choose a subject to begin. Questions are randomised every session. You cannot change your subject once started.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {QUESTION_BANK.map((sub) => (
              <button
                key={sub.id}
                onClick={() => handleSelectSubject(sub)}
                className="flex flex-col items-center gap-3 p-5 rounded-2xl border-2 border-slate-200 bg-white
                           text-center transition-all hover:scale-105 hover:shadow-md hover:border-indigo-300
                           hover:bg-indigo-50 active:scale-100 group"
              >
                <span className="text-3xl">{sub.icon}</span>
                <div>
                  <p className="text-xs font-semibold text-slate-700 group-hover:text-indigo-700 leading-tight">
                    {sub.label}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1">{sub.questions.length} questions · MCQ</p>
                </div>
              </button>
            ))}
          </div>

          <p className="mt-8 text-center text-xs text-slate-400">
            Timer and monitoring start immediately after subject selection.
          </p>
        </main>
      </div>
    )
  }

  // ── Exam ─────────────────────────────────────────────────────
  const c = COLOR_MAP[selectedSubject.color]
  const q = questions[currentQ]
  const answered = Object.keys(answers).length

  return (
    <div className="min-h-screen bg-[#f8f9fc] text-slate-800 flex flex-col">
      <header className="sticky top-0 z-10 flex items-center gap-4 px-6 py-3 bg-white border-b border-slate-200 shadow-sm">
        <div className="flex-1">
          <h1 className="text-sm font-semibold text-slate-700">
            {selectedSubject.icon} {selectedSubject.label}
          </h1>
          <p className="text-xs text-slate-400 font-mono">Session: {examId}</p>
        </div>

        <div className={`font-mono text-lg font-bold tabular-nums ${timeLeft < 300 ? "text-red-500" : "text-slate-700"}`}>
          {formatTime(timeLeft)}
        </div>

        <span className="text-xs text-slate-500 font-mono">{answered}/{questions.length} answered</span>

        <div className="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-full px-3 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          Monitored
        </div>

        {cameraWidget}
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-6 py-10" onKeyDown={handleKeydown}>
        {/* Question nav */}
        <div className="flex flex-wrap gap-2 mb-8">
          {questions.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentQ(i)}
              className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
                i === currentQ
                  ? "bg-indigo-600 text-white"
                  : answers[i] !== undefined
                  ? "bg-indigo-100 text-indigo-700"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {/* Question card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${c.badge}`}>
              Question {currentQ + 1} of {questions.length}
            </span>
            <span className="text-xs text-slate-400">1 mark</span>
          </div>
          <p className="text-slate-700 leading-relaxed font-medium">{q.text}</p>
        </div>

        {/* Options */}
        <div className="space-y-3 mb-8">
          {q.shuffledOptions.map((opt, oi) => {
            const selected = answers[currentQ] === oi
            return (
              <button
                key={oi}
                onClick={() => setAnswers((a) => ({ ...a, [currentQ]: oi }))}
                className={`w-full text-left flex items-center gap-4 px-5 py-4 rounded-xl border-2 transition-all
                            ${selected
                              ? `${c.bg} ${c.border} ${c.text} font-medium`
                              : "bg-white border-slate-200 text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                            }`}
              >
                <span className={`w-6 h-6 shrink-0 rounded-full border-2 flex items-center justify-center text-xs font-bold
                                  ${selected ? `${c.border} ${c.text}` : "border-slate-300 text-slate-400"}`}>
                  {String.fromCharCode(65 + oi)}
                </span>
                <span className="text-sm">{opt}</span>
              </button>
            )
          })}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setCurrentQ((q) => Math.max(0, q - 1))}
            disabled={currentQ === 0}
            className="px-5 py-2 text-sm rounded-xl border border-slate-200 text-slate-600
                       hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            ← Previous
          </button>

          {currentQ < questions.length - 1 ? (
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

      {/* Tab switch warning */}
      {tabCount > 0 && (
        <div className={`fixed bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2
                        text-xs rounded-xl px-4 py-2.5 shadow-lg z-50 transition-colors
                        ${tabCount >= TAB_LIMIT - 1
                          ? "bg-red-50 border border-red-400 text-red-700 font-semibold"
                          : "bg-yellow-50 border border-yellow-300 text-yellow-800"}`}>
          {tabCount >= TAB_LIMIT - 1
            ? `WARNING: ${tabCount}/${TAB_LIMIT} tab switches — one more will terminate your exam!`
            : `Tab switching detected (${tabCount}×) — this session is being monitored.`}
        </div>
      )}
    </div>
  )
}
