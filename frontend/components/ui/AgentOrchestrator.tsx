"use client"

import { useEffect, useRef } from "react"

interface Agent {
  name: string
  status: "thinking" | "working" | "complete" | "error"
  message: string
  progress?: number
}

interface AgentOrchestratorProps {
  agents: Agent[]
  isRunning: boolean
  title?: string
}

const statusConfig = {
  thinking: { color: "text-yellow-400", icon: "◐", bgColor: "bg-yellow-500/10", borderColor: "border-yellow-500/30" },
  working: { color: "text-cyan-400", icon: "●", bgColor: "bg-cyan-500/10", borderColor: "border-cyan-500/30" },
  complete: { color: "text-green-400", icon: "✓", bgColor: "bg-green-500/10", borderColor: "border-green-500/30" },
  error: { color: "text-red-400", icon: "✕", bgColor: "bg-red-500/10", borderColor: "border-red-500/30" },
}

export default function AgentOrchestrator({ agents, isRunning, title = "Agent Orchestra" }: AgentOrchestratorProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [agents])

  return (
    <div className="glass-card overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0 bg-white/5 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="text-xl font-semibold text-white">{title}</div>
          {isRunning && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-cyan-500/20 border border-cyan-500/30 text-xs font-mono text-cyan-300">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              ORCHESTRATING
            </span>
          )}
        </div>
        <div className="text-xs text-slate-400 font-mono">
          {agents.filter(a => a.status === "complete").length} / {agents.length}
        </div>
      </div>

      {/* Agents list */}
      <div className="flex-grow overflow-y-auto scrollable-area px-4 py-4 space-y-3">
        {agents.map((agent, idx) => {
          const config = statusConfig[agent.status]
          return (
            <div
              key={idx}
              className={`${config.bgColor} border ${config.borderColor} rounded-lg p-3 transition-all duration-300 animate-in`}
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              {/* Agent header */}
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-lg font-bold animate-pulse ${config.color}`}>{config.icon}</span>
                <span className="font-semibold text-white text-sm">{agent.name}</span>
                {agent.status === "thinking" && (
                  <span className="text-xs text-yellow-300 font-mono ml-auto">thinking...</span>
                )}
                {agent.status === "working" && (
                  <span className="text-xs text-cyan-300 font-mono ml-auto">executing...</span>
                )}
                {agent.status === "complete" && (
                  <span className="text-xs text-green-300 font-mono ml-auto">done</span>
                )}
              </div>

              {/* Message */}
              <div className="text-xs text-slate-300 font-mono leading-relaxed mb-2 line-clamp-2">
                {agent.message}
              </div>

              {/* Progress bar */}
              {agent.progress !== undefined && (
                <div className="h-1 bg-black/30 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${config.color.replace("text-", "bg-")} transition-all duration-300`}
                    style={{ width: `${agent.progress}%` }}
                  />
                </div>
              )}
            </div>
          )
        })}
        <div ref={endRef} />
      </div>
    </div>
  )
}
