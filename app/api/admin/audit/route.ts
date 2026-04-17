import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import { getAuditLog, getAuditStats } from "@/lib/admin/audit"
import type { AuditAction, AuditResult } from "@/lib/admin/audit"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: Retrieve audit log
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)

  if (searchParams.get("stats") === "true") {
    return NextResponse.json(getAuditStats())
  }

  const action = searchParams.get("action") as AuditAction | null
  const actor = searchParams.get("actor") || undefined
  const result = searchParams.get("result") as AuditResult | null
  const limit = parseInt(searchParams.get("limit") || "50")
  const offset = parseInt(searchParams.get("offset") || "0")
  const search = searchParams.get("search") || undefined

  const data = getAuditLog({
    action: action || undefined,
    actor,
    result: result || undefined,
    limit,
    offset,
    search,
  })

  return NextResponse.json(data)
}
