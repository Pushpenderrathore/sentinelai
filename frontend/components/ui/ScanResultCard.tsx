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
}

const colorConfig = {
  cyan: "from-cyan-500/20 to-blue-500/20 border-cyan-500/30 text-cyan-400",
  purple: "from-purple-500/20 to-pink-500/20 border-purple-500/30 text-purple-400",
  green: "from-green-500/20 to-emerald-500/20 border-green-500/30 text-green-400",
  red: "from-red-500/20 to-orange-500/20 border-red-500/30 text-red-400",
  yellow: "from-yellow-500/20 to-amber-500/20 border-yellow-500/30 text-yellow-400",
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
  className = ""
}: ScanResultCardProps) {
  const colors = colorConfig[color]

  return (
    <button
      onClick={onClick}
      className={`glass-card p-4 text-left group hover:scale-105 transition-all duration-300 ${colors} ${className}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`text-2xl group-hover:scale-110 transition-transform duration-300`}>
          {icon}
        </div>
        {trend && (
          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
            trend === "up" ? "bg-green-500/20 text-green-400" :
            trend === "down" ? "bg-red-500/20 text-red-400" :
            "bg-slate-500/20 text-slate-400"
          }`}>
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"} {trendValue || "0%"}
          </span>
        )}
      </div>

      <div className="space-y-1">
        <p className="text-slate-400 text-xs font-medium">{title}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold text-white">{value}</span>
          {unit && <span className="text-sm text-slate-500">{unit}</span>}
        </div>
      </div>
    </button>
  )
}
