import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import { getSystemMetrics, getLatencyHistory } from "@/lib/admin/metrics"
import { getEventStats } from "@/lib/admin/engine"
import { getErrorStats } from "@/lib/admin/errors"
import { getSnapshotStats } from "@/lib/admin/mirror"
import { getAuditStats } from "@/lib/admin/audit"
import { getActiveSessionCount } from "@/lib/admin/auth"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: Full system metrics
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)

  if (searchParams.get("latency") === "true") {
    const minutes = parseInt(searchParams.get("minutes") || "60")
    return NextResponse.json(getLatencyHistory(minutes))
  }

  const system = getSystemMetrics()
  const events = getEventStats()
  const errors = getErrorStats()
  const snapshots = getSnapshotStats()
  const audit = getAuditStats()

  return NextResponse.json({
    system,
    events,
    errors,
    snapshots,
    audit,
    activeSessions: getActiveSessionCount(),
  })
}
