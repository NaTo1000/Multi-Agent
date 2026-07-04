import { v4 as uuidv4 } from "uuid"

// ─── Types ───────────────────────────────────────────────────────────────────

export interface RatingEntry {
  id: string
  agentId: string
  agentType: string
  ratedBy: string
  task: string
  score: number       // 0–100
  comment: string
  timestamp: number
}

export interface AgentTally {
  agentId: string
  agentType: string
  averageScore: number
  lastScore: number | null
  totalRatings: number
  trend: "up" | "down" | "neutral"
  rank: number
}

// ─── In-Memory Store ─────────────────────────────────────────────────────────

const MAX_HISTORY = 500

// agentId → list of rating entries (capped)
const ratingsByAgent = new Map<string, RatingEntry[]>()

// agentId → { agentId, agentType } metadata
const agentMeta = new Map<string, { agentId: string; agentType: string }>()

// ─── Core helpers ─────────────────────────────────────────────────────────────

function getOrInitAgent(agentId: string, agentType: string): RatingEntry[] {
  if (!agentMeta.has(agentId)) {
    agentMeta.set(agentId, { agentId, agentType })
  }
  if (!ratingsByAgent.has(agentId)) {
    ratingsByAgent.set(agentId, [])
  }
  return ratingsByAgent.get(agentId)!
}

function computeAverage(entries: RatingEntry[]): number {
  if (entries.length === 0) return 0
  const sum = entries.reduce((acc, e) => acc + e.score, 0)
  return Math.round((sum / entries.length) * 100) / 100
}

function computeTrend(entries: RatingEntry[]): "up" | "down" | "neutral" {
  if (entries.length < 2) return "neutral"
  const recent = entries.slice(-5).map((e) => e.score)
  const older = entries.slice(-10, -5).map((e) => e.score)
  const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length
  const olderAvg =
    older.length > 0
      ? older.reduce((a, b) => a + b, 0) / older.length
      : recentAvg
  const delta = recentAvg - olderAvg
  if (delta > 2) return "up"
  if (delta < -2) return "down"
  return "neutral"
}

// ─── Public API ───────────────────────────────────────────────────────────────

/** Submit a single peer rating. */
export function submitRating(
  agentId: string,
  agentType: string,
  ratedBy: string,
  task: string,
  score: number,
  comment: string = ""
): RatingEntry {
  if (score < 0 || score > 100) {
    throw new RangeError(`Score must be 0–100, got ${score}`)
  }
  const entries = getOrInitAgent(agentId, agentType)
  const entry: RatingEntry = {
    id: uuidv4(),
    agentId,
    agentType,
    ratedBy,
    task,
    score: Math.round(score * 100) / 100,
    comment,
    timestamp: Date.now(),
  }
  entries.push(entry)
  // Cap history
  if (entries.length > MAX_HISTORY) {
    entries.splice(0, entries.length - MAX_HISTORY)
  }
  return entry
}

/** Ensure an agent appears in the tally (even before it has any ratings). */
export function ensureAgent(agentId: string, agentType: string): void {
  getOrInitAgent(agentId, agentType)
}

/** Return the competitive leaderboard, highest score first. */
export function getLeaderboard(): AgentTally[] {
  const board: AgentTally[] = []
  for (const [agentId, entries] of ratingsByAgent.entries()) {
    const meta = agentMeta.get(agentId)!
    board.push({
      agentId,
      agentType: meta.agentType,
      averageScore: computeAverage(entries),
      lastScore: entries.length > 0 ? entries[entries.length - 1].score : null,
      totalRatings: entries.length,
      trend: computeTrend(entries),
      rank: 0,
    })
  }
  board.sort((a, b) => b.averageScore - a.averageScore || b.totalRatings - a.totalRatings)
  board.forEach((entry, i) => {
    entry.rank = i + 1
  })
  return board
}

/** Return recent rating history for one agent. */
export function getAgentHistory(agentId: string, limit = 20): RatingEntry[] {
  const entries = ratingsByAgent.get(agentId) ?? []
  return entries.slice(-limit)
}

/** Global stats summary. */
export function getRatingsStats(): {
  totalAgents: number
  totalRatings: number
  globalAverage: number
} {
  let totalRatings = 0
  let scoreSum = 0
  for (const entries of ratingsByAgent.values()) {
    totalRatings += entries.length
    scoreSum += entries.reduce((a, e) => a + e.score, 0)
  }
  return {
    totalAgents: ratingsByAgent.size,
    totalRatings,
    globalAverage: totalRatings > 0 ? Math.round((scoreSum / totalRatings) * 100) / 100 : 0,
  }
}

// ─── Seed demo data (so the leaderboard isn't empty on first load) ────────────

const AGENT_SEEDS = [
  { id: "ai-agent-seed", type: "ai_agent" },
  { id: "frequency-agent-seed", type: "frequency_agent" },
  { id: "modulation-agent-seed", type: "modulation_agent" },
  { id: "firmware-agent-seed", type: "firmware_agent" },
  { id: "comms-agent-seed", type: "comms_agent" },
]

const TASKS = ["auto_optimise", "detect_interference", "fine_tune", "adaptive_select", "recommend_config"]

let seeded = false
export function seedDemoRatings(): void {
  if (seeded) return
  seeded = true

  for (const agent of AGENT_SEEDS) {
    const peers = AGENT_SEEDS.filter((p) => p.id !== agent.id)
    // Simulate 10 rounds of peer ratings per agent
    for (let round = 0; round < 10; round++) {
      const task = TASKS[round % TASKS.length]
      for (const peer of peers) {
        const base = 60 + (Math.abs(agent.id.charCodeAt(0) * 3 + round * 7) % 35)
        const jitter = (Math.abs(peer.id.charCodeAt(0) + round) % 11) - 5
        const score = Math.max(0, Math.min(100, base + jitter))
        submitRating(agent.id, agent.type, peer.id, task, score, `${peer.type}: round ${round + 1} evaluation`)
      }
    }
  }
}
