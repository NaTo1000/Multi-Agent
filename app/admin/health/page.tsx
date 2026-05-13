"use client"

import { useState, useEffect } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"
import { Button } from "@/components/ui/button"
import { MetricCard } from "@/components/admin/metric-card"

interface HealthCheck {
  id: string
  name: string
  type: "http" | "tcp" | "memory" | "disk" | "custom"
  target: string
  interval: number
  timeout: number
  enabled: boolean
  lastCheck?: string
  lastStatus: "healthy" | "degraded" | "unhealthy" | "unknown"
  lastLatency?: number
  consecutiveFailures: number
  metadata?: Record<string, unknown>
}

interface HealthHistory {
  checkId: string
  timestamp: string
  status: string
  latency: number
  error?: string
}

export default function HealthPage() {
  const [checks, setChecks] = useState<HealthCheck[]>([])
  const [summary, setSummary] = useState({ healthy: 0, degraded: 0, unhealthy: 0, unknown: 0 })
  const [history, setHistory] = useState<HealthHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedCheck, setSelectedCheck] = useState<string | null>(null)
  const [newCheck, setNewCheck] = useState({
    name: "",
    type: "http" as HealthCheck["type"],
    target: "",
    interval: 30000,
    timeout: 5000,
  })

  const fetchHealth = async () => {
    try {
      const res = await fetch("/api/admin/health")
      const data = await res.json()
      setChecks(data.checks || [])
      setSummary(data.summary || { healthy: 0, degraded: 0, unhealthy: 0, unknown: 0 })
      setHistory(data.history || [])
    } catch (error) {
      console.error("Failed to fetch health:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  const createCheck = async () => {
    if (!newCheck.name || !newCheck.target) return
    try {
      const res = await fetch("/api/admin/health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "create", check: newCheck }),
      })
      const data = await res.json()
      if (data.check) {
        fetchHealth()
        setNewCheck({ name: "", type: "http", target: "", interval: 30000, timeout: 5000 })
        setShowCreate(false)
      }
    } catch (error) {
      console.error("Failed to create check:", error)
    }
  }

  const runCheck = async (id: string) => {
    try {
      await fetch("/api/admin/health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "run", checkId: id }),
      })
      fetchHealth()
    } catch (error) {
      console.error("Failed to run check:", error)
    }
  }

  const toggleCheck = async (id: string, enabled: boolean) => {
    try {
      await fetch("/api/admin/health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: enabled ? "enable" : "disable", checkId: id }),
      })
      fetchHealth()
    } catch (error) {
      console.error("Failed to toggle check:", error)
    }
  }

  const deleteCheck = async (id: string) => {
    if (!confirm("Delete this health check?")) return
    try {
      await fetch("/api/admin/health", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", checkId: id }),
      })
      fetchHealth()
      if (selectedCheck === id) setSelectedCheck(null)
    } catch (error) {
      console.error("Failed to delete check:", error)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy": return "text-green-400 bg-green-400/20"
      case "degraded": return "text-yellow-400 bg-yellow-400/20"
      case "unhealthy": return "text-red-400 bg-red-400/20"
      default: return "text-muted-foreground bg-muted"
    }
  }

  const getStatusDot = (status: string) => {
    switch (status) {
      case "healthy": return "bg-green-400"
      case "degraded": return "bg-yellow-400"
      case "unhealthy": return "bg-red-400"
      default: return "bg-muted-foreground"
    }
  }

  const totalChecks = checks.length
  const healthyPercent = totalChecks > 0 ? Math.round((summary.healthy / totalChecks) * 100) : 0

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Health Engine</h1>
            <p className="text-muted-foreground">Monitor system health and service status</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={fetchHealth}>Refresh</Button>
            <Button onClick={() => setShowCreate(true)}>Add Check</Button>
          </div>
        </div>

        <div className="mb-8 grid gap-4 md:grid-cols-4">
          <MetricCard title="Overall Health" value={`${healthyPercent}%`} subtitle={`${summary.healthy} of ${totalChecks} healthy`} />
          <MetricCard title="Healthy" value={summary.healthy} subtitle="All systems operational" />
          <MetricCard title="Degraded" value={summary.degraded} subtitle="Partial issues" />
          <MetricCard title="Unhealthy" value={summary.unhealthy} subtitle="Critical failures" />
        </div>

        {showCreate && (
          <div className="mb-6 rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">New Health Check</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <input
                type="text"
                placeholder="Check name"
                value={newCheck.name}
                onChange={(e) => setNewCheck({ ...newCheck, name: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <select
                value={newCheck.type}
                onChange={(e) => setNewCheck({ ...newCheck, type: e.target.value as HealthCheck["type"] })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              >
                <option value="http">HTTP</option>
                <option value="tcp">TCP</option>
                <option value="memory">Memory</option>
                <option value="disk">Disk</option>
                <option value="custom">Custom</option>
              </select>
              <input
                type="text"
                placeholder="Target (URL or endpoint)"
                value={newCheck.target}
                onChange={(e) => setNewCheck({ ...newCheck, target: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <input
                type="number"
                placeholder="Interval (ms)"
                value={newCheck.interval}
                onChange={(e) => setNewCheck({ ...newCheck, interval: parseInt(e.target.value) })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <div className="flex gap-2 md:col-span-2">
                <Button onClick={createCheck}>Create</Button>
                <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Health Checks ({checks.length})</h2>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : checks.length === 0 ? (
              <p className="text-muted-foreground">No health checks configured</p>
            ) : (
              <div className="space-y-3">
                {checks.map((check) => (
                  <div
                    key={check.id}
                    onClick={() => setSelectedCheck(check.id)}
                    className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                      selectedCheck === check.id
                        ? "border-primary bg-primary/10"
                        : "border-border bg-card hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`h-3 w-3 rounded-full ${getStatusDot(check.lastStatus)}`} />
                        <div>
                          <h3 className="font-medium text-foreground">{check.name}</h3>
                          <p className="text-sm text-muted-foreground">{check.type.toUpperCase()} - {check.target}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {check.lastLatency && (
                          <span className="text-sm text-muted-foreground">{check.lastLatency}ms</span>
                        )}
                        <span className={`rounded-full px-2 py-1 text-xs font-medium ${getStatusColor(check.lastStatus)}`}>
                          {check.lastStatus}
                        </span>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center gap-2">
                      <Button size="sm" onClick={(e) => { e.stopPropagation(); runCheck(check.id) }}>
                        Run Now
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline" 
                        onClick={(e) => { e.stopPropagation(); toggleCheck(check.id, !check.enabled) }}
                      >
                        {check.enabled ? "Disable" : "Enable"}
                      </Button>
                      <Button 
                        size="sm" 
                        variant="destructive" 
                        onClick={(e) => { e.stopPropagation(); deleteCheck(check.id) }}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h2 className="mb-4 text-lg font-semibold text-foreground">Recent History</h2>
            <div className="rounded-lg border border-border bg-card">
              {history.length === 0 ? (
                <p className="p-4 text-muted-foreground">No history yet</p>
              ) : (
                <div className="max-h-96 divide-y divide-border overflow-y-auto">
                  {history.slice(0, 20).map((entry, i) => {
                    const check = checks.find((c) => c.id === entry.checkId)
                    return (
                      <div key={i} className="p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-foreground">{check?.name || entry.checkId}</span>
                          <span className={`rounded px-1.5 py-0.5 text-xs ${getStatusColor(entry.status)}`}>
                            {entry.status}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
                          <span>{entry.latency}ms</span>
                          <span>{new Date(entry.timestamp).toLocaleTimeString()}</span>
                        </div>
                        {entry.error && (
                          <p className="mt-1 text-xs text-red-400">{entry.error}</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
