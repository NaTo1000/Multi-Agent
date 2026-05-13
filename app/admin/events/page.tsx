"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AdminSidebar } from "@/components/admin/sidebar"

interface TelemetryEvent {
  id: string
  timestamp: number
  severity: string
  category: string
  message: string
  source: string
  metadata?: Record<string, unknown>
}

const severityColors: Record<string, string> = {
  info: "bg-blue-500/10 text-blue-400",
  warning: "bg-yellow-500/10 text-yellow-400",
  error: "bg-red-500/10 text-red-400",
  critical: "bg-red-600/20 text-red-300",
}

export default function EventsPage() {
  const [events, setEvents] = useState<TelemetryEvent[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState("")
  const [severityFilter, setSeverityFilter] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("")
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  async function fetchEvents() {
    const params = new URLSearchParams()
    if (search) params.set("search", search)
    if (severityFilter) params.set("severity", severityFilter)
    if (categoryFilter) params.set("category", categoryFilter)
    params.set("limit", "100")

    try {
      const res = await fetch(`/api/admin/events?${params}`)
      if (res.status === 401) { router.push("/admin/login"); return }
      const data = await res.json()
      setEvents(data.events || [])
      setTotal(data.total || 0)
    } catch {
      router.push("/admin/login")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
    const interval = setInterval(fetchEvents, 3000)
    return () => clearInterval(interval)
  }, [search, severityFilter, categoryFilter])

  async function handleClear() {
    await fetch("/api/admin/events", { method: "DELETE" })
    fetchEvents()
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Event Log</h1>
            <p className="text-sm text-muted-foreground">{total} total events</p>
          </div>
          <button
            onClick={handleClear}
            className="rounded-lg border border-red-500/30 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
          >
            Clear All
          </button>
        </div>

        <div className="mb-4 flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Search events..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-border bg-card px-4 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
          />
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
          >
            <option value="">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
          >
            <option value="">All Categories</option>
            <option value="system">System</option>
            <option value="auth">Auth</option>
            <option value="stripe">Stripe</option>
            <option value="deployment">Deployment</option>
            <option value="admin">Admin</option>
            <option value="api">API</option>
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : events.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-12 text-center text-muted-foreground">
            No events found
          </div>
        ) : (
          <div className="space-y-2">
            {events.map((event) => (
              <div
                key={event.id}
                className="flex items-start gap-4 rounded-lg border border-border bg-card p-4"
              >
                <span className={`mt-0.5 rounded-md px-2 py-1 text-xs font-medium ${severityColors[event.severity] || "bg-muted text-muted-foreground"}`}>
                  {event.severity.toUpperCase()}
                </span>
                <div className="flex-1">
                  <p className="text-sm text-foreground">{event.message}</p>
                  <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>{new Date(event.timestamp).toLocaleString()}</span>
                    <span className="rounded bg-muted/50 px-1.5 py-0.5">{event.category}</span>
                    <span>{event.source}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
