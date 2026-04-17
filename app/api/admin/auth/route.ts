import { NextRequest, NextResponse } from "next/server"
import { validateAdminKey, createSession, validateSession, destroySession } from "@/lib/admin/auth"
import { recordAudit } from "@/lib/admin/audit"
import { logEvent } from "@/lib/admin/engine"

// POST: Login with GPG key
export async function POST(request: NextRequest) {
  try {
    const { key } = await request.json()
    const ip = request.headers.get("x-forwarded-for") || "unknown"

    if (!key || typeof key !== "string") {
      recordAudit("login_failed", "unknown", "failure", "Missing or invalid key", ip)
      return NextResponse.json({ error: "Key is required" }, { status: 400 })
    }

    const isValid = await validateAdminKey(key)

    if (!isValid) {
      recordAudit("login_failed", "unknown", "denied", "Invalid admin key provided", ip)
      logEvent("warning", "auth", "Failed admin login attempt", "auth", { ip })
      return NextResponse.json({ error: "Invalid admin key" }, { status: 401 })
    }

    const token = await createSession(ip)
    recordAudit("login", "admin", "success", "Admin logged in successfully", ip)
    logEvent("info", "auth", "Admin login successful", "auth", { ip })

    const response = NextResponse.json({ success: true })
    response.cookies.set("admin_session", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 86400, // 24 hours
      path: "/",
    })

    return response
  } catch (error) {
    return NextResponse.json({ error: "Internal server error" }, { status: 500 })
  }
}

// GET: Check session validity
export async function GET(request: NextRequest) {
  const token = request.cookies.get("admin_session")?.value

  if (!token || !validateSession(token)) {
    return NextResponse.json({ authenticated: false }, { status: 401 })
  }

  return NextResponse.json({ authenticated: true })
}

// DELETE: Logout
export async function DELETE(request: NextRequest) {
  const token = request.cookies.get("admin_session")?.value
  const ip = request.headers.get("x-forwarded-for") || "unknown"

  if (token) {
    destroySession(token)
    recordAudit("logout", "admin", "success", "Admin logged out", ip)
  }

  const response = NextResponse.json({ success: true })
  response.cookies.delete("admin_session")
  return response
}
