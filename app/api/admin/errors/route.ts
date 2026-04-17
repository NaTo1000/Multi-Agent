import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import {
  logError,
  getErrors,
  getErrorStats,
  attemptRepair,
  dismissError,
  setSelfRepair,
  getSelfRepairStatus,
  clearResolvedErrors,
} from "@/lib/admin/errors"
import type { ErrorStatus } from "@/lib/admin/errors"
import { recordAudit } from "@/lib/admin/audit"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: List errors
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)

  if (searchParams.get("stats") === "true") {
    return NextResponse.json(getErrorStats())
  }

  const status = searchParams.get("status") as ErrorStatus | null
  const limit = parseInt(searchParams.get("limit") || "50")
  const search = searchParams.get("search") || undefined

  const result = getErrors({
    status: status || undefined,
    limit,
    search,
  })

  return NextResponse.json(result)
}

// POST: Log a new error
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { message, source, stack, metadata } = await request.json()

    if (!message || !source) {
      return NextResponse.json({ error: "message and source are required" }, { status: 400 })
    }

    const error = logError(message, source, stack, metadata)
    return NextResponse.json(error, { status: 201 })
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }
}

// PATCH: Repair, dismiss, or toggle self-repair
export async function PATCH(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { action, errorId, enabled } = await request.json()

    switch (action) {
      case "repair": {
        if (!errorId) {
          return NextResponse.json({ error: "errorId required" }, { status: 400 })
        }
        const entry = await attemptRepair(errorId)
        recordAudit("repair_error", "admin", entry ? "success" : "failure", `Repair attempt on ${errorId}`)
        return NextResponse.json({ repairEntry: entry })
      }

      case "dismiss": {
        if (!errorId) {
          return NextResponse.json({ error: "errorId required" }, { status: 400 })
        }
        const dismissed = dismissError(errorId)
        recordAudit("dismiss_error", "admin", dismissed ? "success" : "failure", `Dismiss error ${errorId}`)
        return NextResponse.json({ dismissed })
      }

      case "toggle_self_repair": {
        setSelfRepair(!!enabled)
        recordAudit("toggle_self_repair", "admin", "success", `Self-repair ${enabled ? "enabled" : "disabled"}`)
        return NextResponse.json({ selfRepairEnabled: getSelfRepairStatus() })
      }

      default:
        return NextResponse.json({ error: "Invalid action" }, { status: 400 })
    }
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }
}

// DELETE: Clear resolved errors
export async function DELETE(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const count = clearResolvedErrors()
  recordAudit("clear_errors", "admin", "success", `Cleared ${count} resolved errors`)
  return NextResponse.json({ cleared: count })
}
