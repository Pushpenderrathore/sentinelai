"use client"

interface StatItem {
  label: string
  value: string | number
  subtext?: string
  color?: "cyan" | "purple" | "green" | "red" | "yellow" | "orange"
  icon?: React.ReactNode
  trend?: "up" | "down" | "neutral"
}

interface StatsDashboardProps {
  title?: string
  stats: StatItem[]
  columns?: 2 | 3 | 4
  compact?: boolean
}

const colorConfig = {
  cyan: {
    text: "text-cyan-400",
    bg: "from-cyan-500/10 to-cyan-500/5",
    border: "border-cyan-500/30",
    hover: "hover:border-cyan-400/50",
    ring: "focus-within:ring-cyan-500/50"
  },
  purple: {
    text: "text-purple-400",
    bg: "from-purple-500/10 to-purple-500/5",
    border: "border-purple-500/30",
    hover: "hover:border-purple-400/50",
    ring: "focus-within:ring-purple-500/50"
  },
  green: {
    text: "text-green-400",
    bg: "from-green-500/10 to-green-500/5",
    border: "border-green-500/30",
    hover: "hover:border-green-400/50",
    ring: "focus-within:ring-green-500/50"
  },
  red: {
    text: "text-red-400",
    bg: "from-red-500/10 to-red-500/5",
    border: "border-red-500/30",
    hover: "hover:border-red-400/50",
    ring: "focus-within:ring-red-500/50"
  },
  yellow: {
    text: "text-yellow-400",
    bg: "from-yellow-500/10 to-yellow-500/5",
    border: "border-yellow-500/30",
    hover: "hover:border-yellow-400/50",
    ring: "focus-within:ring-yellow-500/50"
  },
  orange: {
    text: "text-orange-400",
    bg: "from-orange-500/10 to-orange-500/5",
    border: "border-orange-500/30",
    hover: "hover:border-orange-400/50",
    ring: "focus-within:ring-orange-500/50"
  }
}

export default function StatsDashboard({ title, stats, columns = 4, compact = false }: StatsDashboardProps) {
  const colClasses = {
    2: "grid-cols-1 sm:grid-cols-2",
    3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
    4: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4",
  }

  return (
    <div className="space-y-4">
      {title && (
        <div>
          <h3 className="text-lg font-bold text-white">{title}</h3>
          <div className="w-10 h-0.5 bg-gradient-to-r from-cyan-500 to-transparent mt-2" />
        </div>
      )}
      
      <div className={`grid ${colClasses[columns]} gap-4`}>
        {stats.map((stat, idx) => {
          const config = colorConfig[stat.color || "cyan"]
          return (
            <div
              key={idx}
              className={`relative group rounded-xl border ${config.border} bg-gradient-to-br ${config.bg} p-4 transition-all duration-300 ${config.hover} ${config.ring} focus-within:ring-2 focus-within:shadow-lg ${config.text.replace("text-", "focus-within:shadow-")}/20`}
            >
              {/* Gradient overlay on hover */}
              <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none bg-gradient-to-br from-white/5 to-transparent" />
              
              <div className="relative space-y-2">
                {stat.icon && (
                  <div className="flex items-center justify-between">
                    <div className={`text-2xl ${config.text}`}>{stat.icon}</div>
                    {stat.trend && (
                      <span className={`text-xs font-semibold ${
                        stat.trend === "up" ? "text-green-400" :
                        stat.trend === "down" ? "text-red-400" :
                        "text-slate-400"
                      }`}>
                        {stat.trend === "up" ? "↑" : stat.trend === "down" ? "↓" : "→"}
                      </span>
                    )}
                  </div>
                )}
                
                <div>
                  <div className={`text-${compact ? "xl" : "2xl"} font-bold font-mono ${config.text}`}>
                    {stat.value}
                  </div>
                  <div className="text-xs text-slate-400 mt-1 font-medium">{stat.label}</div>
                  {stat.subtext && <div className="text-xs text-slate-500 mt-1">{stat.subtext}</div>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
