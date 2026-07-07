"use client"

import { useState, useEffect, useCallback } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"

// ─── Types ───

type SnippetStatus = "beta" | "stable" | "deprecated" | "archived"
type ErosionStatus = "stable" | "eroding" | "critical" | "insufficient-data"

interface ErosionMetrics {
  runCount: number
  errorRate: number
  avgDurationMs: number
  p95DurationMs: number
  latencyTrend: number
  memoryTrend: number
  erosionScore: number
  status: ErosionStatus
}

interface SnippetRunResult {
  id: string
  timestamp: number
  durationMs: number
  memoryDeltaKb: number
  output: string
  error: string | null
  success: boolean
}

interface Snippet {
  id: string
  name: string
  description: string
  language: string
  code: string
  tags: string[]
  status: SnippetStatus
  createdAt: number
  createdBy: string
  updatedAt: number
  updatedBy: string
  runs: SnippetRunResult[]
  erosion: ErosionMetrics
}

interface Stats {
  total: number
  beta: number
  stable: number
  deprecated: number
  archived: number
  eroding: number
  critical: number
  totalRuns: number
}

// ─── Helpers ───

const STATUS_STYLES: Record<SnippetStatus, string> = {
  beta: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  stable: "bg-green-500/10 text-green-400 border-green-500/30",
  deprecated: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  archived: "bg-muted text-muted-foreground border-border",
}

const EROSION_STYLES: Record<ErosionStatus, { bar: string; text: string; label: string }> = {
  "stable": { bar: "bg-green-500", text: "text-green-400", label: "Stable" },
  "eroding": { bar: "bg-yellow-400", text: "text-yellow-400", label: "Eroding" },
  "critical": { bar: "bg-red-500", text: "text-red-400", label: "Critical" },
  "insufficient-data": { bar: "bg-muted-foreground", text: "text-muted-foreground", label: "No data" },
}

