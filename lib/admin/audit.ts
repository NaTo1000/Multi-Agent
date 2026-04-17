import { v4 as uuidv4 } from "uuid"

// ─── Types ───

export type AuditAction =
  | "login"
  | "logout"
  | "login_failed"
  | "view_dashboard"
  | "view_events"
  | "view_errors"
  | "view_audit"
  | "view_mirror"
  | "repair_error"
  | "dismiss_error"
  | "clear_events"
  | "clear_errors"
  | "create_snapshot"
  | "rollback_snapshot"
  | "delete_snapshot"
  | "toggle_self_repair"
  | "execute_command"
  | "update_config"

export type AuditResult = "success" | "failure" | "denied"

export interface AuditEntry {
  id: string
  timestamp: number
  action: AuditAction
  actor: string
  result: AuditResult
  detail: string
  ip?: string
  metadata?: Record<string, unknown>
}

// ─── Store ───

const auditLog: AuditEntry[] = []
const MAX_AUDIT = 10000

// ─── Core API ───

export function recordAudit(
  action: AuditAction,
  actor: string,
  result: AuditResult,
  detail: string,
  ip?: string,
  metadata?: Record<string, unknown>
): AuditEntry {
  const entry: AuditEntry = {
    id: uuidv4(),
    timestamp: Date.now(),
    action,
    actor,
    result,
    detail,
    ip,
    metadata,
  }

  auditLog.unshift(entry)

  if (auditLog.length > MAX_AUDIT) {
    auditLog.splice(MAX_AUDIT)
  }

  return entry
}

export function getAuditLog(options?: {
  action?: AuditAction
  actor?: string
  result?: AuditResult
  limit?: number
  offset?: number
  search?: string
}): { entries: AuditEntry[]; total: number } {
  let filtered = [...auditLog]

  if (options?.action) {
    filtered = filtered.filter((e) => e.action === options.action)
  }
  if (options?.actor) {
    filtered = filtered.filter((e) => e.actor === options.actor)
  }
  if (options?.result) {
    filtered = filtered.filter((e) => e.result === options.result)
  }
  if (options?.search) {
    const q = options.search.toLowerCase()
    filtered = filtered.filter(
      (e) =>
        e.detail.toLowerCase().includes(q) ||
        e.action.toLowerCase().includes(q) ||
        e.actor.toLowerCase().includes(q)
    )
  }

  const total = filtered.length
  const offset = options?.offset || 0
  const limit = options?.limit || 50

  return {
    entries: filtered.slice(offset, offset + limit),
    total,
  }
}

export function getAuditStats() {
  const now = Date.now()
  const last24h = auditLog.filter((e) => now - e.timestamp < 86400000)

  return {
    total: auditLog.length,
    last24h: last24h.length,
    byAction: auditLog.reduce(
      (acc, e) => {
        acc[e.action] = (acc[e.action] || 0) + 1
        return acc
      },
      {} as Record<string, number>
    ),
    byResult: {
      success: auditLog.filter((e) => e.result === "success").length,
      failure: auditLog.filter((e) => e.result === "failure").length,
      denied: auditLog.filter((e) => e.result === "denied").length,
    },
    failedLogins: auditLog.filter((e) => e.action === "login_failed").length,
  }
}

export function clearAuditLog(): number {
  const count = auditLog.length
  auditLog.length = 0
  recordAudit("clear_events", "system", "success", `Cleared ${count} audit entries`)
  return count
}
