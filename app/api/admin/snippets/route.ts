import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import {
  getAllSnippets,
  getSnippet,
  createSnippet,
  updateSnippet,
  deleteSnippet,
  runSnippet,
  getSnippetStats,
  type SnippetStatus,
  type SnippetLanguage,
} from "@/lib/admin/snippets"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

function actorFromRequest(request: NextRequest): string {
  return (request.cookies.get("admin_session")?.value ?? "admin").slice(0, 16)
}

// GET: list all snippets + stats, or single snippet
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const id = searchParams.get("id")

  if (id) {
    const snippet = getSnippet(id)
    if (!snippet) return NextResponse.json({ error: "Not found" }, { status: 404 })
    return NextResponse.json(snippet)
  }

  const status = searchParams.get("status") as SnippetStatus | null
  const search = searchParams.get("search") ?? undefined

  return NextResponse.json({
    snippets: getAllSnippets({ status: status ?? undefined, search }),
    stats: getSnippetStats(),
  })
}

// POST: create | update | delete | run
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const actor = actorFromRequest(request)

  try {
    const body = await request.json()

    if (body.action === "create") {
      const { name, description, code, language, tags } = body
      if (!name || !code) {
        return NextResponse.json({ error: "name and code are required" }, { status: 400 })
      }
      const snippet = createSnippet(name, description ?? "", code, language as SnippetLanguage, tags ?? [], actor)
      return NextResponse.json({ snippet })
    }

    if (body.action === "update") {
      const { id, ...updates } = body
      if (!id) return NextResponse.json({ error: "id required" }, { status: 400 })
      const snippet = updateSnippet(id, updates, actor)
      if (!snippet) return NextResponse.json({ error: "Snippet not found" }, { status: 404 })
      return NextResponse.json({ snippet })
    }

    if (body.action === "delete") {
      const { id } = body
      if (!id) return NextResponse.json({ error: "id required" }, { status: 400 })
      const success = deleteSnippet(id, actor)
      return NextResponse.json({ success })
    }

    if (body.action === "run") {
      const { id } = body
      if (!id) return NextResponse.json({ error: "id required" }, { status: 400 })
      const result = await runSnippet(id, actor)
      if (!result) return NextResponse.json({ error: "Snippet not found" }, { status: 404 })
      const snippet = getSnippet(id)
      return NextResponse.json({ result, erosion: snippet?.erosion })
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 })
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 })
  }
}
