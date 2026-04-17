import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import { runHealthCheck, getHealthStatus, getHealthHistory, getChecks } from "@/lib/admin/health"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: Get health status
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const view = searchParams.get("view")

  if (view === "history") {
    const limit = parseInt(searchParams.get("limit") || "20")
    return NextResponse.json(getHealthHistory(limit))
  }

  if (view === "checks") {
    return NextResponse.json(getChecks())
  }

  const status = getHealthStatus()
  return NextResponse.json(status || { overallStatus: "unknown", checks: [], summary: { total: 0 } })
}

// POST: Run health check
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const body = await request.json().catch(() => ({}))
    const checkId = body?.checkId as string | undefined
    const report = await runHealthCheck(checkId)
    return NextResponse.json(report)
  } catch {
    return NextResponse.json({ error: "Health check failed" }, { status: 500 })
  }
}
