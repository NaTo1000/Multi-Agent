"use client"

import { useState, useEffect } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"
import { Button } from "@/components/ui/button"
import { MetricCard } from "@/components/admin/metric-card"

interface WebhookEndpoint {
  id: string
  name: string
  url: string
  secret?: string
  events: string[]
  enabled: boolean
  createdAt: string
  lastTriggered?: string
}

interface WebhookDelivery {
  id: string
  webhookId: string
  eventType: string
  payload: Record<string, unknown>
  status: "pending" | "success" | "failed"
  statusCode?: number
  response?: string
  attempts: number
  createdAt: string
  completedAt?: string
}

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([])
  const [stats, setStats] = useState({ total: 0, enabled: 0, deliveries: 0, successRate: 0 })
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedWebhook, setSelectedWebhook] = useState<WebhookEndpoint | null>(null)
  const [showTestEvent, setShowTestEvent] = useState(false)
  const [testEvent, setTestEvent] = useState({ type: "test.event", payload: "{}" })
  const [newWebhook, setNewWebhook] = useState({
    name: "",
    url: "",
    secret: "",
    events: ["*"],
  })

  const fetchWebhooks = async () => {
    try {
      const res = await fetch("/api/admin/webhook")
      const data = await res.json()
      setWebhooks(data.webhooks || [])
      setStats(data.stats || { total: 0, enabled: 0, deliveries: 0, successRate: 0 })
    } catch (error) {
      console.error("Failed to fetch webhooks:", error)
    } finally {
      setLoading(false)
    }
  }

  const fetchDeliveries = async () => {
    try {
      const res = await fetch("/api/admin/webhook?action=deliveries")
      const data = await res.json()
      setDeliveries(data.deliveries || [])
    } catch (error) {
      console.error("Failed to fetch deliveries:", error)
    }
  }

  useEffect(() => {
    fetchWebhooks()
    fetchDeliveries()
    const interval = setInterval(() => {
      fetchWebhooks()
      fetchDeliveries()
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const createWebhook = async () => {
    if (!newWebhook.name || !newWebhook.url) return
    try {
      const res = await fetch("/api/admin/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "create", webhook: newWebhook }),
      })
      const data = await res.json()
      if (data.webhook) {
        fetchWebhooks()
        setNewWebhook({ name: "", url: "", secret: "", events: ["*"] })
        setShowCreate(false)
      }
    } catch (error) {
      console.error("Failed to create webhook:", error)
    }
  }

  const testWebhook = async (id: string) => {
    try {
      await fetch("/api/admin/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "test", webhookId: id }),
      })
      fetchDeliveries()
    } catch (error) {
      console.error("Failed to test webhook:", error)
    }
  }

  const toggleWebhook = async (id: string, enable: boolean) => {
    try {
      await fetch("/api/admin/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: enable ? "enable" : "disable", webhookId: id }),
      })
      fetchWebhooks()
    } catch (error) {
      console.error("Failed to toggle webhook:", error)
    }
  }

  const deleteWebhook = async (id: string) => {
    if (!confirm("Delete this webhook?")) return
    try {
      await fetch("/api/admin/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", webhookId: id }),
      })
      fetchWebhooks()
      if (selectedWebhook?.id === id) setSelectedWebhook(null)
    } catch (error) {
      console.error("Failed to delete webhook:", error)
    }
  }

  const triggerTestEvent = async () => {
    try {
      let payload = {}
      try {
        payload = JSON.parse(testEvent.payload)
      } catch {
        payload = { raw: testEvent.payload }
      }
      await fetch("/api/admin/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "trigger", event: { type: testEvent.type, payload } }),
      })
      fetchDeliveries()
      setShowTestEvent(false)
    } catch (error) {
      console.error("Failed to trigger event:", error)
    }
  }

  const retryDelivery = async (deliveryId: string) => {
    try {
      await fetch("/api/admin/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "retry", deliveryId }),
      })
      fetchDeliveries()
    } catch (error) {
      console.error("Failed to retry delivery:", error)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "success": return "bg-green-400/20 text-green-400"
      case "failed": return "bg-red-400/20 text-red-400"
      default: return "bg-yellow-400/20 text-yellow-400"
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Webhook Engine</h1>
            <p className="text-muted-foreground">Manage webhook endpoints and event delivery</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setShowTestEvent(true)}>Trigger Event</Button>
            <Button onClick={() => setShowCreate(true)}>Add Webhook</Button>
          </div>
        </div>

        <div className="mb-8 grid gap-4 md:grid-cols-4">
          <MetricCard title="Total Webhooks" value={stats.total} subtitle="Registered endpoints" />
          <MetricCard title="Enabled" value={stats.enabled} subtitle="Active webhooks" />
          <MetricCard title="Deliveries" value={stats.deliveries} subtitle="Total attempts" />
          <MetricCard title="Success Rate" value={`${stats.successRate}%`} subtitle="Delivery success" />
        </div>

        {showTestEvent && (
          <div className="mb-6 rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">Trigger Test Event</h2>
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Event type (e.g., user.created)"
                value={testEvent.type}
                onChange={(e) => setTestEvent({ ...testEvent, type: e.target.value })}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <textarea
                placeholder="Payload (JSON)"
                value={testEvent.payload}
                onChange={(e) => setTestEvent({ ...testEvent, payload: e.target.value })}
                className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-sm text-foreground"
                rows={4}
              />
              <div className="flex gap-2">
                <Button onClick={triggerTestEvent}>Trigger</Button>
                <Button variant="outline" onClick={() => setShowTestEvent(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        {showCreate && (
          <div className="mb-6 rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">New Webhook</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <input
                type="text"
                placeholder="Webhook name"
                value={newWebhook.name}
                onChange={(e) => setNewWebhook({ ...newWebhook, name: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <input
                type="text"
                placeholder="URL"
                value={newWebhook.url}
                onChange={(e) => setNewWebhook({ ...newWebhook, url: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <input
                type="text"
                placeholder="Secret (optional)"
                value={newWebhook.secret}
                onChange={(e) => setNewWebhook({ ...newWebhook, secret: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <input
                type="text"
                placeholder="Events (comma-separated, or * for all)"
                value={newWebhook.events.join(", ")}
                onChange={(e) => setNewWebhook({ ...newWebhook, events: e.target.value.split(",").map((s) => s.trim()) })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <div className="flex gap-2 md:col-span-2">
                <Button onClick={createWebhook}>Create</Button>
                <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h2 className="mb-4 text-lg font-semibold text-foreground">Webhooks ({webhooks.length})</h2>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : webhooks.length === 0 ? (
              <p className="text-muted-foreground">No webhooks configured</p>
            ) : (
              <div className="space-y-3">
                {webhooks.map((webhook) => (
                  <div
                    key={webhook.id}
                    onClick={() => setSelectedWebhook(webhook)}
                    className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                      selectedWebhook?.id === webhook.id
                        ? "border-primary bg-primary/10"
                        : "border-border bg-card hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-foreground">{webhook.name}</h3>
                        <p className="text-sm text-muted-foreground">{webhook.url}</p>
                      </div>
                      <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                        webhook.enabled ? "bg-green-400/20 text-green-400" : "bg-muted text-muted-foreground"
                      }`}>
                        {webhook.enabled ? "Active" : "Paused"}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Events: {webhook.events.join(", ")}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button size="sm" onClick={(e) => { e.stopPropagation(); testWebhook(webhook.id) }}>
                        Test
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={(e) => { e.stopPropagation(); toggleWebhook(webhook.id, !webhook.enabled) }}
                      >
                        {webhook.enabled ? "Disable" : "Enable"}
                      </Button>
                      <Button 
                        size="sm" 
                        variant="destructive"
                        onClick={(e) => { e.stopPropagation(); deleteWebhook(webhook.id) }}
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
            <h2 className="mb-4 text-lg font-semibold text-foreground">Recent Deliveries</h2>
            <div className="rounded-lg border border-border bg-card">
              {deliveries.length === 0 ? (
                <p className="p-4 text-muted-foreground">No deliveries yet</p>
              ) : (
                <div className="max-h-[500px] divide-y divide-border overflow-y-auto">
                  {deliveries.slice(0, 30).map((delivery) => {
                    const webhook = webhooks.find((w) => w.id === delivery.webhookId)
                    return (
                      <div key={delivery.id} className="p-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="font-medium text-foreground">{webhook?.name || delivery.webhookId}</span>
                            <span className="ml-2 text-sm text-muted-foreground">{delivery.eventType}</span>
                          </div>
                          <span className={`rounded px-2 py-0.5 text-xs font-medium ${getStatusColor(delivery.status)}`}>
                            {delivery.status}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
                          <span>
                            {delivery.statusCode && `HTTP ${delivery.statusCode} • `}
                            {delivery.attempts} attempt(s)
                          </span>
                          <span>{new Date(delivery.createdAt).toLocaleString()}</span>
                        </div>
                        {delivery.status === "failed" && (
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="mt-2"
                            onClick={() => retryDelivery(delivery.id)}
                          >
                            Retry
                          </Button>
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
