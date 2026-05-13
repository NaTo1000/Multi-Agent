import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"
import { recordAudit } from "./audit"

// ─── Types ───

export type WebhookEvent =
  | "error.created"
  | "error.resolved"
  | "error.critical"
  | "pipeline.completed"
  | "pipeline.failed"
  | "health.degraded"
  | "health.unhealthy"
  | "snapshot.created"
  | "snapshot.restored"
  | "auth.login"
  | "auth.failed"
  | "config.changed"
  | "job.failed"

export type WebhookStatus = "active" | "paused" | "failing"

export interface Webhook {
  id: string
  name: string
  url: string
  events: WebhookEvent[]
  status: WebhookStatus
  secret: string
  createdAt: number
  createdBy: string
  lastTriggered: number | null
  totalDeliveries: number
  totalFailures: number
  consecutiveFailures: number
  maxFailures: number
}

export interface WebhookDelivery {
  id: string
  webhookId: string
  webhookName: string
  event: WebhookEvent
  payload: Record<string, unknown>
  timestamp: number
  status: "pending" | "delivered" | "failed"
  statusCode: number | null
  responseTimeMs: number | null
  error: string | null
  retries: number
}

// ─── Store ───

const webhooks: Map<string, Webhook> = new Map()
const deliveries: WebhookDelivery[] = []
const MAX_DELIVERIES = 500

// ─── Core API ───

export function createWebhook(
  name: string,
  url: string,
  events: WebhookEvent[],
  createdBy: string = "admin"
): Webhook {
  const webhook: Webhook = {
    id: uuidv4(),
    name,
    url,
    events,
    status: "active",
    secret: uuidv4().replace(/-/g, ""),
    createdAt: Date.now(),
    createdBy,
    lastTriggered: null,
    totalDeliveries: 0,
    totalFailures: 0,
    consecutiveFailures: 0,
    maxFailures: 10,
  }

  webhooks.set(webhook.id, webhook)
  logEvent("info", "admin", `Webhook created: ${name} -> ${url}`, "webhook")
  recordAudit("update_config", createdBy, "success", `Created webhook: ${name}`)

  return webhook
}

export async function triggerWebhook(event: WebhookEvent, payload: Record<string, unknown>): Promise<WebhookDelivery[]> {
  const matchingWebhooks = Array.from(webhooks.values()).filter(
    (w) => w.status === "active" && w.events.includes(event)
  )

  const results: WebhookDelivery[] = []

  for (const webhook of matchingWebhooks) {
    const delivery: WebhookDelivery = {
      id: uuidv4(),
      webhookId: webhook.id,
      webhookName: webhook.name,
      event,
      payload,
      timestamp: Date.now(),
      status: "pending",
      statusCode: null,
      responseTimeMs: null,
      error: null,
      retries: 0,
    }

    try {
      const start = Date.now()
      const response = await fetch(webhook.url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Webhook-Event": event,
          "X-Webhook-Signature": webhook.secret,
          "X-Webhook-Id": webhook.id,
          "X-Delivery-Id": delivery.id,
        },
        body: JSON.stringify({
          event,
          timestamp: Date.now(),
          payload,
        }),
        signal: AbortSignal.timeout(10000),
      })

      delivery.responseTimeMs = Date.now() - start
      delivery.statusCode = response.status

      if (response.ok) {
        delivery.status = "delivered"
        webhook.consecutiveFailures = 0
      } else {
        delivery.status = "failed"
        delivery.error = `HTTP ${response.status}`
        webhook.consecutiveFailures++
        webhook.totalFailures++
      }
    } catch (e) {
      delivery.status = "failed"
      delivery.error = e instanceof Error ? e.message : "Delivery failed"
      delivery.responseTimeMs = 0
      webhook.consecutiveFailures++
      webhook.totalFailures++
    }

    webhook.totalDeliveries++
    webhook.lastTriggered = Date.now()

    if (webhook.consecutiveFailures >= webhook.maxFailures) {
      webhook.status = "failing"
      logEvent("error", "system", `Webhook disabled after ${webhook.maxFailures} failures: ${webhook.name}`, "webhook")
    }

    deliveries.unshift(delivery)
    if (deliveries.length > MAX_DELIVERIES) deliveries.splice(MAX_DELIVERIES)

    results.push(delivery)
  }

  return results
}

export function getWebhook(id: string): Webhook | null {
  return webhooks.get(id) || null
}

export function getWebhooks(): Webhook[] {
  return Array.from(webhooks.values()).sort((a, b) => b.createdAt - a.createdAt)
}

export function updateWebhook(
  id: string,
  updates: Partial<Pick<Webhook, "name" | "url" | "events" | "status">>
): Webhook | null {
  const webhook = webhooks.get(id)
  if (!webhook) return null

  if (updates.name) webhook.name = updates.name
  if (updates.url) webhook.url = updates.url
  if (updates.events) webhook.events = updates.events
  if (updates.status) {
    webhook.status = updates.status
    if (updates.status === "active") webhook.consecutiveFailures = 0
  }

  logEvent("info", "admin", `Webhook updated: ${webhook.name}`, "webhook")
  return webhook
}

export function deleteWebhook(id: string): boolean {
  const webhook = webhooks.get(id)
  if (!webhook) return false
  webhooks.delete(id)
  logEvent("info", "admin", `Webhook deleted: ${webhook.name}`, "webhook")
  return true
}

export function getDeliveries(webhookId?: string, limit: number = 50): WebhookDelivery[] {
  let list = [...deliveries]
  if (webhookId) list = list.filter((d) => d.webhookId === webhookId)
  return list.slice(0, limit)
}

export function testWebhook(id: string): Promise<WebhookDelivery[]> {
  return triggerWebhook("config.changed", {
    type: "test",
    message: "Test webhook delivery",
    webhookId: id,
  })
}

export function getWebhookStats() {
  const list = Array.from(webhooks.values())
  return {
    total: list.length,
    active: list.filter((w) => w.status === "active").length,
    paused: list.filter((w) => w.status === "paused").length,
    failing: list.filter((w) => w.status === "failing").length,
    totalDeliveries: deliveries.length,
    recentDeliveries: deliveries.slice(0, 10),
    availableEvents: [
      "error.created", "error.resolved", "error.critical",
      "pipeline.completed", "pipeline.failed",
      "health.degraded", "health.unhealthy",
      "snapshot.created", "snapshot.restored",
      "auth.login", "auth.failed",
      "config.changed", "job.failed",
    ] as WebhookEvent[],
  }
}
