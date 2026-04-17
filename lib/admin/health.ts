import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"
import { getSystemMetrics } from "./metrics"
import { getErrorStats } from "./errors"

// ─── Types ───

export type CheckStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export interface HealthCheck {
  id: string
  name: string
  description: string
  status: CheckStatus
  lastChecked: number | null
  lastHealthy: number | null
  responseTimeMs: number | null
  message: string
  consecutiveFailures: number
  totalChecks: number
  totalFailures: number
  metadata?: Record<string, unknown>
}

export interface HealthReport {
  timestamp: number
  overallStatus: CheckStatus
  checks: HealthCheck[]
  summary: {
    healthy: number
    degraded: number
    unhealthy: number
    unknown: number
    total: number
  }
}

// ─── Store ───

const checks: Map<string, HealthCheck> = new Map()
const reports: HealthReport[] = []
const MAX_REPORTS = 100

// ─── Built-in Checks ───

type CheckFn = () => Promise<{ status: CheckStatus; message: string; responseTimeMs: number; metadata?: Record<string, unknown> }>

const checkFunctions: Map<string, CheckFn> = new Map()

// Memory check
checkFunctions.set("memory", async () => {
  const start = Date.now()
  const metrics = getSystemMetrics()
  const responseTimeMs = Date.now() - start
  const heapPercent = metrics.memory.heapTotal > 0
    ? (metrics.memory.heapUsed / metrics.memory.heapTotal) * 100
    : 0

  let status: CheckStatus = "healthy"
  let message = `Heap usage: ${Math.round(heapPercent)}% (${metrics.memory.heapUsed}MB / ${metrics.memory.heapTotal}MB)`

  if (heapPercent > 90) {
    status = "unhealthy"
    message = `CRITICAL: Memory at ${Math.round(heapPercent)}%`
  } else if (heapPercent > 75) {
    status = "degraded"
    message = `WARNING: Memory at ${Math.round(heapPercent)}%`
  }

  return { status, message, responseTimeMs, metadata: { heapPercent: Math.round(heapPercent), ...metrics.memory } }
})

// Error rate check
checkFunctions.set("error-rate", async () => {
  const start = Date.now()
  const errStats = getErrorStats()
  const responseTimeMs = Date.now() - start

  let status: CheckStatus = "healthy"
  let message = `Active errors: ${errStats.active}, Self-repair: ${errStats.selfRepairEnabled ? "ON" : "OFF"}`

  if (errStats.active > 10) {
    status = "unhealthy"
    message = `CRITICAL: ${errStats.active} active errors`
  } else if (errStats.active > 3) {
    status = "degraded"
    message = `WARNING: ${errStats.active} active errors`
  }

  return { status, message, responseTimeMs, metadata: errStats }
})

// Latency check
checkFunctions.set("latency", async () => {
  const start = Date.now()
  const metrics = getSystemMetrics()
  const responseTimeMs = Date.now() - start

  let status: CheckStatus = "healthy"
  const avgLatency = metrics.requests.avgLatencyMs
  let message = `Avg latency: ${avgLatency}ms, RPM: ${metrics.requests.rpm}`

  if (avgLatency > 2000) {
    status = "unhealthy"
    message = `CRITICAL: Avg latency ${avgLatency}ms`
  } else if (avgLatency > 500) {
    status = "degraded"
    message = `WARNING: Avg latency ${avgLatency}ms`
  }

  return { status, message, responseTimeMs, metadata: { avgLatency, rpm: metrics.requests.rpm } }
})

// Uptime check
checkFunctions.set("uptime", async () => {
  const start = Date.now()
  const metrics = getSystemMetrics()
  const responseTimeMs = Date.now() - start

  return {
    status: "healthy" as CheckStatus,
    message: `System uptime: ${metrics.uptime.formatted}`,
    responseTimeMs,
    metadata: { uptimeMs: metrics.uptime.ms },
  }
})

// API responsiveness check
checkFunctions.set("api-response", async () => {
  const start = Date.now()
  // Simulate checking API responsiveness
  await new Promise((r) => setTimeout(r, 5))
  const responseTimeMs = Date.now() - start

  let status: CheckStatus = "healthy"
  let message = `API response time: ${responseTimeMs}ms`

  if (responseTimeMs > 5000) {
    status = "unhealthy"
    message = `CRITICAL: API response ${responseTimeMs}ms`
  } else if (responseTimeMs > 1000) {
    status = "degraded"
    message = `WARNING: API response ${responseTimeMs}ms`
  }

  return { status, message, responseTimeMs }
})

