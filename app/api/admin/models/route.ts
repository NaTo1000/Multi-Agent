import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import {
  getActiveModel,
  getAllModels,
  switchModel,
  updateModelParam,
  resetModelParams,
  getChangeLog,
  type ModelParams,
} from "@/lib/admin/models"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: active model + all models + change log
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const limit = parseInt(searchParams.get("limit") || "50")

  const { model, state } = getActiveModel()
  return NextResponse.json({
    activeModel: model,
    activeState: state,
    models: getAllModels(),
    changeLog: getChangeLog(limit),
  })
}

// POST: switch model | update param | reset params
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const body = await request.json()
    const actor = (request.cookies.get("admin_session")?.value ?? "admin").slice(0, 16)

    if (body.action === "switch") {
      const { modelId } = body
      if (!modelId) return NextResponse.json({ error: "modelId required" }, { status: 400 })
      const state = switchModel(modelId, actor)
      if (!state) return NextResponse.json({ error: "Model not found" }, { status: 404 })
      return NextResponse.json({ state })
    }

    if (body.action === "update_param") {
      const { paramKey, value } = body
      if (!paramKey || value === undefined) {
        return NextResponse.json({ error: "paramKey and value required" }, { status: 400 })
      }
      const state = updateModelParam(paramKey as keyof ModelParams, Number(value), actor)
      if (!state) return NextResponse.json({ error: "Active model not found" }, { status: 404 })
      return NextResponse.json({ state })
    }

    if (body.action === "reset") {
      const state = resetModelParams(actor)
      if (!state) return NextResponse.json({ error: "Active model not found" }, { status: 404 })
      return NextResponse.json({ state })
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 })
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 })
  }
}
