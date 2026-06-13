"use client"

interface ProgressIndicatorProps {
  current: number
  total: number
  label?: string
  showPercentage?: boolean
  animated?: boolean
  size?: "sm" | "md" | "lg"
}

export default function ProgressIndicator({
  current,
  total,
  label,
  showPercentage = true,
  animated = true,
  size = "md"
}: ProgressIndicatorProps) {
  const percentage = Math.round((current / total) * 100)
  
  const sizeClasses = {
    sm: "h-1.5",
    md: "h-2.5",
    lg: "h-3"
  }

  return (
    <div className="w-full">
      {(label || showPercentage) && (
        <div className="flex items-center justify-between mb-2">
          {label && <span className="text-xs font-medium text-slate-300">{label}</span>}
          {showPercentage && <span className="text-xs font-semibold text-cyan-400">{percentage}%</span>}
        </div>
      )}
      
      <div className={`relative w-full bg-slate-800/50 rounded-full overflow-hidden border border-slate-700 ${sizeClasses[size]}`}>
        <div
          className={`h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500 ${animated ? "shadow-lg shadow-cyan-500/50" : ""}`}
          style={{ width: `${percentage}%` }}
        />
        
        {animated && (
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-30 animate-shimmer"
            style={{ width: `${percentage}%` }}
          />
        )}
      </div>

      <div className="flex justify-between mt-1.5 text-xs text-slate-500">
        <span>{current}</span>
        <span>of {total}</span>
      </div>
    </div>
  )
}
