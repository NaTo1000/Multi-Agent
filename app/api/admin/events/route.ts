import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import { logEvent, getEvents, getEventStats, clearEvents } from "@/lib/admin/engine"
import type { EventSeverity, EventCategory } from "@/lib/admin/engine"
import { recordAudit } from "@/lib/admin/audit"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: List events with filtering
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const severity = searchParams.get("severity") as EventSeverity | null
  const category = searchParams.get("category") as EventCategory | null
  const limit = parseInt(searchParams.get("limit") || "50")
  const offset = parseInt(searchParams.get("offset") || "0")
  const search = searchParams.get("search") || undefined

  if (searchParams.get("stats") === "true") {
    return NextResponse.json(getEventStats())
  }

  const result = getEvents({
    severity: severity || undefined,
    category: category || undefined,
    limit,
    offset,
    search,
  })

  return NextResponse.json(result)
}

// POST: Create a new event
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { severity, category, message, source, metadata } = await request.json()

    if (!severity || !category || !message) {
      return NextResponse.json({ error: "severity, category, and message are required" }, { status: 400 })
    }

    const event = logEvent(severity, category, message, source || "admin", metadata)
    return NextResponse.json(event, { status: 201 })
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }
}

// DELETE: Clear all events
export async function DELETE(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const count = clearEvents()
  recordAudit("clear_events", "admin", "success", `Cleared ${count} events`)
  return NextResponse.json({ cleared: count })
}
