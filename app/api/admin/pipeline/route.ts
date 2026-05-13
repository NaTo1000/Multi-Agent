import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import {
  createPipeline,
  runPipeline,
  pausePipeline,
  getPipeline,
  getPipelines,
  deletePipeline,
  getPipelineStats,
  createDeployPipeline,
  createHealthCheckPipeline,
} from "@/lib/admin/pipeline"
import { recordAudit } from "@/lib/admin/audit"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: List pipelines or get stats
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const id = searchParams.get("id")

  if (id) {
    const pipeline = getPipeline(id)
    if (!pipeline) return NextResponse.json({ error: "Not found" }, { status: 404 })
    return NextResponse.json(pipeline)
  }

  const stats = getPipelineStats()
  const pipelines = getPipelines()
  return NextResponse.json({ pipelines, stats })
}

// POST: Create or run pipeline
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const body = await request.json()
    const { action } = body

    switch (action) {
      case "create": {
        const { name, description, steps } = body
        if (!name || !steps?.length) {
          return NextResponse.json({ error: "name and steps required" }, { status: 400 })
        }
        const pipeline = createPipeline(name, description || "", steps, "admin")
        return NextResponse.json(pipeline)
      }

      case "create-deploy": {
        const pipeline = createDeployPipeline("admin")
        return NextResponse.json(pipeline)
      }

      case "create-health-check": {
        const pipeline = createHealthCheckPipeline("admin")
        return NextResponse.json(pipeline)
      }

      case "run": {
        const { id } = body
        if (!id) return NextResponse.json({ error: "id required" }, { status: 400 })
        const pipeline = await runPipeline(id)
        if (!pipeline) return NextResponse.json({ error: "Not found" }, { status: 404 })
        recordAudit("execute_command", "admin", "success", `Ran pipeline: ${pipeline.name}`)
        return NextResponse.json(pipeline)
      }

      case "pause": {
        const { id } = body
        if (!id) return NextResponse.json({ error: "id required" }, { status: 400 })
        const success = pausePipeline(id)
        return NextResponse.json({ success })
      }

      default:
        return NextResponse.json({ error: "Invalid action" }, { status: 400 })
    }
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 })
  }
}

// DELETE: Delete pipeline
export async function DELETE(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const id = searchParams.get("id")
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 })

  const success = deletePipeline(id)
  return NextResponse.json({ success })
}
