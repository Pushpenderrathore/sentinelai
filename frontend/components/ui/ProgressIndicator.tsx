"use client"

interface ProgressIndicatorProps {
  current: number
  total: number
  label?: string
  showPercentage?: boolean
  animated?: boolean
  size?: "sm" | "md" | "lg"
  color?: "cyan" | "purple" | "green" | "red"
  showSteps?: boolean
}

const colorConfig = {
  cyan: "from-cyan-500 to-blue-500 shadow-cyan-500/50",
  purple: "from-purple-500 to-pink-500 shadow-purple-500/50",
  green: "from-green-500 to-emerald-500 shadow-green-500/50",
  red: "from-red-500 to-orange-500 shadow-red-500/50",
}

export default function ProgressIndicator({
  current,
  total,
  label,
  showPercentage = true,
  animated = true,
  size = "md",
  color = "cyan",
  showSteps = false,
}: ProgressIndicatorProps) {
  const percentage = Math.round((current / total) * 100)
  
  const sizeClasses = {
    sm: "h-1.5",
    md: "h-2.5",
    lg: "h-4"
  }

  const colors = colorConfig[color]

  return (
    <div className="w-full space-y-2">
      {(label || showPercentage) && (
        <div className="flex items-center justify-between">
          {label && <label className="text-xs font-semibold text-slate-300">{label}</label>}
          {showPercentage && (
            <span className={`text-xs font-bold ${
              color === "cyan" ? "text-cyan-400" :
              color === "purple" ? "text-purple-400" :
              color === "green" ? "text-green-400" :
              "text-red-400"
            }`}
            >
              {percentage}%
            </span>
          )}
        </div>
      )}
      
      <div className={`relative w-full bg-slate-800/50 rounded-full overflow-hidden border border-slate-700/50 ${sizeClasses[size]}`}>
        <div
          className={`h-full bg-gradient-to-r ${colors} rounded-full transition-all duration-500 ease-out ${animated ? `shadow-lg ${colors.split(" ").pop()}` : ""}`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={current}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-label={label}
        />
        
        {animated && (
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-shimmer"
            style={{ width: `${percentage}%` }}
            aria-hidden="true"
          />
        )}
      </div>

      {showSteps && (
        <div className="flex justify-between mt-3">
          {Array.from({ length: Math.min(5, total) }).map((_, i) => {
            const stepValue = Math.round((i / 4) * total)
            return (
              <div
                key={i}
                className={`text-xs font-mono ${stepValue <= current ? "text-slate-300" : "text-slate-600"}`}
              >
                {stepValue}
              </div>
            )
          })}
        </div>
      )}

      <div className="flex justify-between mt-2 text-xs text-slate-500 font-mono">
        <span>{current}</span>
        <span>of {total}</span>
      </div>
    </div>
  )
}
