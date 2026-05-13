import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import {
  getConfig,
  setConfig,
  createConfig,
  deleteConfig,
  getAllConfigs,
  getConfigStats,
  getConfigCategories,
} from "@/lib/admin/config"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: List configs or get single config
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const key = searchParams.get("key")
  const category = searchParams.get("category") || undefined
  const search = searchParams.get("search") || undefined

  if (key) {
    const config = getConfig(key)
    if (!config) return NextResponse.json({ error: "Not found" }, { status: 404 })
    return NextResponse.json(config)
  }

  const configs = getAllConfigs({ category, search })
  const stats = getConfigStats()
  const categories = getConfigCategories()

  return NextResponse.json({ configs, stats, categories })
}

// POST: Create new config
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { key, value, type, description, category, isSecret } = await request.json()
    if (!key || value === undefined || !type || !description || !category) {
      return NextResponse.json({ error: "key, value, type, description, category required" }, { status: 400 })
    }
    const config = createConfig(key, value, type, description, category, "admin", isSecret)
    return NextResponse.json(config)
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 })
  }
}

// PATCH: Update config value
export async function PATCH(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { key, value } = await request.json()
    if (!key || value === undefined) {
      return NextResponse.json({ error: "key and value required" }, { status: 400 })
    }
    const config = setConfig(key, value, "admin")
    if (!config) return NextResponse.json({ error: "Config not found or locked" }, { status: 404 })
    return NextResponse.json(config)
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 })
  }
}

// DELETE: Delete config
export async function DELETE(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const key = searchParams.get("key")
  if (!key) return NextResponse.json({ error: "key required" }, { status: 400 })

  const success = deleteConfig(key)
  return NextResponse.json({ success })
}
