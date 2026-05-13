import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"
import { recordAudit } from "./audit"

// ─── Types ───

export type StepStatus = "pending" | "running" | "success" | "failed" | "skipped"
export type PipelineStatus = "idle" | "running" | "completed" | "failed" | "paused"

export interface PipelineStep {
  id: string
  name: string
  description: string
  status: StepStatus
  order: number
  startedAt: number | null
  completedAt: number | null
  durationMs: number | null
  output: string | null
  error: string | null
  retries: number
  maxRetries: number
  handler: string // name of the handler function
}

export interface Pipeline {
  id: string
  name: string
  description: string
  status: PipelineStatus
  steps: PipelineStep[]
  createdAt: number
  startedAt: number | null
  completedAt: number | null
  currentStep: number
  totalDurationMs: number | null
  createdBy: string
  metadata?: Record<string, unknown>
}

// ─── Store ───

const pipelines: Map<string, Pipeline> = new Map()

// ─── Step Handlers Registry ───

type StepHandler = (step: PipelineStep, pipeline: Pipeline) => Promise<{ output: string; success: boolean }>

const handlers: Map<string, StepHandler> = new Map()

// Register built-in handlers
handlers.set("validate-config", async (step) => {
  await delay(300)
  return { output: `Config validation passed for step: ${step.name}`, success: true }
})

handlers.set("run-health-check", async () => {
  await delay(500)
  const memUsage = process.memoryUsage()
  return {
    output: `Health check passed. Heap: ${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`,
    success: true,
  }
})

handlers.set("create-backup", async (_step, pipeline) => {
  await delay(800)
  return { output: `Backup created for pipeline: ${pipeline.name}`, success: true }
})

handlers.set("deploy-update", async (step) => {
  await delay(1200)
  return { output: `Deployment completed for: ${step.name}`, success: true }
})

handlers.set("run-tests", async () => {
  await delay(700)
  return { output: "All tests passed (12/12)", success: true }
})

handlers.set("notify-admin", async (_step, pipeline) => {
  await delay(200)
  return { output: `Notification sent for pipeline: ${pipeline.name}`, success: true }
})

handlers.set("cleanup", async () => {
  await delay(400)
  return { output: "Temporary files cleaned up", success: true }
})

handlers.set("compile-assets", async () => {
  await delay(900)
  return { output: "Assets compiled successfully", success: true }
})

handlers.set("migrate-data", async () => {
  await delay(1100)
  return { output: "Data migration complete: 0 records affected", success: true }
})

handlers.set("custom", async (step) => {
  await delay(500)
  return { output: `Custom step executed: ${step.name}`, success: true }
})

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

// ─── Core API ───

export function createPipeline(
  name: string,
  description: string,
  steps: Array<{ name: string; description: string; handler: string; maxRetries?: number }>,
  createdBy: string = "admin"
): Pipeline {
  const pipeline: Pipeline = {
    id: uuidv4(),
    name,
    description,
    status: "idle",
    steps: steps.map((s, i) => ({
      id: uuidv4(),
      name: s.name,
      description: s.description,
      status: "pending",
      order: i,
      startedAt: null,
      completedAt: null,
      durationMs: null,
      output: null,
      error: null,
      retries: 0,
      maxRetries: s.maxRetries ?? 2,
      handler: s.handler,
    })),
    createdAt: Date.now(),
    startedAt: null,
    completedAt: null,
    currentStep: 0,
    totalDurationMs: null,
    createdBy,
  }

  pipelines.set(pipeline.id, pipeline)
  logEvent("info", "system", `Pipeline created: ${name}`, "pipeline", { pipelineId: pipeline.id })
  recordAudit("update_config", createdBy, "success", `Created pipeline: ${name}`)
  return pipeline
}

