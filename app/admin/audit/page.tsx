"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AdminSidebar } from "@/components/admin/sidebar"

interface AuditEntry {
  id: string
  timestamp: number
  action: string
  actor: string
  result: string
  detail: string
  ip?: string
}

const resultColors: Record<string, string> = {
  success: "bg-emerald-500/10 text-emerald-400",
  failure: "bg-red-500/10 text-red-400",
  denied: "bg-yellow-500/10 text-yellow-400",
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState("")
  const [resultFilter, setResultFilter] = useState("")
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  async function fetchAudit() {
    const params = new URLSearchParams()
    if (search) params.set("search", search)
    if (resultFilter) params.set("result", resultFilter)
    params.set("limit", "100")

    try {
      const res = await fetch(`/api/admin/audit?${params}`)
      if (res.status === 401) { router.push("/admin/login"); return }
      const data = await res.json()
      setEntries(data.entries || [])
      setTotal(data.total || 0)
    } catch {
      router.push("/admin/login")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAudit()
    const interval = setInterval(fetchAudit, 5000)
    return () => clearInterval(interval)
  }, [search, resultFilter])

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Audit Trail</h1>
          <p className="text-sm text-muted-foreground">{total} total audit entries - who did what, when</p>
        </div>

        <div className="mb-4 flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Search audit log..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded-lg border border-border bg-card px-4 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
          />
          <select
            value={resultFilter}
            onChange={(e) => setResultFilter(e.target.value)}
            className="rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
          >
            <option value="">All Results</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="denied">Denied</option>
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : entries.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-12 text-center text-muted-foreground">
            No audit entries found
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Time</th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Action</th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Actor</th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Result</th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="border-b border-border/50 last:border-0">
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="rounded bg-muted/50 px-2 py-0.5 text-xs font-medium text-foreground">
                          {entry.action}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">{entry.actor}</td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${resultColors[entry.result] || "bg-muted text-muted-foreground"}`}>
                          {entry.result}
                        </span>
                      </td>
                      <td className="max-w-xs truncate px-4 py-3 text-xs text-muted-foreground">{entry.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
