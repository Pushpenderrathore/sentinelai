"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { createExamSession } from "@/lib/api"

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
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <a href="/" className="absolute top-6 left-6 text-sentinel-muted hover:text-white text-sm flex items-center gap-1.5 transition-colors">
        ← Home
      </a>

      <div className="w-full max-w-md">
        <div className="mb-10 text-center">
          <div className="inline-block text-sentinel-purple mb-4">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"/>
            </svg>
          </div>
          <h1 className="text-2xl font-bold mb-2">ExamGuard</h1>
          <p className="text-sentinel-muted text-sm">Create a monitored exam session.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            { key: "student_name", label: "Student Name", placeholder: "Riya Sharma",       type: "text" },
            { key: "student_id",   label: "Student ID",   placeholder: "STU-2024-001",      type: "text" },
            { key: "college_id",   label: "College ID",   placeholder: "CLG-AKGEC-2024",    type: "text" },
          ].map(({ key, label, placeholder, type }) => (
            <div key={key}>
              <label className="block text-xs text-sentinel-muted mb-1.5">{label}</label>
              <input
                type={type}
                value={(form as Record<string, string | number>)[key] as string}
                onChange={(e) => set(key, e.target.value)}
                placeholder={placeholder}
                required
                className="w-full px-4 py-3 bg-sentinel-surface border border-sentinel-border rounded-xl
                           text-sm placeholder:text-sentinel-muted
                           focus:outline-none focus:border-sentinel-purple/50 focus:ring-1 focus:ring-sentinel-purple/20
                           transition-colors"
              />
            </div>
          ))}

          <div>
            <label className="block text-xs text-sentinel-muted mb-1.5">
              Duration — <span className="text-slate-300">{form.duration_minutes} minutes</span>
            </label>
            <input
              type="range"
              min={15} max={180} step={15}
              value={form.duration_minutes}
              onChange={(e) => set("duration_minutes", parseInt(e.target.value))}
              className="w-full accent-sentinel-purple"
            />
            <div className="flex justify-between text-xs text-sentinel-muted mt-1">
              <span>15 min</span>
              <span>180 min</span>
            </div>
          </div>

          {error && <p className="text-sentinel-red text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl font-medium text-sm
                       bg-sentinel-purple text-white
                       hover:bg-sentinel-purple/90 active:scale-[0.98]
                       disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all duration-150"
          >
            {loading ? "Creating session…" : "Start Proctored Exam"}
          </button>
        </form>

        {/* Quick-fill examples */}
        <div className="mt-5">
          <p className="text-xs text-sentinel-muted text-center mb-2">Quick fill example</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {[
              { label: "Riya Sharma",  student_name: "Riya Sharma",  student_id: "24-CSE-1042", college_id: "CLG-AKGEC-2024", duration_minutes: 60  },
              { label: "Arjun Mehta", student_name: "Arjun Mehta", student_id: "24-CSE-2187", college_id: "CLG-AKGEC-2024", duration_minutes: 90  },
              { label: "Priya Patel", student_name: "Priya Patel", student_id: "24-IT-3056",  college_id: "CLG-AKGEC-2024", duration_minutes: 120 },
            ].map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => setForm({ student_name: ex.student_name, student_id: ex.student_id, college_id: ex.college_id, exam_name: "B.Tech Proctored Examination", duration_minutes: ex.duration_minutes })}
                className="text-xs font-mono px-3 py-1.5 rounded-lg border border-sentinel-border
                           text-sentinel-muted hover:text-white hover:border-slate-500 transition-colors"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-5 text-xs text-center text-sentinel-muted">
          Once created, share the exam link with the student. Open{" "}
          <code className="text-slate-400">/exam/[id]/monitor</code> in a separate tab to watch live.
        </p>
      </div>
    </main>
  )
}
