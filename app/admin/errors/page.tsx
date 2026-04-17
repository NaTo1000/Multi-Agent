"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AdminSidebar } from "@/components/admin/sidebar"

interface TrackedError {
  id: string
  timestamp: number
  message: string
  stack?: string
  source: string
  status: string
  occurrences: number
  firstSeen: number
  lastSeen: number
  repairAttempts: number
  maxRepairAttempts: number
  repairLog: { timestamp: number; action: string; result: string; detail: string }[]
}

interface ErrorStats {
  total: number
  active: number
  repairing: number
  resolved: number
  dismissed: number
  selfRepairEnabled: boolean
}

const statusColors: Record<string, string> = {
  active: "bg-red-500/10 text-red-400",
  repairing: "bg-yellow-500/10 text-yellow-400",
  resolved: "bg-emerald-500/10 text-emerald-400",
  dismissed: "bg-muted text-muted-foreground",
}

export default function ErrorsPage() {
  const [errors, setErrors] = useState<TrackedError[]>([])
  const [stats, setStats] = useState<ErrorStats | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [search, setSearch] = useState("")
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  async function fetchErrors() {
    const params = new URLSearchParams()
    if (statusFilter) params.set("status", statusFilter)
    if (search) params.set("search", search)

    try {
      const [errRes, statsRes] = await Promise.all([
        fetch(`/api/admin/errors?${params}`),
        fetch("/api/admin/errors?stats=true"),
      ])
      if (errRes.status === 401) { router.push("/admin/login"); return }
      const errData = await errRes.json()
      const statsData = await statsRes.json()
      setErrors(errData.errors || [])
      setStats(statsData)
    } catch {
      router.push("/admin/login")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchErrors()
    const interval = setInterval(fetchErrors, 4000)
    return () => clearInterval(interval)
  }, [statusFilter, search])

  async function handleRepair(errorId: string) {
    await fetch("/api/admin/errors", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "repair", errorId }),
    })
    fetchErrors()
  }

  async function handleDismiss(errorId: string) {
    await fetch("/api/admin/errors", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "dismiss", errorId }),
    })
    fetchErrors()
  }

  async function toggleSelfRepair() {
    const newState = stats ? !stats.selfRepairEnabled : true
    await fetch("/api/admin/errors", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "toggle_self_repair", enabled: newState }),
    })
    fetchErrors()
  }

  async function handleClearResolved() {
    await fetch("/api/admin/errors", { method: "DELETE" })
    fetchErrors()
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Error Logger</h1>
            <p className="text-sm text-muted-foreground">
              {stats ? `${stats.active} active, ${stats.resolved} resolved` : "Loading..."}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={toggleSelfRepair}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${
                stats?.selfRepairEnabled
                  ? "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                  : "bg-red-500/10 text-red-400 hover:bg-red-500/20"
              }`}
            >
              Self-Repair: {stats?.selfRepairEnabled ? "ON" : "OFF"}
            </button>
            <button
              onClick={handleClearResolved}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground hover:bg-accent"
            >
              Clear Resolved
            </button>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Search errors..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-border bg-card px-4 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="repairing">Repairing</option>
            <option value="resolved">Resolved</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : errors.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-12 text-center text-muted-foreground">
            No errors found
          </div>
        ) : (
          <div className="space-y-3">
            {errors.map((err) => (
              <div key={err.id} className="rounded-xl border border-border bg-card">
                <button
                  onClick={() => setExpanded(expanded === err.id ? null : err.id)}
                  className="flex w-full items-start gap-4 p-4 text-left"
                >
                  <span className={`mt-0.5 rounded-md px-2 py-1 text-xs font-medium ${statusColors[err.status]}`}>
                    {err.status.toUpperCase()}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">{err.message}</p>
                    <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>{err.source}</span>
                      <span>x{err.occurrences}</span>
                      <span>Repairs: {err.repairAttempts}/{err.maxRepairAttempts}</span>
                      <span>{new Date(err.lastSeen).toLocaleString()}</span>
                    </div>
                  </div>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className={`text-muted-foreground transition-transform ${expanded === err.id ? "rotate-180" : ""}`}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {expanded === err.id && (
                  <div className="border-t border-border p-4">
                    {err.stack && (
                      <pre className="mb-3 overflow-auto rounded-lg bg-background p-3 text-xs text-muted-foreground">
                        {err.stack}
                      </pre>
                    )}

                    {err.repairLog.length > 0 && (
                      <div className="mb-3">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Repair History</p>
                        <div className="space-y-1">
                          {err.repairLog.map((entry, i) => (
                            <div key={i} className="flex items-center gap-3 text-xs">
                              <span className={entry.result === "success" ? "text-emerald-400" : "text-red-400"}>
                                [{entry.result}]
                              </span>
                              <span className="text-muted-foreground">{entry.action}</span>
                              <span className="text-muted-foreground">{entry.detail}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2">
                      {err.status === "active" && (
                        <>
                          <button
                            onClick={() => handleRepair(err.id)}
                            className="rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20"
                          >
                            Attempt Repair
                          </button>
                          <button
                            onClick={() => handleDismiss(err.id)}
                            className="rounded-lg bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted/80"
                          >
                            Dismiss
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
