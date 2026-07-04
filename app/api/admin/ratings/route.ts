import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import {
  getLeaderboard,
  getRatingsStats,
  getAgentHistory,
  submitRating,
  ensureAgent,
  seedDemoRatings,
} from "@/lib/admin/ratings"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

// GET: leaderboard + stats, or ?agentId=<id> for history
export async function GET(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  // Ensure demo data exists so the board is never empty on first load
  seedDemoRatings()

  const { searchParams } = new URL(request.url)
  const agentId = searchParams.get("agentId")

  if (agentId) {
    const limit = parseInt(searchParams.get("limit") ?? "20")
    return NextResponse.json({ history: getAgentHistory(agentId, limit) })
  }

  return NextResponse.json({
    leaderboard: getLeaderboard(),
    stats: getRatingsStats(),
  })
}

// POST: submit a rating  { agentId, agentType, ratedBy, task, score, comment? }
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  const body = await request.json()
  const { agentId, agentType, ratedBy, task, score, comment } = body

  if (!agentId || !agentType || !ratedBy || !task || typeof score !== "number") {
    return NextResponse.json({ error: "Missing required fields" }, { status: 400 })
  }

  if (score < 0 || score > 100) {
    return NextResponse.json({ error: "Score must be 0–100" }, { status: 400 })
  }

  ensureAgent(agentId, agentType)
  const entry = submitRating(agentId, agentType, ratedBy, task, score, comment ?? "")

  return NextResponse.json({ entry, leaderboard: getLeaderboard() })
}
