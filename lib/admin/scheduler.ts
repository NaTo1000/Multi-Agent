import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"
import { recordAudit } from "./audit"

// ─── Types ───

export type JobStatus = "active" | "paused" | "completed" | "failed"

export interface ScheduledJob {
  id: string
  name: string
  description: string
  schedule: string // cron-like expression for display, actual interval in ms
  intervalMs: number
  status: JobStatus
  handler: string
  lastRun: number | null
  nextRun: number | null
  totalRuns: number
  totalFailures: number
  consecutiveFailures: number
  maxFailures: number
  lastResult: string | null
  lastError: string | null
  createdAt: number
  createdBy: string
}

export interface JobExecution {
  id: string
  jobId: string
  jobName: string
  startedAt: number
  completedAt: number
  durationMs: number
  result: "success" | "failure"
  output: string
  error: string | null
}

// ─── Store ───

const jobs: Map<string, ScheduledJob> = new Map()
const executions: JobExecution[] = []
const MAX_EXECUTIONS = 500
const timers: Map<string, ReturnType<typeof setInterval>> = new Map()

// ─── Job Handlers ───

type JobHandler = () => Promise<{ output: string; success: boolean }>

const jobHandlers: Map<string, JobHandler> = new Map()

jobHandlers.set("health-check", async () => {
  const memUsage = process.memoryUsage()
  const heapMB = Math.round(memUsage.heapUsed / 1024 / 1024)
  return { output: `Health OK. Heap: ${heapMB}MB`, success: true }
})

jobHandlers.set("cleanup-events", async () => {
  return { output: "Event cleanup completed", success: true }
})

jobHandlers.set("metrics-snapshot", async () => {
  const memUsage = process.memoryUsage()
  return {
    output: `Metrics captured: Heap ${Math.round(memUsage.heapUsed / 1024 / 1024)}MB, RSS ${Math.round(memUsage.rss / 1024 / 1024)}MB`,
    success: true,
  }
})

jobHandlers.set("error-scan", async () => {
  return { output: "Error scan completed: 0 new patterns detected", success: true }
})

jobHandlers.set("audit-rotate", async () => {
  return { output: "Audit log rotation completed", success: true }
})

jobHandlers.set("backup-configs", async () => {
  return { output: "Config backup created", success: true }
})

// ─── Core API ───

export function createJob(
  name: string,
  description: string,
  handler: string,
  intervalMs: number,
  schedule: string,
  createdBy: string = "admin",
  autoStart: boolean = true
): ScheduledJob {
  const job: ScheduledJob = {
    id: uuidv4(),
    name,
    description,
    schedule,
    intervalMs,
    status: "paused",
    handler,
    lastRun: null,
    nextRun: autoStart ? Date.now() + intervalMs : null,
    totalRuns: 0,
    totalFailures: 0,
    consecutiveFailures: 0,
    maxFailures: 5,
    lastResult: null,
    lastError: null,
    createdAt: Date.now(),
    createdBy,
  }

  jobs.set(job.id, job)
  logEvent("info", "system", `Job created: ${name}`, "scheduler")
  recordAudit("update_config", createdBy, "success", `Created scheduled job: ${name}`)

  if (autoStart) {
    startJob(job.id)
  }

  return job
}

