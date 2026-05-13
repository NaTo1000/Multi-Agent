import { NextRequest, NextResponse } from "next/server"
import { schedulerEngine, type ScheduledJob } from "@/lib/admin/scheduler"
import { auditTrail } from "@/lib/admin/audit"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const action = searchParams.get("action")

  if (action === "history") {
    const jobId = searchParams.get("jobId")
    if (!jobId) {
      return NextResponse.json({ error: "jobId required" }, { status: 400 })
    }
    return NextResponse.json({ history: schedulerEngine.getJobHistory(jobId) })
  }

  if (action === "due") {
    return NextResponse.json({ jobs: schedulerEngine.getDueJobs() })
  }

  const jobs = schedulerEngine.getAllJobs()
  const stats = schedulerEngine.getStats()
  return NextResponse.json({ jobs, stats })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const { action, jobId, job } = body

  if (action === "create" && job) {
    const newJob: Omit<ScheduledJob, "id" | "createdAt" | "lastRun" | "nextRun" | "runCount"> = {
      name: job.name,
      description: job.description,
      schedule: job.schedule,
      taskType: job.taskType,
      taskConfig: job.taskConfig || {},
      enabled: job.enabled ?? true,
      retryOnFailure: job.retryOnFailure ?? true,
      maxRetries: job.maxRetries ?? 3,
    }
    const created = schedulerEngine.createJob(newJob)
    auditTrail.log("scheduler.create", "admin", { jobId: created.id, name: created.name }, "success")
    return NextResponse.json({ job: created })
  }

  if (action === "trigger" && jobId) {
    const result = await schedulerEngine.triggerJob(jobId)
    auditTrail.log("scheduler.trigger", "admin", { jobId, success: result.success }, result.success ? "success" : "failure")
    return NextResponse.json({ result })
  }

  if (action === "enable" && jobId) {
    const updated = schedulerEngine.enableJob(jobId)
    if (updated) {
      auditTrail.log("scheduler.enable", "admin", { jobId }, "success")
      return NextResponse.json({ job: updated })
    }
    return NextResponse.json({ error: "Job not found" }, { status: 404 })
  }

  if (action === "disable" && jobId) {
    const updated = schedulerEngine.disableJob(jobId)
    if (updated) {
      auditTrail.log("scheduler.disable", "admin", { jobId }, "success")
      return NextResponse.json({ job: updated })
    }
    return NextResponse.json({ error: "Job not found" }, { status: 404 })
  }

  if (action === "delete" && jobId) {
    const deleted = schedulerEngine.deleteJob(jobId)
    if (deleted) {
      auditTrail.log("scheduler.delete", "admin", { jobId }, "success")
      return NextResponse.json({ success: true })
    }
    return NextResponse.json({ error: "Job not found" }, { status: 404 })
  }

  if (action === "processDue") {
    const results = await schedulerEngine.processDueJobs()
    auditTrail.log("scheduler.processDue", "admin", { count: results.length }, "success")
    return NextResponse.json({ results })
  }

  return NextResponse.json({ error: "Invalid action" }, { status: 400 })
}
