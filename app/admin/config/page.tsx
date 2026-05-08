"use client"

import { useState, useEffect } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"
import { Button } from "@/components/ui/button"

interface ConfigEntry {
  key: string
  value: unknown
  type: "string" | "number" | "boolean" | "json" | "secret"
  description?: string
  category: string
  encrypted: boolean
  updatedAt: string
  updatedBy?: string
}

interface ConfigHistory {
  key: string
  oldValue: unknown
  newValue: unknown
  changedBy: string
  changedAt: string
}

export default function ConfigPage() {
  const [configs, setConfigs] = useState<ConfigEntry[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>("all")
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [history, setHistory] = useState<ConfigHistory[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [newConfig, setNewConfig] = useState({
    key: "",
    value: "",
    type: "string" as const,
    description: "",
    category: "general",
  })

  const fetchConfigs = async () => {
    try {
      const res = await fetch("/api/admin/config")
      const data = await res.json()
      setConfigs(data.configs || [])
      setCategories(data.categories || [])
    } catch (error) {
      console.error("Failed to fetch configs:", error)
    } finally {
      setLoading(false)
    }
  }

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/admin/config?action=history")
      const data = await res.json()
      setHistory(data.history || [])
    } catch (error) {
      console.error("Failed to fetch history:", error)
    }
  }

  useEffect(() => {
    fetchConfigs()
  }, [])

  const createConfig = async () => {
    if (!newConfig.key) return
    try {
      const res = await fetch("/api/admin/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set", config: newConfig }),
      })
      const data = await res.json()
      if (data.config) {
        fetchConfigs()
        setNewConfig({ key: "", value: "", type: "string", description: "", category: "general" })
        setShowCreate(false)
      }
    } catch (error) {
      console.error("Failed to create config:", error)
    }
  }

  const updateConfig = async (key: string) => {
    try {
      await fetch("/api/admin/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "set", config: { key, value: editValue } }),
      })
      setEditingKey(null)
      fetchConfigs()
    } catch (error) {
      console.error("Failed to update config:", error)
    }
  }

  const deleteConfig = async (key: string) => {
    if (!confirm(`Delete config "${key}"?`)) return
    try {
      await fetch("/api/admin/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", key }),
      })
      fetchConfigs()
    } catch (error) {
      console.error("Failed to delete config:", error)
    }
  }

  const filteredConfigs = selectedCategory === "all"
    ? configs
    : configs.filter((c) => c.category === selectedCategory)

  const formatValue = (config: ConfigEntry) => {
    if (config.encrypted || config.type === "secret") return "••••••••"
    if (typeof config.value === "object") return JSON.stringify(config.value)
    return String(config.value)
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Config Builder</h1>
            <p className="text-muted-foreground">Manage dynamic application settings</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { fetchHistory(); setShowHistory(!showHistory) }}>
              {showHistory ? "Hide History" : "View History"}
            </Button>
            <Button onClick={() => setShowCreate(true)}>Add Config</Button>
          </div>
        </div>

        {showCreate && (
          <div className="mb-6 rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">New Configuration</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <input
                type="text"
                placeholder="Key (e.g., app.feature.enabled)"
                value={newConfig.key}
                onChange={(e) => setNewConfig({ ...newConfig, key: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <select
                value={newConfig.type}
                onChange={(e) => setNewConfig({ ...newConfig, type: e.target.value as ConfigEntry["type"] })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              >
                <option value="string">String</option>
                <option value="number">Number</option>
                <option value="boolean">Boolean</option>
                <option value="json">JSON</option>
                <option value="secret">Secret</option>
              </select>
              <input
                type="text"
                placeholder="Value"
                value={newConfig.value}
                onChange={(e) => setNewConfig({ ...newConfig, value: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <input
                type="text"
                placeholder="Category"
                value={newConfig.category}
                onChange={(e) => setNewConfig({ ...newConfig, category: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <textarea
                placeholder="Description"
                value={newConfig.description}
                onChange={(e) => setNewConfig({ ...newConfig, description: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground md:col-span-2"
                rows={2}
              />
              <div className="flex gap-2 md:col-span-2">
                <Button onClick={createConfig}>Create</Button>
                <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        <div className="mb-6 flex gap-2">
          <Button
            variant={selectedCategory === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedCategory("all")}
          >
            All ({configs.length})
          </Button>
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={selectedCategory === cat ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategory(cat)}
            >
              {cat} ({configs.filter((c) => c.category === cat).length})
            </Button>
          ))}
        </div>

        {showHistory ? (
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border p-4">
              <h2 className="font-semibold text-foreground">Configuration History</h2>
            </div>
            <div className="divide-y divide-border">
              {history.length === 0 ? (
                <p className="p-4 text-muted-foreground">No history available</p>
              ) : (
                history.slice(0, 50).map((entry, i) => (
                  <div key={i} className="p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-sm text-primary">{entry.key}</span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(entry.changedAt).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-1 text-sm">
                      <span className="text-red-400">{String(entry.oldValue)}</span>
                      <span className="text-muted-foreground"> → </span>
                      <span className="text-green-400">{String(entry.newValue)}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">by {entry.changedBy}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-card">
            <table className="w-full">
              <thead className="border-b border-border">
                <tr className="text-left text-sm text-muted-foreground">
                  <th className="p-4">Key</th>
                  <th className="p-4">Value</th>
                  <th className="p-4">Type</th>
                  <th className="p-4">Category</th>
                  <th className="p-4">Updated</th>
                  <th className="p-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr><td colSpan={6} className="p-4 text-muted-foreground">Loading...</td></tr>
                ) : filteredConfigs.length === 0 ? (
                  <tr><td colSpan={6} className="p-4 text-muted-foreground">No configurations found</td></tr>
                ) : (
                  filteredConfigs.map((config) => (
                    <tr key={config.key}>
                      <td className="p-4 font-mono text-sm text-foreground">{config.key}</td>
                      <td className="p-4">
                        {editingKey === config.key ? (
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="w-full rounded border border-border bg-background px-2 py-1 text-sm text-foreground"
                            autoFocus
                          />
                        ) : (
                          <span className="font-mono text-sm text-muted-foreground">
                            {formatValue(config)}
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-sm text-muted-foreground">{config.type}</td>
                      <td className="p-4 text-sm text-muted-foreground">{config.category}</td>
                      <td className="p-4 text-sm text-muted-foreground">
                        {new Date(config.updatedAt).toLocaleDateString()}
                      </td>
                      <td className="p-4">
                        <div className="flex gap-2">
                          {editingKey === config.key ? (
                            <>
                              <Button size="sm" onClick={() => updateConfig(config.key)}>Save</Button>
                              <Button size="sm" variant="outline" onClick={() => setEditingKey(null)}>Cancel</Button>
                            </>
                          ) : (
                            <>
                              <Button size="sm" variant="outline" onClick={() => { setEditingKey(config.key); setEditValue(formatValue(config)) }}>
                                Edit
                              </Button>
                              <Button size="sm" variant="destructive" onClick={() => deleteConfig(config.key)}>
                                Delete
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
