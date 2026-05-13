interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: "up" | "down" | "neutral"
  color?: "default" | "green" | "red" | "yellow" | "blue"
}

const colorMap = {
  default: "border-border",
  green: "border-emerald-500/50",
  red: "border-red-500/50",
  yellow: "border-yellow-500/50",
  blue: "border-primary/50",
}

const trendColorMap = {
  up: "text-emerald-400",
  down: "text-red-400",
  neutral: "text-muted-foreground",
}

export function MetricCard({ title, value, subtitle, trend = "neutral", color = "default" }: MetricCardProps) {
  return (
    <div className={`rounded-xl border-l-4 ${colorMap[color]} bg-card p-4`}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <p className="mt-1 text-2xl font-bold text-foreground">{value}</p>
      {subtitle && (
        <p className={`mt-1 text-xs ${trendColorMap[trend]}`}>{subtitle}</p>
      )}
    </div>
  )
}