function ErosionBar({ score, status }: { score: number; status: ErosionStatus }) {
  const style = EROSION_STYLES[status]
  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between">
        <span className={`text-xs font-medium ${style.text}`}>{style.label}</span>
        <span className="text-xs text-muted-foreground">{score}/100</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-300 ${style.bar}`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  )
}

function TrendArrow({ value, unit }: { value: number; unit: string }) {
  if (Math.abs(value) < 0.01) return <span className="text-xs text-muted-foreground">→ flat</span>
  const up = value > 0
  return (
    <span className={`text-xs font-medium ${up ? "text-red-400" : "text-green-400"}`}>
      {up ? "↑" : "↓"} {Math.abs(value).toFixed(2)}{unit}/run
    </span>
  )
}

// ─── Page ───

export default function SnippetsPage() {
  const [snippets, setSnippets] = useState<Snippet[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [selected, setSelected] = useState<Snippet | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [lastRun, setLastRun] = useState<SnippetRunResult | null>(null)
  const [statusFilter, setStatusFilter] = useState<SnippetStatus | "all">("all")
  const [showCreate, setShowCreate] = useState(false)
  const [newSnippet, setNewSnippet] = useState({ name: "", description: "", code: "", tags: "" })

  const fetchSnippets = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (statusFilter !== "all") params.set("status", statusFilter)
      const res = await fetch(`/api/admin/snippets?${params}`)
      if (!res.ok) return
      const data = await res.json()
      setSnippets(data.snippets ?? [])
      setStats(data.stats ?? null)
      // Refresh selected snippet data
      if (selected) {
        const fresh = (data.snippets as Snippet[]).find((s) => s.id === selected.id)
        if (fresh) setSelected(fresh)
      }
    } catch (err) {
      console.error("Failed to fetch snippets:", err)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, selected])

  useEffect(() => {
    fetchSnippets()
  }, [statusFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate() {
    if (!newSnippet.name || !newSnippet.code) return
    try {
      const res = await fetch("/api/admin/snippets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "create",
          name: newSnippet.name,
          description: newSnippet.description,
          code: newSnippet.code,
          language: "javascript",
          tags: newSnippet.tags.split(",").map((t) => t.trim()).filter(Boolean),
        }),
      })
      const data = await res.json()
      if (data.snippet) {
        setNewSnippet({ name: "", description: "", code: "", tags: "" })
        setShowCreate(false)
        await fetchSnippets()
        setSelected(data.snippet)
      }
    } catch (err) {
      console.error("Failed to create snippet:", err)
    }
  }

  async function handleStatusChange(id: string, status: SnippetStatus) {
    try {
      await fetch("/api/admin/snippets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "update", id, status }),
      })
      await fetchSnippets()
    } catch (err) {
      console.error("Failed to update snippet:", err)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this snippet and all its run history?")) return
    try {
      await fetch("/api/admin/snippets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", id }),
      })
      if (selected?.id === id) {
        setSelected(null)
        setLastRun(null)
      }
      await fetchSnippets()
    } catch (err) {
      console.error("Failed to delete snippet:", err)
    }
  }

  async function handleRun(id: string) {
    setRunning(true)
    setLastRun(null)
    try {
      const res = await fetch("/api/admin/snippets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "run", id }),
      })
      const data = await res.json()
      if (data.result) {
        setLastRun(data.result)
        await fetchSnippets()
      }
    } catch (err) {
      console.error("Failed to run snippet:", err)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Snippet Runtime</h1>
            <p className="text-sm text-muted-foreground">
              Lite beta testing — run snippets and track runtime erosion over time
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            New Snippet
          </button>
        </div>

        {/* Stats bar */}
        {stats && (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {[
              { label: "Total", value: stats.total, color: "text-foreground" },
              { label: "Beta", value: stats.beta, color: "text-blue-400" },
              { label: "Stable", value: stats.stable, color: "text-green-400" },
              { label: "Deprecated", value: stats.deprecated, color: "text-yellow-400" },
              { label: "Archived", value: stats.archived, color: "text-muted-foreground" },
              { label: "Eroding", value: stats.eroding, color: "text-yellow-400" },
              { label: "Critical", value: stats.critical, color: "text-red-400" },
              { label: "Total Runs", value: stats.totalRuns, color: "text-foreground" },
            ].map((s) => (
              <div key={s.label} className="rounded-lg border border-border bg-card p-3 text-center">
                <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Create form */}
        {showCreate && (
          <div className="mb-6 rounded-xl border border-border bg-card p-5">
            <h2 className="mb-4 text-sm font-semibold text-foreground">New Snippet</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                type="text"
                placeholder="Name"
                value={newSnippet.name}
                onChange={(e) => setNewSnippet({ ...newSnippet, name: e.target.value })}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
              />
              <input
                type="text"
                placeholder="Tags (comma-separated)"
                value={newSnippet.tags}
                onChange={(e) => setNewSnippet({ ...newSnippet, tags: e.target.value })}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
              />
              <input
                type="text"
                placeholder="Description"
                value={newSnippet.description}
                onChange={(e) => setNewSnippet({ ...newSnippet, description: e.target.value })}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none sm:col-span-2"
              />
              <textarea
                placeholder="JavaScript code..."
                value={newSnippet.code}
                onChange={(e) => setNewSnippet({ ...newSnippet, code: e.target.value })}
                rows={6}
                className="rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none sm:col-span-2"
              />
              <div className="flex gap-2 sm:col-span-2">
                <button
                  onClick={handleCreate}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Create
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Status filter tabs */}
        <div className="mb-4 flex flex-wrap gap-2">
          {(["all", "beta", "stable", "deprecated", "archived"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                statusFilter === f
                  ? "bg-primary text-primary-foreground"
                  : "border border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-5">
          {/* ── Snippet list ── */}
          <div className="lg:col-span-2">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : snippets.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">No snippets found</p>
            ) : (
              <div className="space-y-3">
                {snippets.map((snippet) => (
                  <div
                    key={snippet.id}
                    onClick={() => { setSelected(snippet); setLastRun(null) }}
                    className={`cursor-pointer rounded-xl border p-4 transition-all ${
                      selected?.id === snippet.id
                        ? "border-primary bg-primary/5"
                        : "border-border bg-card hover:border-primary/40"
                    }`}
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">{snippet.name}</p>
                        <p className="truncate text-xs text-muted-foreground">{snippet.description}</p>
                      </div>
                      <span className={`flex-shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[snippet.status]}`}>
                        {snippet.status}
                      </span>
                    </div>
                    <ErosionBar score={snippet.erosion.erosionScore} status={snippet.erosion.status} />
                    <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{snippet.erosion.runCount} runs</span>
                      {snippet.erosion.runCount > 0 && (
                        <span>{snippet.erosion.avgDurationMs}ms avg</span>
                      )}
                      {snippet.tags.slice(0, 2).map((t) => (
                        <span key={t} className="rounded bg-muted px-1.5 py-0.5">{t}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Detail panel ── */}
          <div className="lg:col-span-3">
            {!selected ? (
              <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-border py-24 text-sm text-muted-foreground">
                Select a snippet to view details
              </div>
            ) : (
              <div className="space-y-4">
                {/* Header */}
                <div className="rounded-xl border border-border bg-card p-5">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-base font-semibold text-foreground">{selected.name}</h2>
                      <p className="text-sm text-muted-foreground">{selected.description}</p>
                    </div>
                    <div className="flex flex-shrink-0 flex-wrap gap-2">
                      <select
                        value={selected.status}
                        onChange={(e) => handleStatusChange(selected.id, e.target.value as SnippetStatus)}
                        className={`rounded-full border px-2 py-0.5 text-xs font-medium focus:outline-none ${STATUS_STYLES[selected.status]}`}
                      >
                        <option value="beta">beta</option>
                        <option value="stable">stable</option>
                        <option value="deprecated">deprecated</option>
                        <option value="archived">archived</option>
                      </select>
                    </div>
                  </div>
                  <div className="mb-4 flex flex-wrap gap-1">
                    {selected.tags.map((t) => (
                      <span key={t} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{t}</span>
                    ))}
                  </div>
                  {/* Code */}
                  <pre className="mb-4 max-h-48 overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-xs text-foreground">
                    {selected.code}
                  </pre>
                  {/* Actions */}
                  <div className="flex flex-wrap gap-2">
                    <button
                      disabled={running}
                      onClick={() => handleRun(selected.id)}
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      {running ? "Running…" : "▶ Run"}
                    </button>
                    <button
                      onClick={() => handleDelete(selected.id)}
                      className="rounded-lg border border-red-500/40 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-500/10"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {/* Last run output */}
                {lastRun && (
                  <div className={`rounded-xl border p-4 ${lastRun.success ? "border-green-500/30 bg-green-500/5" : "border-red-500/30 bg-red-500/5"}`}>
                    <div className="mb-2 flex items-center justify-between">
                      <span className={`text-xs font-semibold uppercase tracking-wide ${lastRun.success ? "text-green-400" : "text-red-400"}`}>
                        {lastRun.success ? "✓ Run succeeded" : "✕ Run failed"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {lastRun.durationMs}ms · {lastRun.memoryDeltaKb > 0 ? "+" : ""}{lastRun.memoryDeltaKb} KB heap
                      </span>
                    </div>
                    {lastRun.error && (
                      <pre className="mb-2 rounded bg-red-900/20 p-2 font-mono text-xs text-red-300">{lastRun.error}</pre>
                    )}
                    {lastRun.output && (
                      <pre className="rounded bg-muted p-2 font-mono text-xs text-foreground whitespace-pre-wrap">{lastRun.output}</pre>
                    )}
                    {!lastRun.error && !lastRun.output && (
                      <p className="text-xs text-muted-foreground italic">(no output)</p>
                    )}
                  </div>
                )}

                {/* Erosion metrics */}
                <div className="rounded-xl border border-border bg-card p-5">
                  <h3 className="mb-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Runtime Erosion Analysis
                  </h3>
                  <div className="mb-4">
                    <ErosionBar score={selected.erosion.erosionScore} status={selected.erosion.status} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-lg border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">Total Runs</p>
                      <p className="text-lg font-bold text-foreground">{selected.erosion.runCount}</p>
                    </div>
                    <div className="rounded-lg border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">Error Rate</p>
                      <p className={`text-lg font-bold ${selected.erosion.errorRate > 0.1 ? "text-red-400" : "text-green-400"}`}>
                        {(selected.erosion.errorRate * 100).toFixed(0)}%
                      </p>
                    </div>
                    <div className="rounded-lg border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">Avg Duration</p>
                      <p className="text-lg font-bold text-foreground">{selected.erosion.avgDurationMs}ms</p>
                    </div>
                    <div className="rounded-lg border border-border bg-background p-3">
                      <p className="text-xs text-muted-foreground">p95 Duration</p>
                      <p className="text-lg font-bold text-foreground">{selected.erosion.p95DurationMs}ms</p>
                    </div>
                    <div className="rounded-lg border border-border bg-background p-3">
                      <p className="mb-1 text-xs text-muted-foreground">Latency Trend</p>
                      <TrendArrow value={selected.erosion.latencyTrend} unit="ms" />
                    </div>
                    <div className="rounded-lg border border-border bg-background p-3">
                      <p className="mb-1 text-xs text-muted-foreground">Memory Trend</p>
                      <TrendArrow value={selected.erosion.memoryTrend} unit=" KB" />
                    </div>
                  </div>
                </div>

                {/* Run history */}
                {selected.runs.length > 0 && (
                  <div className="rounded-xl border border-border bg-card">
                    <div className="border-b border-border px-5 py-3">
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Run History ({selected.runs.length})
                      </h3>
                    </div>
                    <div className="max-h-64 divide-y divide-border overflow-y-auto">
                      {selected.runs.slice(0, 50).map((run) => (
                        <div key={run.id} className="flex items-center gap-4 px-5 py-2.5">
                          <span className={`h-2 w-2 flex-shrink-0 rounded-full ${run.success ? "bg-green-400" : "bg-red-400"}`} />
                          <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground">
                            {new Date(run.timestamp).toLocaleString()}
                          </span>
                          <span className="flex-shrink-0 text-xs text-foreground">{run.durationMs}ms</span>
                          <span className={`flex-shrink-0 text-xs ${run.memoryDeltaKb > 0 ? "text-yellow-400" : "text-muted-foreground"}`}>
                            {run.memoryDeltaKb > 0 ? "+" : ""}{run.memoryDeltaKb} KB
                          </span>
                          {run.error && (
                            <span className="flex-shrink-0 rounded bg-red-500/10 px-1.5 py-0.5 text-xs text-red-400">err</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
