"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AdminSidebar } from "@/components/admin/sidebar"
import { MetricCard } from "@/components/admin/metric-card"

interface Metrics {
  system: {
    uptime: { formatted: string }
    memory: { heapUsed: number; heapTotal: number; rss: number }
    requests: { total: number; lastHour: number; rpm: number; avgLatencyMs: number; errorRate: number }
  }
  events: { total: number; lastHour: number; bySeverity: { error: number; critical: number; warning: number } }
  errors: { total: number; active: number; resolved: number; selfRepairEnabled: boolean }
  snapshots: { total: number }
  activeSessions: number
}

export default function AdminDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    async function fetchMetrics() {
      try {
        const res = await fetch("/api/admin/metrics")
        if (res.status === 401) {
          router.push("/admin/login")
          return
        }
        const data = await res.json()
        setMetrics(data)
      } catch {
        router.push("/admin/login")
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
    const interval = setInterval(fetchMetrics, 5000)
    return () => clearInterval(interval)
  }, [router])

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">System Dashboard</h1>
          <p className="text-sm text-muted-foreground">Real-time system monitoring and telemetry</p>
        </div>

        {metrics && (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                title="Uptime"
                value={metrics.system.uptime.formatted}
                subtitle="System running"
                color="green"
                trend="up"
              />
              <MetricCard
                title="Memory"
                value={`${metrics.system.memory.heapUsed} MB`}
                subtitle={`of ${metrics.system.memory.heapTotal} MB heap`}
                color="blue"
              />
              <MetricCard
                title="Active Errors"
                value={metrics.errors.active}
                subtitle={`${metrics.errors.resolved} resolved`}
                color={metrics.errors.active > 0 ? "red" : "green"}
                trend={metrics.errors.active > 0 ? "down" : "up"}
              />
              <MetricCard
                title="Self-Repair"
                value={metrics.errors.selfRepairEnabled ? "ON" : "OFF"}
                subtitle={`${metrics.errors.total} total errors tracked`}
                color={metrics.errors.selfRepairEnabled ? "green" : "yellow"}
              />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                title="Total Requests"
                value={metrics.system.requests.total}
                subtitle={`${metrics.system.requests.rpm} req/min`}
                color="blue"
              />
              <MetricCard
                title="Avg Latency"
                value={`${metrics.system.requests.avgLatencyMs}ms`}
                subtitle="Last hour average"
                color="default"
              />
              <MetricCard
                title="Error Rate"
                value={`${metrics.system.requests.errorRate}%`}
                subtitle={`${metrics.system.requests.lastHour} requests last hour`}
                color={metrics.system.requests.errorRate > 5 ? "red" : "green"}
                trend={metrics.system.requests.errorRate > 5 ? "down" : "up"}
              />
              <MetricCard
                title="Events"
                value={metrics.events.total}
                subtitle={`${metrics.events.lastHour} last hour`}
                color="default"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-border bg-card p-5">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">System Overview</h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">RSS Memory</span>
                    <span className="text-sm font-medium text-foreground">{metrics.system.memory.rss} MB</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Active Sessions</span>
                    <span className="text-sm font-medium text-foreground">{metrics.activeSessions}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Snapshots</span>
                    <span className="text-sm font-medium text-foreground">{metrics.snapshots.total}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Warning Events</span>
                    <span className="text-sm font-medium text-yellow-400">{metrics.events.bySeverity.warning}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Critical Events</span>
                    <span className="text-sm font-medium text-red-400">{metrics.events.bySeverity.critical}</span>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-5">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Quick Actions</h2>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => router.push("/admin/terminal")}
                    className="rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-foreground hover:border-primary/50 hover:bg-primary/5"
                  >
                    Open Terminal
                  </button>
                  <button
                    onClick={() => router.push("/admin/errors")}
                    className="rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-foreground hover:border-primary/50 hover:bg-primary/5"
                  >
                    View Errors
                  </button>
                  <button
                    onClick={() => router.push("/admin/mirror")}
                    className="rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-foreground hover:border-primary/50 hover:bg-primary/5"
                  >
                    Create Snapshot
                  </button>
                  <button
                    onClick={() => router.push("/admin/audit")}
                    className="rounded-lg border border-border bg-background px-4 py-3 text-left text-sm font-medium text-foreground hover:border-primary/50 hover:bg-primary/5"
                  >
                    Audit Trail
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
