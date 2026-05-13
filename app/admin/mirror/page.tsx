"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AdminSidebar } from "@/components/admin/sidebar"

interface Snapshot {
  id: string
  number: number
  timestamp: number
  label: string
  description: string
  size: number
  createdBy: string
}

export default function MirrorPage() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [label, setLabel] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [rollbackTarget, setRollbackTarget] = useState<string | null>(null)
  const router = useRouter()

  async function fetchSnapshots() {
    try {
      const res = await fetch("/api/admin/mirror")
      if (res.status === 401) { router.push("/admin/login"); return }
      const data = await res.json()
      setSnapshots(data)
    } catch {
      router.push("/admin/login")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSnapshots()
  }, [])

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!label) return
    setCreating(true)
    await fetch("/api/admin/mirror", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, description }),
    })
    setLabel("")
    setDescription("")
    setCreating(false)
    fetchSnapshots()
  }

  async function handleRollback(id: string) {
    await fetch("/api/admin/mirror", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ snapshotId: id }),
    })
    setRollbackTarget(null)
    fetchSnapshots()
  }

  async function handleDelete(id: string) {
    await fetch(`/api/admin/mirror?id=${id}`, { method: "DELETE" })
    fetchSnapshots()
  }

  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Mirror / Snapshots</h1>
          <p className="text-sm text-muted-foreground">Create snapshots and rollback to previous states</p>
        </div>

        <form onSubmit={handleCreate} className="mb-6 rounded-xl border border-border bg-card p-5">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Create Snapshot</h2>
          <div className="flex flex-wrap gap-3">
            <input
              type="text"
              placeholder="Snapshot label..."
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
              required
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="flex-1 rounded-lg border border-border bg-background px-4 py-2 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:outline-none"
            />
            <button
              type="submit"
              disabled={creating || !label}
              className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
        </form>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : snapshots.length === 0 ? (
          <div className="rounded-xl border border-border bg-card p-12 text-center text-muted-foreground">
            No snapshots yet
          </div>
        ) : (
          <div className="space-y-3">
            {snapshots.map((snap) => (
              <div key={snap.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-bold text-primary">#{snap.number}</span>
                      <h3 className="text-sm font-semibold text-foreground">{snap.label}</h3>
                    </div>
                    {snap.description && (
                      <p className="mt-1 text-xs text-muted-foreground">{snap.description}</p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>{new Date(snap.timestamp).toLocaleString()}</span>
                      <span>{formatBytes(snap.size)}</span>
                      <span>by {snap.createdBy}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {rollbackTarget === snap.id ? (
                      <>
                        <button
                          onClick={() => handleRollback(snap.id)}
                          className="rounded-lg bg-yellow-500/10 px-3 py-1.5 text-xs font-medium text-yellow-400 hover:bg-yellow-500/20"
                        >
                          Confirm Rollback
                        </button>
                        <button
                          onClick={() => setRollbackTarget(null)}
                          className="rounded-lg bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => setRollbackTarget(snap.id)}
                          className="rounded-lg border border-yellow-500/30 px-3 py-1.5 text-xs font-medium text-yellow-400 hover:bg-yellow-500/10"
                        >
                          Rollback
                        </button>
                        <button
                          onClick={() => handleDelete(snap.id)}
                          className="rounded-lg border border-red-500/30 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/10"
                        >
                          Delete
                        </button>
                      </>
                    )}
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