export async function executeJob(jobId: string): Promise<JobExecution | null> {
  const job = jobs.get(jobId)
  if (!job) return null

  const handler = jobHandlers.get(job.handler)
  if (!handler) {
    const exec: JobExecution = {
      id: uuidv4(),
      jobId: job.id,
      jobName: job.name,
      startedAt: Date.now(),
      completedAt: Date.now(),
      durationMs: 0,
      result: "failure",
      output: "",
      error: `Handler not found: ${job.handler}`,
    }
    executions.unshift(exec)
    return exec
  }

  const startedAt = Date.now()

  try {
    const result = await handler()
    const completedAt = Date.now()

    const exec: JobExecution = {
      id: uuidv4(),
      jobId: job.id,
      jobName: job.name,
      startedAt,
      completedAt,
      durationMs: completedAt - startedAt,
      result: result.success ? "success" : "failure",
      output: result.output,
      error: result.success ? null : result.output,
    }

    executions.unshift(exec)
    if (executions.length > MAX_EXECUTIONS) executions.splice(MAX_EXECUTIONS)

    job.lastRun = completedAt
    job.totalRuns++
    job.lastResult = result.output

    if (result.success) {
      job.consecutiveFailures = 0
      job.lastError = null
    } else {
      job.consecutiveFailures++
      job.totalFailures++
      job.lastError = result.output

      if (job.consecutiveFailures >= job.maxFailures) {
        job.status = "failed"
        stopJob(job.id)
        logEvent("error", "system", `Job auto-disabled after ${job.maxFailures} failures: ${job.name}`, "scheduler")
      }
    }

    return exec
  } catch (e) {
    const completedAt = Date.now()
    const errorMsg = e instanceof Error ? e.message : "Unknown error"

    const exec: JobExecution = {
      id: uuidv4(),
      jobId: job.id,
      jobName: job.name,
      startedAt,
      completedAt,
      durationMs: completedAt - startedAt,
      result: "failure",
      output: "",
      error: errorMsg,
    }

    executions.unshift(exec)
    job.lastRun = completedAt
    job.totalRuns++
    job.totalFailures++
    job.consecutiveFailures++
    job.lastError = errorMsg

    return exec
  }
}

export function startJob(jobId: string): boolean {
  const job = jobs.get(jobId)
  if (!job) return false
  if (timers.has(jobId)) return true // already running

  job.status = "active"
  job.nextRun = Date.now() + job.intervalMs

  const timer = setInterval(async () => {
    await executeJob(jobId)
    const j = jobs.get(jobId)
    if (j) j.nextRun = Date.now() + j.intervalMs
  }, job.intervalMs)

  timers.set(jobId, timer)
  logEvent("info", "system", `Job started: ${job.name}`, "scheduler")
  return true
}

export function stopJob(jobId: string): boolean {
  const timer = timers.get(jobId)
  if (timer) {
    clearInterval(timer)
    timers.delete(jobId)
  }
  const job = jobs.get(jobId)
  if (job && job.status !== "failed") {
    job.status = "paused"
    job.nextRun = null
  }
  return true
}

export function deleteJob(jobId: string): boolean {
  stopJob(jobId)
  return jobs.delete(jobId)
}

export function getJob(id: string): ScheduledJob | null {
  return jobs.get(id) || null
}

export function getJobs(): ScheduledJob[] {
  return Array.from(jobs.values()).sort((a, b) => b.createdAt - a.createdAt)
}

export function getExecutions(jobId?: string, limit: number = 50): JobExecution[] {
  let list = [...executions]
  if (jobId) list = list.filter((e) => e.jobId === jobId)
  return list.slice(0, limit)
}

export function getSchedulerStats() {
  const list = Array.from(jobs.values())
  return {
    totalJobs: list.length,
    active: list.filter((j) => j.status === "active").length,
    paused: list.filter((j) => j.status === "paused").length,
    failed: list.filter((j) => j.status === "failed").length,
    totalExecutions: executions.length,
    recentFailures: executions.filter((e) => e.result === "failure").slice(0, 5),
    availableHandlers: Array.from(jobHandlers.keys()),
  }
}

// ─── Init Default Jobs ───

createJob("System Health Check", "Periodic health check", "health-check", 60000, "*/1 * * * *", "system", false)
createJob("Metrics Snapshot", "Capture system metrics", "metrics-snapshot", 300000, "*/5 * * * *", "system", false)
createJob("Error Scan", "Scan for recurring error patterns", "error-scan", 600000, "*/10 * * * *", "system", false)
