import { v4 as uuidv4 } from "uuid"

// ─── Types ───

export type EventSeverity = "info" | "warning" | "error" | "critical"
export type EventCategory = "system" | "auth" | "stripe" | "deployment" | "admin" | "api"

export interface TelemetryEvent {
  id: string
  timestamp: number
  severity: EventSeverity
  category: EventCategory
  message: string
  metadata?: Record<string, unknown>
  source: string
}

// ─── In-Memory Store ───

const events: TelemetryEvent[] = []
const MAX_EVENTS = 10000

// ─── Event Bus ───

type EventListener = (event: TelemetryEvent) => void
const listeners: EventListener[] = []

export function subscribe(listener: EventListener): () => void {
  listeners.push(listener)
  return () => {
    const idx = listeners.indexOf(listener)
    if (idx >= 0) listeners.splice(idx, 1)
  }
}

function emit(event: TelemetryEvent) {
  for (const listener of listeners) {
    try {
      listener(event)
    } catch {
      // Listener errors don't break the bus
    }
  }
}

// ─── Core API ───

export function logEvent(
  severity: EventSeverity,
  category: EventCategory,
  message: string,
  source: string = "system",
  metadata?: Record<string, unknown>
): TelemetryEvent {
  const event: TelemetryEvent = {
    id: uuidv4(),
    timestamp: Date.now(),
    severity,
    category,
    message,
    source,
    metadata,
  }

  events.unshift(event) // newest first

  // Cap store size
  if (events.length > MAX_EVENTS) {
    events.splice(MAX_EVENTS)
  }

  emit(event)
  return event
}

export function getEvents(options?: {
  severity?: EventSeverity
  category?: EventCategory
  limit?: number
  offset?: number
  search?: string
}): { events: TelemetryEvent[]; total: number } {
  let filtered = [...events]

  if (options?.severity) {
    filtered = filtered.filter((e) => e.severity === options.severity)
  }
  if (options?.category) {
    filtered = filtered.filter((e) => e.category === options.category)
  }
  if (options?.search) {
    const q = options.search.toLowerCase()
    filtered = filtered.filter(
      (e) =>
        e.message.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q)
    )
  }

  const total = filtered.length
  const offset = options?.offset || 0
  const limit = options?.limit || 50

  return {
    events: filtered.slice(offset, offset + limit),
    total,
  }
}

export function clearEvents(): number {
  const count = events.length
  events.length = 0
  logEvent("info", "admin", `Cleared ${count} events`, "admin")
  return count
}

export function getEventStats() {
  const now = Date.now()
  const last24h = events.filter((e) => now - e.timestamp < 86400000)
  const lastHour = events.filter((e) => now - e.timestamp < 3600000)

  return {
    total: events.length,
    last24h: last24h.length,
    lastHour: lastHour.length,
    bySeverity: {
      info: events.filter((e) => e.severity === "info").length,
      warning: events.filter((e) => e.severity === "warning").length,
      error: events.filter((e) => e.severity === "error").length,
      critical: events.filter((e) => e.severity === "critical").length,
    },
    byCategory: {
      system: events.filter((e) => e.category === "system").length,
      auth: events.filter((e) => e.category === "auth").length,
      stripe: events.filter((e) => e.category === "stripe").length,
      deployment: events.filter((e) => e.category === "deployment").length,
      admin: events.filter((e) => e.category === "admin").length,
      api: events.filter((e) => e.category === "api").length,
    },
  }
}