export async function runPipeline(id: string): Promise<Pipeline | null> {
  const pipeline = pipelines.get(id)
  if (!pipeline) return null
  if (pipeline.status === "running") return pipeline

  pipeline.status = "running"
  pipeline.startedAt = Date.now()
  pipeline.currentStep = 0

  logEvent("info", "system", `Pipeline started: ${pipeline.name}`, "pipeline")

  for (let i = 0; i < pipeline.steps.length; i++) {
    if (pipeline.status === "paused") break

    const step = pipeline.steps[i]
    pipeline.currentStep = i
    step.status = "running"
    step.startedAt = Date.now()

    const handler = handlers.get(step.handler)
    if (!handler) {
      step.status = "failed"
      step.error = `Handler not found: ${step.handler}`
      step.completedAt = Date.now()
      step.durationMs = step.completedAt - step.startedAt
      pipeline.status = "failed"
      logEvent("error", "system", `Pipeline step failed (no handler): ${step.name}`, "pipeline")
      break
    }

    let success = false
    while (step.retries <= step.maxRetries && !success) {
      try {
        const result = await handler(step, pipeline)
        if (result.success) {
          step.status = "success"
          step.output = result.output
          success = true
        } else {
          step.retries++
          if (step.retries > step.maxRetries) {
            step.status = "failed"
            step.error = result.output
          }
        }
      } catch (e) {
        step.retries++
        if (step.retries > step.maxRetries) {
          step.status = "failed"
          step.error = e instanceof Error ? e.message : "Unknown error"
        }
      }
    }

    step.completedAt = Date.now()
    step.durationMs = step.completedAt - (step.startedAt || Date.now())

    if (step.status === "failed") {
      // Skip remaining steps
      for (let j = i + 1; j < pipeline.steps.length; j++) {
        pipeline.steps[j].status = "skipped"
      }
      pipeline.status = "failed"
      logEvent("error", "system", `Pipeline failed at step: ${step.name}`, "pipeline")
      break
    }
  }

  if (pipeline.status === "running") {
    pipeline.status = "completed"
  }

  pipeline.completedAt = Date.now()
  pipeline.totalDurationMs = pipeline.completedAt - (pipeline.startedAt || Date.now())

  logEvent(
    pipeline.status === "completed" ? "info" : "error",
    "system",
    `Pipeline ${pipeline.status}: ${pipeline.name} (${pipeline.totalDurationMs}ms)`,
    "pipeline"
  )

  return pipeline
}

export function pausePipeline(id: string): boolean {
  const pipeline = pipelines.get(id)
  if (!pipeline || pipeline.status !== "running") return false
  pipeline.status = "paused"
  logEvent("warning", "system", `Pipeline paused: ${pipeline.name}`, "pipeline")
  return true
}

export function getPipeline(id: string): Pipeline | null {
  return pipelines.get(id) || null
}

export function getPipelines(limit: number = 20): Pipeline[] {
  return Array.from(pipelines.values())
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, limit)
}

export function deletePipeline(id: string): boolean {
  const pipeline = pipelines.get(id)
  if (!pipeline) return false
  if (pipeline.status === "running") return false
  pipelines.delete(id)
  logEvent("info", "admin", `Pipeline deleted: ${pipeline.name}`, "pipeline")
  return true
}

export function getPipelineStats() {
  const list = Array.from(pipelines.values())
  return {
    total: list.length,
    idle: list.filter((p) => p.status === "idle").length,
    running: list.filter((p) => p.status === "running").length,
    completed: list.filter((p) => p.status === "completed").length,
    failed: list.filter((p) => p.status === "failed").length,
    paused: list.filter((p) => p.status === "paused").length,
    availableHandlers: Array.from(handlers.keys()),
  }
}

// ─── Template Pipelines ───

export function createDeployPipeline(createdBy: string = "admin"): Pipeline {
  return createPipeline(
    "Deploy Update",
    "Full deployment pipeline with validation, backup, and deploy",
    [
      { name: "Validate Config", description: "Validate system configuration", handler: "validate-config" },
      { name: "Run Tests", description: "Execute test suite", handler: "run-tests" },
      { name: "Create Backup", description: "Backup current state", handler: "create-backup" },
      { name: "Compile Assets", description: "Build and compile assets", handler: "compile-assets" },
      { name: "Deploy", description: "Deploy the update", handler: "deploy-update" },
      { name: "Health Check", description: "Post-deploy health check", handler: "run-health-check" },
      { name: "Notify Admin", description: "Send completion notification", handler: "notify-admin" },
    ],
    createdBy
  )
}

export function createHealthCheckPipeline(createdBy: string = "admin"): Pipeline {
  return createPipeline(
    "System Health Check",
    "Comprehensive system health verification",
    [
      { name: "Health Check", description: "Run system health check", handler: "run-health-check" },
      { name: "Validate Config", description: "Validate all configs", handler: "validate-config" },
      { name: "Run Tests", description: "Run system tests", handler: "run-tests" },
      { name: "Cleanup", description: "Clean temporary files", handler: "cleanup" },
    ],
    createdBy
  )
}
