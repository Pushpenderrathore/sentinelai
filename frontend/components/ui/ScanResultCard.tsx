"use client"

interface ScanResultCardProps {
  title: string
  value: string | number
  unit?: string
  icon: React.ReactNode
  color: "cyan" | "purple" | "green" | "red" | "yellow"
  trend?: "up" | "down" | "neutral"
  trendValue?: string
  onClick?: () => void
  className?: string
  description?: string
  actionLabel?: string
}

const colorConfig = {
  cyan: {
    gradient: "from-cyan-500/20 to-blue-500/20",
    border: "border-cyan-500/30",
    text: "text-cyan-400",
    hover: "hover:border-cyan-400/60 hover:shadow-cyan-500/20",
  },
  purple: {
    gradient: "from-purple-500/20 to-pink-500/20",
    border: "border-purple-500/30",
    text: "text-purple-400",
    hover: "hover:border-purple-400/60 hover:shadow-purple-500/20",
  },
  green: {
    gradient: "from-green-500/20 to-emerald-500/20",
    border: "border-green-500/30",
    text: "text-green-400",
    hover: "hover:border-green-400/60 hover:shadow-green-500/20",
  },
  red: {
    gradient: "from-red-500/20 to-orange-500/20",
    border: "border-red-500/30",
    text: "text-red-400",
    hover: "hover:border-red-400/60 hover:shadow-red-500/20",
  },
  yellow: {
    gradient: "from-yellow-500/20 to-amber-500/20",
    border: "border-yellow-500/30",
    text: "text-yellow-400",
    hover: "hover:border-yellow-400/60 hover:shadow-yellow-500/20",
  },
}

export default function ScanResultCard({
  title,
  value,
  unit,
  icon,
  color,
  trend,
  trendValue,
  onClick,
  className = "",
  description,
  actionLabel,
}: ScanResultCardProps) {
  const config = colorConfig[color]

  return (
    <button
      onClick={onClick}
      className={`glass-card p-5 text-left group relative overflow-hidden transition-all duration-300 
        bg-gradient-to-br ${config.gradient} ${config.border}
        ${config.hover} hover:scale-105 hover:shadow-xl
        focus:outline-none focus:ring-2 ${config.text.replace("text-", "focus:ring-")}/50 focus:ring-offset-2 focus:ring-offset-slate-950
        ${className}`}
    >
      {/* Animated gradient overlay */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-br from-white/10 to-transparent pointer-events-none" />

      <div className="relative space-y-3">
        <div className="flex items-start justify-between">
          <div className={`text-3xl group-hover:scale-110 transition-transform duration-300 ${config.text}`}>
            {icon}
          </div>
          {trend && (
            <span className={`text-xs font-semibold px-2.5 py-1 rounded-lg backdrop-blur ${
              trend === "up" ? "bg-green-500/20 text-green-300 border border-green-500/30" :
              trend === "down" ? "bg-red-500/20 text-red-300 border border-red-500/30" :
              "bg-slate-500/20 text-slate-300 border border-slate-500/30"
            }`}>
              {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"} {trendValue || "0%"}
            </span>
          )}
        </div>

        <div>
          <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">{title}</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className={`text-3xl font-bold font-mono ${config.text}`}>{value}</span>
            {unit && <span className="text-sm text-slate-500">{unit}</span>}
          </div>
        </div>

        {description && (
          <p className="text-xs text-slate-400 line-clamp-2">{description}</p>
        )}

        {actionLabel && (
          <div className={`text-xs font-semibold ${config.text} group-hover:translate-x-1 transition-transform`}>
            {actionLabel} →
          </div>
        )}
      </div>
    </button>
  )
}
