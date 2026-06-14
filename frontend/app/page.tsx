import Link from "next/link"

const modules = [
  {
    href:    "/scan",
    label:   "VulnSentinel",
    tag:     "Code Security",
    color:   "from-cyan-500/10 to-blue-500/10 border-cyan-500/20 hover:border-cyan-400/50",
    accent:  "text-sentinel-cyan",
    icon: (
      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
      </svg>
    ),
    description: "Scan any GitHub repository for vulnerabilities. Multi-agent pipeline detects SQL injection, XSS, CVEs, and more — then generates patches automatically.",
    cta: "Start a Scan →",
    stats: { scans: "1.2K+", accuracy: "99.8%", fixes: "847" }
  },
  {
    href:    "/exam",
    label:   "ExamGuard",
    tag:     "Exam Integrity",
    color:   "from-purple-500/10 to-pink-500/10 border-purple-500/20 hover:border-purple-400/50",
    accent:  "text-sentinel-purple",
    icon: (
      <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
      </svg>
    ),
    description: "AI-powered proctoring with real-time tab monitoring, face detection, and keystroke analysis. Flags suspicious behaviour instantly — no human proctor needed.",
    cta: "Create Exam Session →",
    stats: { exams: "342", avgScore: "97.3%", integrity: "100%" }
  },
]

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 sm:px-6 py-16 sm:py-20">
      {/* Logo */}
      <div className="text-center mb-16 animate-fade-in">
        <div className="inline-flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sentinel-cyan to-sentinel-purple flex items-center justify-center shadow-lg shadow-cyan-500/30">
            <svg className="w-6 h-6 text-black" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
            </svg>
          </div>
          <div>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
              SentinelAI
            </h1>
            <p className="text-sm text-slate-400 font-mono tracking-widest mt-1">AUTONOMOUS THREAT DETECTION</p>
          </div>
        </div>
        <p className="text-slate-400 text-lg max-w-lg mx-auto leading-relaxed">
          Intelligent threat detection for <span className="text-slate-300 font-semibold">code security</span> and <span className="text-slate-300 font-semibold">academic integrity</span>
        </p>
      </div>

      {/* Module cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-4xl">
        {modules.map((mod, idx) => (
          <Link
            key={mod.href}
            href={mod.href}
            className="group relative rounded-2xl border bg-gradient-to-br p-8 transition-all duration-300 overflow-hidden animate-scale-in"
            style={{ animationDelay: `${idx * 0.1}s` }}
          >
            {/* Background gradient */}
            <div className={`absolute inset-0 bg-gradient-to-br ${mod.color}`} />
            
            {/* Animated hover overlay */}
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-br from-white/10 to-transparent" />

            <div className="relative">
              {/* Icon */}
              <div className={`${mod.accent} mb-6 group-hover:scale-110 transition-transform duration-300`}>
                {mod.icon}
              </div>

              {/* Header */}
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex-grow">
                  <h2 className="text-2xl font-bold text-white mb-2">{mod.label}</h2>
                  <span className={`inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-full font-mono font-semibold border ${mod.color}`}>
                    <span className="w-2 h-2 rounded-full bg-current" />
                    {mod.tag}
                  </span>
                </div>
              </div>

              {/* Description */}
              <p className="text-slate-200 text-sm leading-relaxed mb-6">
                {mod.description}
              </p>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 mb-6 p-3 rounded-lg bg-white/5 backdrop-blur border border-white/10">
                {Object.entries(mod.stats).map(([key, value]) => (
                  <div key={key} className="text-center">
                    <p className="text-xs text-slate-400 font-mono uppercase">{key}</p>
                    <p className={`text-sm font-bold mt-1 ${mod.accent}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* CTA */}
              <div className="flex items-center gap-2 font-semibold group-hover:gap-3 transition-all">
                <span className={`${mod.accent}`}>
                  {mod.cta.split("→")[0].trim()}
                </span>
                <span className={`${mod.accent} group-hover:translate-x-1 transition-transform`}>→</span>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-16 text-center space-y-2">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
          <span className="w-2 h-2 rounded-full bg-sentinel-cyan animate-pulse" />
          <p className="text-xs font-mono text-slate-400">Powered by Multi-Agent AI</p>
        </div>
        <p className="text-xs text-slate-500 font-mono">
          FAR AWAY 2026 · Team Zen Hackers · Agentic &amp; Autonomous Systems
        </p>
      </div>
    </main>
  )
}
