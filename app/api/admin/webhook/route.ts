import { NextRequest, NextResponse } from "next/server"
import { webhookEngine, type WebhookEndpoint } from "@/lib/admin/webhook"
import { auditTrail } from "@/lib/admin/audit"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const action = searchParams.get("action")

  if (action === "deliveries") {
    const webhookId = searchParams.get("webhookId")
    const limit = parseInt(searchParams.get("limit") || "50")
    return NextResponse.json({ 
      deliveries: webhookEngine.getDeliveryHistory(webhookId || undefined, limit) 
    })
  }

  if (action === "stats") {
    return NextResponse.json({ stats: webhookEngine.getStats() })
  }

  const webhooks = webhookEngine.getAllWebhooks()
  const stats = webhookEngine.getStats()
  return NextResponse.json({ webhooks, stats })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const { action, webhookId, webhook, deliveryId, event } = body

  if (action === "create" && webhook) {
    const newWebhook: Omit<WebhookEndpoint, "id" | "createdAt" | "lastTriggered"> = {
      name: webhook.name,
      url: webhook.url,
      secret: webhook.secret,
      events: webhook.events || ["*"],
      enabled: webhook.enabled ?? true,
      retryPolicy: webhook.retryPolicy || { maxRetries: 3, backoffMs: 1000 },
      headers: webhook.headers || {},
    }
    const created = webhookEngine.registerWebhook(newWebhook)
    auditTrail.log("webhook.create", "admin", { webhookId: created.id, name: created.name }, "success")
    return NextResponse.json({ webhook: created })
  }

  if (action === "update" && webhookId && webhook) {
    const updated = webhookEngine.updateWebhook(webhookId, webhook)
    if (updated) {
      auditTrail.log("webhook.update", "admin", { webhookId }, "success")
      return NextResponse.json({ webhook: updated })
    }
    return NextResponse.json({ error: "Webhook not found" }, { status: 404 })
  }

  if (action === "delete" && webhookId) {
    const deleted = webhookEngine.deleteWebhook(webhookId)
    if (deleted) {
      auditTrail.log("webhook.delete", "admin", { webhookId }, "success")
      return NextResponse.json({ success: true })
    }
    return NextResponse.json({ error: "Webhook not found" }, { status: 404 })
  }

  if (action === "enable" && webhookId) {
    const updated = webhookEngine.updateWebhook(webhookId, { enabled: true })
    if (updated) {
      auditTrail.log("webhook.enable", "admin", { webhookId }, "success")
      return NextResponse.json({ webhook: updated })
    }
    return NextResponse.json({ error: "Webhook not found" }, { status: 404 })
  }

  if (action === "disable" && webhookId) {
    const updated = webhookEngine.updateWebhook(webhookId, { enabled: false })
    if (updated) {
      auditTrail.log("webhook.disable", "admin", { webhookId }, "success")
      return NextResponse.json({ webhook: updated })
    }
    return NextResponse.json({ error: "Webhook not found" }, { status: 404 })
  }

  if (action === "trigger" && event) {
    const results = await webhookEngine.triggerEvent(event.type, event.payload || {})
    auditTrail.log("webhook.trigger", "admin", { eventType: event.type, deliveries: results.length }, "success")
    return NextResponse.json({ results })
  }

  if (action === "retry" && deliveryId) {
    const result = await webhookEngine.retryDelivery(deliveryId)
    if (result) {
      auditTrail.log("webhook.retry", "admin", { deliveryId, success: result.success }, result.success ? "success" : "failure")
      return NextResponse.json({ result })
    }
    return NextResponse.json({ error: "Delivery not found" }, { status: 404 })
  }

  if (action === "test" && webhookId) {
    const result = await webhookEngine.testWebhook(webhookId)
    if (result) {
      auditTrail.log("webhook.test", "admin", { webhookId, success: result.success }, result.success ? "success" : "failure")
      return NextResponse.json({ result })
    }
    return NextResponse.json({ error: "Webhook not found" }, { status: 404 })
  }

  return NextResponse.json({ error: "Invalid action" }, { status: 400 })
}
