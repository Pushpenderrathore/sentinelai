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
  thinking: {
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30",
    icon: "◐",
    label: "thinking...",
  },
  working: {
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30",
    icon: "●",
    label: "executing...",
  },
  complete: {
    color: "text-green-400",
    bgColor: "bg-green-500/10",
    borderColor: "border-green-500/30",
    icon: "✓",
    label: "done",
  },
  error: {
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30",
    icon: "✕",
    label: "error",
  },
}

export default function AgentOrchestrator({ agents, isRunning, title = "Agent Orchestra" }: AgentOrchestratorProps) {
  const endRef = useRef<HTMLDivElement>(null)
  const completedCount = agents.filter(a => a.status === "complete").length
  const errorCount = agents.filter(a => a.status === "error").length

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [agents])

  return (
    <div className="glass-card overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 shrink-0 bg-white/5 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="text-xl font-bold text-white">{title}</div>
          {isRunning && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 border border-cyan-500/30 text-xs font-semibold text-cyan-300">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              ORCHESTRATING
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="text-center">
            <div className="text-sm font-bold text-white">{completedCount}</div>
            <div className="text-xs text-slate-400 font-mono">complete</div>
          </div>
          <div className="w-px h-8 bg-white/10" />
          <div className="text-center">
            <div className="text-sm font-bold text-white">{agents.length}</div>
            <div className="text-xs text-slate-400 font-mono">total</div>
          </div>
          {errorCount > 0 && (
            <>
              <div className="w-px h-8 bg-white/10" />
              <div className="text-center">
                <div className="text-sm font-bold text-red-400">{errorCount}</div>
                <div className="text-xs text-slate-400 font-mono">error</div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="shrink-0 px-5 py-3 bg-white/5">
        <div className="w-full bg-slate-800/50 rounded-full h-1.5 overflow-hidden border border-white/10">
          <div
            className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500 shadow-lg shadow-cyan-500/30"
            style={{ width: `${agents.length > 0 ? (completedCount / agents.length) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Agents list */}
      <div className="flex-grow overflow-y-auto scrollable-area px-5 py-4 space-y-3">
        {agents.length === 0 && (
          <div className="flex items-center justify-center h-32 text-slate-400">
            <p className="text-sm">Waiting for orchestration to start...</p>
          </div>
        )}

        {agents.map((agent, idx) => {
          const config = statusConfig[agent.status]
          const isLastAgent = idx === agents.length - 1
          const nextAgentStarted = idx < agents.length - 1 && 
            (agents[idx + 1].status !== "thinking" || agents[idx + 1].message !== "")

          return (
            <div key={idx}>
              {/* Connection line */}
              {!isLastAgent && nextAgentStarted && (
                <div className="mx-4 h-2 bg-gradient-to-b from-white/20 to-white/5" />
              )}

              <div
                className={`${config.bgColor} border ${config.borderColor} rounded-lg p-4 transition-all duration-300 hover:border-opacity-100`}
              >
                {/* Agent header */}
                <div className="flex items-start gap-3 mb-2">
                  <span className={`text-lg font-bold flex-shrink-0 ${config.color} animate-pulse`}>
                    {config.icon}
                  </span>
                  <div className="flex-grow min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-white text-sm">{agent.name}</span>
                      <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${config.bgColor} ${config.color} border ${config.borderColor}`}>
                        {config.label}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Message */}
                <div className="text-xs text-slate-300 font-mono leading-relaxed ml-7 line-clamp-2">
                  {agent.message}
                </div>

                {/* Progress bar */}
                {agent.progress !== undefined && (
                  <div className="mt-2 ml-7 h-1.5 bg-black/30 rounded-full overflow-hidden border border-white/10">
                    <div
                      className={`h-full ${config.color.replace("text-", "bg-")} transition-all duration-300`}
                      style={{ width: `${agent.progress}%` }}
                    />
                  </div>
                )}
              </div>
            </div>
          )
        })}
        <div ref={endRef} />
      </div>
    </div>
  )
}
