"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { createExamSession } from "@/lib/api"
import Link from "next/link"

export default function ExamPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    student_id:       "",
    student_name:     "",
    college_id:       "",
    exam_name:        "B.Tech Proctored Examination",
    duration_minutes: 60,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState("")

  function set(key: string, value: string | number) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.student_id || !form.student_name || !form.college_id) return
    setLoading(true)
    setError("")
    try {
      const { exam_id } = await createExamSession(form)
      router.push(`/exam/${exam_id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create session")
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen px-4 sm:px-6 py-8 sm:py-12 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl opacity-20" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-500/10 rounded-full blur-3xl opacity-20" />
      </div>

      <div className="relative z-10 max-w-2xl mx-auto">
        {/* Skip to main content */}
        <a href="#exam-form" className="sr-only focus:not-sr-only focus:block focus:mb-4 focus:px-4 focus:py-2 focus:bg-purple-400 focus:text-black focus:rounded-lg focus:font-semibold">
          Skip to exam form
        </a>

        {/* Header */}
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-purple-400 mb-8 transition-colors focus:outline-none focus:ring-2 focus:ring-purple-400/50 rounded px-2 py-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to home
        </Link>

        <div className="mb-12">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"/>
              </svg>
            </div>
            <div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white mb-1">ExamGuard</h1>
              <p className="text-sm text-slate-400">AI-powered proctoring with real-time integrity monitoring</p>
            </div>
          </div>
          <p className="text-slate-400 max-w-lg">
            Create a secure, monitored exam session. Face detection, keystroke analysis, and tab monitoring ensure academic integrity. Perfect for remote assessments and online proctoring.
          </p>
        </div>

        {/* Main form card */}
        <form id="exam-form" onSubmit={handleSubmit} className="glass-card p-6 sm:p-8 mb-8 space-y-8">
          {/* Student Information Section */}
          <div>
            <div className="mb-5 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center">
                <span className="text-lg">👤</span>
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Student Information</h3>
                <p className="text-xs text-slate-500">Enter your details for session identification</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              {[
                { key: "student_name", label: "Student Name", placeholder: "e.g., Riya Sharma", type: "text" },
                { key: "student_id",   label: "Student ID",   placeholder: "e.g., STU-2024-001", type: "text" },
              ].map(({ key, label, placeholder, type }) => (
                <div key={key}>
                  <label htmlFor={key} className="block text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wide">{label}</label>
                  <input
                    id={key}
                    type={type}
                    value={(form as Record<string, string | number>)[key] as string}
                    onChange={(e) => set(key, e.target.value)}
                    placeholder={placeholder}
                    required
                    className="input-glass w-full transition-all focus:ring-2 focus:ring-purple-400/50"
                    aria-label={label}
                    aria-required="true"
                  />
                </div>
              ))}
            </div>

            <div>
              <label htmlFor="college_id" className="block text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wide">College ID</label>
              <input
                id="college_id"
                type="text"
                value={form.college_id}
                onChange={(e) => set("college_id", e.target.value)}
                placeholder="e.g., CLG-AKGEC-2024"
                required
                className="input-glass w-full transition-all focus:ring-2 focus:ring-purple-400/50"
                aria-label="College ID"
                aria-required="true"
              />
            </div>
          </div>

          {/* Exam Settings Section */}
          <div className="border-t border-white/10 pt-8">
            <div className="mb-5 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center">
                <span className="text-lg">⏱️</span>
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Exam Configuration</h3>
                <p className="text-xs text-slate-500">Set the duration and monitoring preferences</p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <label htmlFor="duration-slider" className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Exam Duration</label>
                  <span className="text-sm font-bold bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent">
                    {form.duration_minutes} minutes
                  </span>
                </div>
                <input
                  id="duration-slider"
                  type="range"
                  min={15}
                  max={180}
                  step={15}
                  value={form.duration_minutes}
                  onChange={(e) => set("duration_minutes", parseInt(e.target.value))}
                  className="w-full h-2.5 bg-slate-800/50 rounded-full appearance-none cursor-pointer accent-purple-500"
                  aria-label="Exam Duration in minutes"
                  aria-valuenow={form.duration_minutes}
                  aria-valuemin={15}
                  aria-valuemax={180}
                  aria-valuetext={`${form.duration_minutes} minutes`}
                />
                <div className="flex justify-between text-xs text-slate-500 mt-3 font-mono">
                  <span>15 min</span>
                  <span>90 min (Recommended)</span>
                  <span>180 min</span>
                </div>
              </div>

              {/* Monitoring info box */}
              <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
                <p className="text-xs text-slate-300 flex items-start gap-2">
                  <span className="text-purple-400 font-bold mt-0.5">ℹ</span>
                  <span>Real-time monitoring enabled: Face detection, keystroke analysis, and tab activity will be recorded.</span>
                </p>
              </div>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3" role="alert">
              <svg className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <p className="text-sm text-red-300 font-medium">{error}</p>
            </div>
          )}

          {/* Submit button */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={loading || !form.student_id || !form.student_name || !form.college_id}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  <span>Creating Exam Session...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                  </svg>
                  <span>Start Proctored Exam</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Features */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
          {[
            { icon: "👁️", title: "Face Detection", desc: "Real-time face recognition ensures the registered student is present" },
            { icon: "⌨️", title: "Keystroke Analysis", desc: "Detects suspicious typing patterns and unusual activity" },
            { icon: "📱", title: "Tab Monitoring", desc: "Tracks window focus and detects tab switching attempts" },
            { icon: "🎯", title: "Integrity Scoring", desc: "Comprehensive behavioral analysis with real-time risk assessment" },
          ].map((feat, i) => (
            <div key={i} className="glass-card p-4">
              <div className="text-2xl mb-2">{feat.icon}</div>
              <h4 className="text-sm font-semibold text-white mb-1">{feat.title}</h4>
              <p className="text-xs text-slate-400">{feat.desc}</p>
            </div>
          ))}
        </div>

        {/* Quick examples */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-bold text-white mb-4">Quick Fill Examples</h3>
          <div className="space-y-2">
            {[
              { name: "Riya Sharma",  id: "24-CSE-1042", college: "CLG-AKGEC-2024", duration: 60 },
              { name: "Arjun Mehta", id: "24-CSE-2187", college: "CLG-AKGEC-2024", duration: 90 },
              { name: "Priya Patel", id: "24-IT-3056",  college: "CLG-AKGEC-2024", duration: 120 },
            ].map((ex, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setForm({ 
                  student_name: ex.name, 
                  student_id: ex.id, 
                  college_id: ex.college, 
                  exam_name: "B.Tech Proctored Examination", 
                  duration_minutes: ex.duration 
                })}
                className="w-full text-left px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-300
                         hover:bg-white/10 hover:border-white/20 hover:text-white
                         transition-all duration-300 text-sm font-mono"
              >
                <span className="font-semibold">{ex.name}</span> • ID: {ex.id} • {ex.duration} min
              </button>
            ))}
          </div>
        </div>

        {/* Info */}
        <div className="mt-8 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <p className="text-xs text-blue-300 leading-relaxed">
            <strong>Pro Tip:</strong> Once created, share the exam link with the student. Open <code className="text-slate-300 font-mono">/exam/[id]/monitor</code> in a separate browser or second screen to watch the live proctoring feed.
          </p>
        </div>
      </div>
    </main>
  )
}
