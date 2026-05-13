import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import { createSnapshot, getSnapshots, rollbackToSnapshot, deleteSnapshot, getSnapshotStats } from "@/lib/admin/mirror"
import { recordAudit } from "@/lib/admin/audit"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: List snapshots
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)

  if (searchParams.get("stats") === "true") {
    return NextResponse.json(getSnapshotStats())
  }

  const limit = parseInt(searchParams.get("limit") || "20")
  return NextResponse.json(getSnapshots(limit))
}

// POST: Create a new snapshot
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { label, description } = await request.json()

    if (!label) {
      return NextResponse.json({ error: "label is required" }, { status: 400 })
    }

    const snapshot = createSnapshot(label, description || "", "admin")
    recordAudit("create_snapshot", "admin", "success", `Created snapshot: ${label}`)
    return NextResponse.json(snapshot, { status: 201 })
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }
}

// PATCH: Rollback to snapshot
export async function PATCH(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { snapshotId } = await request.json()

    if (!snapshotId) {
      return NextResponse.json({ error: "snapshotId is required" }, { status: 400 })
    }

    const result = rollbackToSnapshot(snapshotId)
    recordAudit(
      "rollback_snapshot",
      "admin",
      result.success ? "success" : "failure",
      result.message
    )
    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }
}

// DELETE: Remove a snapshot
export async function DELETE(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const id = searchParams.get("id")

  if (!id) {
    return NextResponse.json({ error: "id query param is required" }, { status: 400 })
  }

  const deleted = deleteSnapshot(id)
  recordAudit("delete_snapshot", "admin", deleted ? "success" : "failure", `Delete snapshot ${id}`)
  return NextResponse.json({ deleted })
}
