// ─── System Metrics Collector ───

const startTime = Date.now()

interface RequestMetric {
  timestamp: number
  path: string
  method: string
  statusCode: number
  latencyMs: number
}

const requestLog: RequestMetric[] = []
const MAX_REQUEST_LOG = 5000

// ─── Counters ───

let totalRequests = 0
let totalErrors = 0
let activeConnections = 0

export function recordRequest(path: string, method: string, statusCode: number, latencyMs: number) {
  totalRequests++
  if (statusCode >= 400) totalErrors++

  requestLog.unshift({
    timestamp: Date.now(),
    path,
    method,
    statusCode,
    latencyMs,
  })

  if (requestLog.length > MAX_REQUEST_LOG) {
    requestLog.splice(MAX_REQUEST_LOG)
  }
}

export function incrementConnections() {
  activeConnections++
}

export function decrementConnections() {
  activeConnections = Math.max(0, activeConnections - 1)
}

export function getSystemMetrics() {
  const now = Date.now()
  const uptimeMs = now - startTime
  const uptimeHours = Math.floor(uptimeMs / 3600000)
  const uptimeMinutes = Math.floor((uptimeMs % 3600000) / 60000)

  // Memory usage (Node.js)
  let memoryUsage = { heapUsed: 0, heapTotal: 0, rss: 0, external: 0 }
  if (typeof process !== "undefined" && process.memoryUsage) {
    const mem = process.memoryUsage()
    memoryUsage = {
      heapUsed: Math.round(mem.heapUsed / 1024 / 1024 * 100) / 100,
      heapTotal: Math.round(mem.heapTotal / 1024 / 1024 * 100) / 100,
      rss: Math.round(mem.rss / 1024 / 1024 * 100) / 100,
      external: Math.round(mem.external / 1024 / 1024 * 100) / 100,
    }
  }

  // Request stats from last hour
  const lastHourRequests = requestLog.filter((r) => now - r.timestamp < 3600000)
  const avgLatency =
    lastHourRequests.length > 0
      ? Math.round(lastHourRequests.reduce((sum, r) => sum + r.latencyMs, 0) / lastHourRequests.length)
      : 0

  const errorRate =
    totalRequests > 0 ? Math.round((totalErrors / totalRequests) * 10000) / 100 : 0

  // Requests per minute (last 5 mins)
  const last5min = requestLog.filter((r) => now - r.timestamp < 300000)
  const rpm = Math.round(last5min.length / 5)

  return {
    uptime: {
      ms: uptimeMs,
      formatted: `${uptimeHours}h ${uptimeMinutes}m`,
    },
    memory: memoryUsage,
    requests: {
      total: totalRequests,
      lastHour: lastHourRequests.length,
      rpm,
      avgLatencyMs: avgLatency,
      errorRate,
    },
    connections: {
      active: activeConnections,
    },
    timestamp: now,
  }
}

export function getLatencyHistory(minutes: number = 60): { timestamp: number; avgMs: number }[] {
  const now = Date.now()
  const cutoff = now - minutes * 60000
  const filtered = requestLog.filter((r) => r.timestamp > cutoff)

  // Group by minute
  const buckets = new Map<number, number[]>()
  for (const r of filtered) {
    const minute = Math.floor(r.timestamp / 60000)
    if (!buckets.has(minute)) buckets.set(minute, [])
    buckets.get(minute)!.push(r.latencyMs)
  }

  return Array.from(buckets.entries())
    .map(([minute, latencies]) => ({
      timestamp: minute * 60000,
      avgMs: Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length),
    }))
    .sort((a, b) => a.timestamp - b.timestamp)
}
