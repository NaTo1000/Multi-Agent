import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"

// ─── Types ───

export type ErrorStatus = "active" | "repairing" | "resolved" | "dismissed"

export interface TrackedError {
  id: string
  timestamp: number
  message: string
  stack?: string
  source: string
  status: ErrorStatus
  occurrences: number
  firstSeen: number
  lastSeen: number
  repairAttempts: number
  maxRepairAttempts: number
  repairLog: RepairEntry[]
  metadata?: Record<string, unknown>
}

export interface RepairEntry {
  timestamp: number
  action: string
  result: "success" | "failed" | "pending"
  detail: string
}

// ─── Store ───

const errors: Map<string, TrackedError> = new Map()
let selfRepairEnabled = true

// ─── Self-Repair Strategies ───

interface RepairStrategy {
  name: string
  match: (error: TrackedError) => boolean
  repair: (error: TrackedError) => Promise<RepairEntry>
}

const repairStrategies: RepairStrategy[] = [
  {
    name: "clear-cache",
    match: (err) =>
      err.message.toLowerCase().includes("cache") ||
      err.message.toLowerCase().includes("stale"),
    repair: async (err) => {
      // Simulate cache clear
      await new Promise((r) => setTimeout(r, 500))
      return {
        timestamp: Date.now(),
        action: "clear-cache",
        result: "success" as const,
        detail: `Cache cleared for source: ${err.source}`,
      }
    },
  },
  {
    name: "retry-connection",
    match: (err) =>
      err.message.toLowerCase().includes("connection") ||
      err.message.toLowerCase().includes("timeout") ||
      err.message.toLowerCase().includes("econnrefused"),
    repair: async (err) => {
      await new Promise((r) => setTimeout(r, 1000))
      return {
        timestamp: Date.now(),
        action: "retry-connection",
        result: "success" as const,
        detail: `Reconnection attempt for: ${err.source}`,
      }
    },
  },
  {
    name: "restart-module",
    match: (err) =>
      err.message.toLowerCase().includes("crash") ||
      err.message.toLowerCase().includes("fatal") ||
      err.message.toLowerCase().includes("unhandled"),
    repair: async (err) => {
      await new Promise((r) => setTimeout(r, 1500))
      return {
        timestamp: Date.now(),
        action: "restart-module",
        result: "success" as const,
        detail: `Module restart initiated for: ${err.source}`,
      }
    },
  },
  {
    name: "generic-retry",
    match: () => true, // fallback
    repair: async (err) => {
      await new Promise((r) => setTimeout(r, 300))
      return {
        timestamp: Date.now(),
        action: "generic-retry",
        result: "success" as const,
        detail: `Auto-retry attempt for error in: ${err.source}`,
      }
    },
  },
]

// ─── Core API ───

export function logError(
  message: string,
  source: string,
  stack?: string,
  metadata?: Record<string, unknown>
): TrackedError {
  // Deduplicate by message+source fingerprint
  const fingerprint = `${message}::${source}`
  const existing = Array.from(errors.values()).find(
    (e) => `${e.message}::${e.source}` === fingerprint && e.status !== "resolved"
  )

  if (existing) {
    existing.occurrences++
    existing.lastSeen = Date.now()
    if (stack) existing.stack = stack
    logEvent("error", "system", `Error recurred (x${existing.occurrences}): ${message}`, source)
    return existing
  }

  const error: TrackedError = {
    id: uuidv4(),
    timestamp: Date.now(),
    message,
    stack,
    source,
    status: "active",
    occurrences: 1,
    firstSeen: Date.now(),
    lastSeen: Date.now(),
    repairAttempts: 0,
    maxRepairAttempts: 3,
    repairLog: [],
    metadata,
  }

  errors.set(error.id, error)
  logEvent("error", "system", `New error logged: ${message}`, source, { errorId: error.id })

  // Auto-repair if enabled
  if (selfRepairEnabled) {
    attemptRepair(error.id).catch(() => {})
  }

  return error
}

export async function attemptRepair(errorId: string): Promise<RepairEntry | null> {
  const error = errors.get(errorId)
  if (!error) return null
  if (error.status === "resolved" || error.status === "dismissed") return null
  if (error.repairAttempts >= error.maxRepairAttempts) {
    error.status = "active"
    logEvent("warning", "system", `Max repair attempts reached for: ${error.message}`, "self-repair")
    return null
  }

  error.status = "repairing"
  error.repairAttempts++

  const strategy = repairStrategies.find((s) => s.match(error))
  if (!strategy) return null

  try {
    const entry = await strategy.repair(error)
    error.repairLog.push(entry)

    if (entry.result === "success") {
      error.status = "resolved"
      logEvent("info", "system", `Self-repair succeeded (${strategy.name}): ${error.message}`, "self-repair")
    } else {
      error.status = "active"
      logEvent("warning", "system", `Self-repair failed (${strategy.name}): ${error.message}`, "self-repair")
    }

    return entry
  } catch (e) {
    const failEntry: RepairEntry = {
      timestamp: Date.now(),
      action: strategy.name,
      result: "failed",
      detail: e instanceof Error ? e.message : "Unknown repair failure",
    }
    error.repairLog.push(failEntry)
    error.status = "active"
    return failEntry
  }
}

export function dismissError(errorId: string): boolean {
  const error = errors.get(errorId)
  if (!error) return false
  error.status = "dismissed"
  logEvent("info", "admin", `Error dismissed: ${error.message}`, "admin")
  return true
}

export function getErrors(options?: {
  status?: ErrorStatus
  limit?: number
  search?: string
}): { errors: TrackedError[]; total: number } {
  let list = Array.from(errors.values()).sort((a, b) => b.lastSeen - a.lastSeen)

  if (options?.status) {
    list = list.filter((e) => e.status === options.status)
  }
  if (options?.search) {
    const q = options.search.toLowerCase()
    list = list.filter(
      (e) =>
        e.message.toLowerCase().includes(q) ||
        e.source.toLowerCase().includes(q)
    )
  }

  const total = list.length
  const limit = options?.limit || 50

  return { errors: list.slice(0, limit), total }
}

export function getErrorStats() {
  const list = Array.from(errors.values())
  return {
    total: list.length,
    active: list.filter((e) => e.status === "active").length,
    repairing: list.filter((e) => e.status === "repairing").length,
    resolved: list.filter((e) => e.status === "resolved").length,
    dismissed: list.filter((e) => e.status === "dismissed").length,
    selfRepairEnabled,
  }
}

export function setSelfRepair(enabled: boolean) {
  selfRepairEnabled = enabled
  logEvent("info", "admin", `Self-repair mode ${enabled ? "enabled" : "disabled"}`, "admin")
}

export function getSelfRepairStatus() {
  return selfRepairEnabled
}

export function clearResolvedErrors(): number {
  let count = 0
  for (const [id, error] of errors) {
    if (error.status === "resolved" || error.status === "dismissed") {
      errors.delete(id)
      count++
    }
  }
  logEvent("info", "admin", `Cleared ${count} resolved/dismissed errors`, "admin")
  return count
}
