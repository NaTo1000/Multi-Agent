import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"
import { recordAudit } from "./audit"

// ─── Types ───

export type ConfigValueType = "string" | "number" | "boolean" | "json"

export interface ConfigEntry {
  id: string
  key: string
  value: string | number | boolean | Record<string, unknown>
  type: ConfigValueType
  description: string
  category: string
  isSecret: boolean
  isLocked: boolean
  updatedAt: number
  updatedBy: string
  history: ConfigChange[]
}

export interface ConfigChange {
  timestamp: number
  oldValue: unknown
  newValue: unknown
  changedBy: string
}

// ─── Store ───

const configs: Map<string, ConfigEntry> = new Map()

// ─── Initialize Default Configs ───

function initDefaults() {
  const defaults: Array<{
    key: string
    value: string | number | boolean | Record<string, unknown>
    type: ConfigValueType
    description: string
    category: string
    isSecret?: boolean
    isLocked?: boolean
  }> = [
    {
      key: "system.name",
      value: "Multi-Agent Admin",
      type: "string",
      description: "System display name",
      category: "system",
    },
    {
      key: "system.version",
      value: "1.0.0",
      type: "string",
      description: "Current system version",
      category: "system",
      isLocked: true,
    },
    {
      key: "system.debug",
      value: false,
      type: "boolean",
      description: "Enable debug mode",
      category: "system",
    },
    {
      key: "telemetry.maxEvents",
      value: 10000,
      type: "number",
      description: "Maximum events to store",
      category: "telemetry",
    },
    {
      key: "telemetry.retentionHours",
      value: 168,
      type: "number",
      description: "Event retention period in hours",
      category: "telemetry",
    },
    {
      key: "errors.selfRepair",
      value: true,
      type: "boolean",
      description: "Enable automatic self-repair",
      category: "errors",
    },
    {
      key: "errors.maxRetries",
      value: 3,
      type: "number",
      description: "Max self-repair retries per error",
      category: "errors",
    },
    {
      key: "auth.sessionDuration",
      value: 86400000,
      type: "number",
      description: "Admin session duration in ms (24h default)",
      category: "auth",
    },
    {
      key: "mirror.maxSnapshots",
      value: 50,
      type: "number",
      description: "Maximum snapshots to retain",
      category: "mirror",
    },
    {
      key: "mirror.autoBackup",
      value: true,
      type: "boolean",
      description: "Auto-backup before rollback",
      category: "mirror",
    },
    {
      key: "pipeline.timeout",
      value: 300000,
      type: "number",
      description: "Pipeline execution timeout in ms (5min)",
      category: "pipeline",
    },
    {
      key: "webhook.retries",
      value: 3,
      type: "number",
      description: "Webhook delivery retry count",
      category: "webhook",
    },
    {
      key: "webhook.timeout",
      value: 10000,
      type: "number",
      description: "Webhook request timeout in ms",
      category: "webhook",
    },
    {
      key: "scheduler.enabled",
      value: true,
      type: "boolean",
      description: "Enable scheduled jobs",
      category: "scheduler",
    },
    {
      key: "health.checkInterval",
      value: 60000,
      type: "number",
      description: "Health check interval in ms",
      category: "health",
    },
    {
      key: "health.thresholds",
      value: { memoryPercent: 85, errorRate: 10, latencyMs: 2000 },
      type: "json",
      description: "Health check warning thresholds",
      category: "health",
    },
  ]

  for (const d of defaults) {
    const entry: ConfigEntry = {
      id: uuidv4(),
      key: d.key,
      value: d.value,
      type: d.type,
      description: d.description,
      category: d.category,
      isSecret: d.isSecret ?? false,
      isLocked: d.isLocked ?? false,
      updatedAt: Date.now(),
      updatedBy: "system",
      history: [],
    }
    configs.set(d.key, entry)
  }
}

initDefaults()

// ─── Core API ───

export function getConfig(key: string): ConfigEntry | null {
  return configs.get(key) || null
}

export function getConfigValue<T = unknown>(key: string): T | null {
  const entry = configs.get(key)
  return entry ? (entry.value as T) : null
}

export function setConfig(
  key: string,
  value: string | number | boolean | Record<string, unknown>,
  changedBy: string = "admin"
): ConfigEntry | null {
  const entry = configs.get(key)
  if (!entry) return null
  if (entry.isLocked) {
    logEvent("warning", "admin", `Attempted to modify locked config: ${key}`, "config")
    return null
  }

  const change: ConfigChange = {
    timestamp: Date.now(),
    oldValue: entry.value,
    newValue: value,
    changedBy,
  }

  entry.history.push(change)
  entry.value = value
  entry.updatedAt = Date.now()
  entry.updatedBy = changedBy

  logEvent("info", "admin", `Config updated: ${key}`, "config", { oldValue: change.oldValue, newValue: value })
  recordAudit("update_config", changedBy, "success", `Updated config: ${key}`)

  return entry
}

export function createConfig(
  key: string,
  value: string | number | boolean | Record<string, unknown>,
  type: ConfigValueType,
  description: string,
  category: string,
  createdBy: string = "admin",
  isSecret: boolean = false
): ConfigEntry {
  const entry: ConfigEntry = {
    id: uuidv4(),
    key,
    value,
    type,
    description,
    category,
    isSecret,
    isLocked: false,
    updatedAt: Date.now(),
    updatedBy: createdBy,
    history: [],
  }

  configs.set(key, entry)
  logEvent("info", "admin", `Config created: ${key}`, "config")
  return entry
}

export function deleteConfig(key: string): boolean {
  const entry = configs.get(key)
  if (!entry || entry.isLocked) return false
  configs.delete(key)
  logEvent("info", "admin", `Config deleted: ${key}`, "config")
  return true
}

export function getAllConfigs(options?: {
  category?: string
  search?: string
}): ConfigEntry[] {
  let list = Array.from(configs.values())

  if (options?.category) {
    list = list.filter((c) => c.category === options.category)
  }
  if (options?.search) {
    const q = options.search.toLowerCase()
    list = list.filter(
      (c) =>
        c.key.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q) ||
        c.category.toLowerCase().includes(q)
    )
  }

  return list.sort((a, b) => a.key.localeCompare(b.key))
}

export function getConfigCategories(): string[] {
  const cats = new Set<string>()
  for (const entry of configs.values()) {
    cats.add(entry.category)
  }
  return Array.from(cats).sort()
}

export function getConfigStats() {
  const list = Array.from(configs.values())
  return {
    total: list.length,
    locked: list.filter((c) => c.isLocked).length,
    secrets: list.filter((c) => c.isSecret).length,
    categories: getConfigCategories(),
    recentChanges: list
      .filter((c) => c.history.length > 0)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 5)
      .map((c) => ({ key: c.key, updatedAt: c.updatedAt, updatedBy: c.updatedBy })),
  }
}
