"use client"

interface StatItem {
  label: string
  value: string | number
  subtext?: string
  color?: "cyan" | "purple" | "green" | "red"
}

interface StatsDashboardProps {
  title?: string
  stats: StatItem[]
  columns?: 2 | 3 | 4
}

const colorConfig = {
  cyan: "text-cyan-400",
  purple: "text-purple-400",
  green: "text-green-400",
  red: "text-red-400",
}

export default function StatsDashboard({ title, stats, columns = 4 }: StatsDashboardProps) {
  const colClasses = {
    2: "grid-cols-2",
    3: "grid-cols-3",
    4: "grid-cols-4",
  }

  return (
    <div className="glass-card p-6">
      {title && <h3 className="text-lg font-bold text-white mb-4">{title}</h3>}
      
      <div className={`grid ${colClasses[columns]} gap-4`}>
        {stats.map((stat, idx) => (
          <div key={idx} className="text-center p-3 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 transition-all duration-300 hover:scale-105">
            <div className={`text-2xl font-bold ${colorConfig[stat.color || "cyan"]}`}>
              {stat.value}
            </div>
            <div className="text-xs text-slate-400 mt-1 font-medium">{stat.label}</div>
            {stat.subtext && <div className="text-xs text-slate-500 mt-0.5">{stat.subtext}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}