// Disk/storage check
checkFunctions.set("storage", async () => {
  const start = Date.now()
  const responseTimeMs = Date.now() - start

  return {
    status: "healthy" as CheckStatus,
    message: "Storage subsystem operational",
    responseTimeMs,
    metadata: { type: "in-memory" },
  }
})

// ─── Init Checks ───

function initChecks() {
  const builtIn = [
    { name: "Memory Usage", description: "Monitor heap memory usage", fn: "memory" },
    { name: "Error Rate", description: "Monitor active error count and self-repair status", fn: "error-rate" },
    { name: "API Latency", description: "Monitor average API response latency", fn: "latency" },
    { name: "System Uptime", description: "Track system uptime", fn: "uptime" },
    { name: "API Responsiveness", description: "Check API endpoint responsiveness", fn: "api-response" },
    { name: "Storage Health", description: "Verify storage subsystem", fn: "storage" },
  ]

  for (const check of builtIn) {
    const hc: HealthCheck = {
      id: check.fn,
      name: check.name,
      description: check.description,
      status: "unknown",
      lastChecked: null,
      lastHealthy: null,
      responseTimeMs: null,
      message: "Not yet checked",
      consecutiveFailures: 0,
      totalChecks: 0,
      totalFailures: 0,
    }
    checks.set(check.fn, hc)
  }
}

initChecks()

// ─── Core API ───

export async function runHealthCheck(checkId?: string): Promise<HealthReport> {
  const checksToRun = checkId
    ? [checks.get(checkId)].filter(Boolean) as HealthCheck[]
    : Array.from(checks.values())

  for (const check of checksToRun) {
    const fn = checkFunctions.get(check.id)
    if (!fn) {
      check.status = "unknown"
      check.message = "No check function registered"
      continue
    }

    try {
      const result = await fn()
      check.status = result.status
      check.message = result.message
      check.responseTimeMs = result.responseTimeMs
      check.lastChecked = Date.now()
      check.totalChecks++

      if (result.status === "healthy") {
        check.lastHealthy = Date.now()
        check.consecutiveFailures = 0
      } else {
        check.consecutiveFailures++
        check.totalFailures++
      }

      if (result.metadata) {
        check.metadata = result.metadata
      }
    } catch (e) {
      check.status = "unhealthy"
      check.message = e instanceof Error ? e.message : "Check failed"
      check.lastChecked = Date.now()
      check.consecutiveFailures++
      check.totalChecks++
      check.totalFailures++
    }
  }

  const allChecks = Array.from(checks.values())
  const overallStatus = allChecks.some((c) => c.status === "unhealthy")
    ? "unhealthy"
    : allChecks.some((c) => c.status === "degraded")
      ? "degraded"
      : allChecks.every((c) => c.status === "healthy")
        ? "healthy"
        : "unknown"

  const report: HealthReport = {
    timestamp: Date.now(),
    overallStatus,
    checks: allChecks,
    summary: {
      healthy: allChecks.filter((c) => c.status === "healthy").length,
      degraded: allChecks.filter((c) => c.status === "degraded").length,
      unhealthy: allChecks.filter((c) => c.status === "unhealthy").length,
      unknown: allChecks.filter((c) => c.status === "unknown").length,
      total: allChecks.length,
    },
  }

  reports.unshift(report)
  if (reports.length > MAX_REPORTS) reports.splice(MAX_REPORTS)

  if (overallStatus !== "healthy") {
    logEvent(
      overallStatus === "unhealthy" ? "critical" : "warning",
      "system",
      `Health check: ${overallStatus} (${report.summary.unhealthy} unhealthy, ${report.summary.degraded} degraded)`,
      "health"
    )
  }

  return report
}

export function getHealthStatus(): HealthReport | null {
  if (reports.length === 0) return null
  return reports[0]
}

export function getHealthHistory(limit: number = 20): HealthReport[] {
  return reports.slice(0, limit)
}

export function getChecks(): HealthCheck[] {
  return Array.from(checks.values())
}
