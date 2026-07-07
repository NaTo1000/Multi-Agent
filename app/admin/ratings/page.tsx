"use client"

import { useState, useEffect } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"
import { MetricCard } from "@/components/admin/metric-card"

interface AgentTally {
  agentId: string
  agentType: string
  averageScore: number
  lastScore: number | null
  totalRatings: number
  trend: "up" | "down" | "neutral"
  rank: number
}

interface RatingEntry {
  id: string
  agentId: string
  agentType: string
  ratedBy: string
  task: string
  score: number
  comment: string
  timestamp: number
}

interface Stats {
  totalAgents: number
  totalRatings: number
  globalAverage: number
}

const RANK_MEDALS = ["🥇", "🥈", "🥉"]

function TrendIcon({ trend }: { trend: "up" | "down" | "neutral" }) {
  if (trend === "up") {
    return (
      <svg className="text-green-400" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="18 15 12 9 6 15" />
      </svg>
    )
  }
  if (trend === "down") {
    return (
      <svg className="text-red-400" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    )
  }
  return (
    <svg className="text-muted-foreground" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 85 ? "bg-emerald-500" :
    score >= 70 ? "bg-blue-500" :
    score >= 55 ? "bg-yellow-500" : "bg-red-500"

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="w-12 text-right text-sm font-semibold tabular-nums text-foreground">
        {score.toFixed(1)}%
      </span>
    </div>
  )
}

export default function RatingsPage() {
  const [leaderboard, setLeaderboard] = useState<AgentTally[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [history, setHistory] = useState<RatingEntry[]>([])
  const [selectedAgent, setSelectedAgent] = useState<AgentTally | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchLeaderboard = async () => {
    try {
      const res = await fetch("/api/admin/ratings")
      const data = await res.json()
      setLeaderboard(data.leaderboard ?? [])
      setStats(data.stats ?? null)
    } catch (error) {
      console.error("Failed to fetch ratings:", error)
    } finally {
      setLoading(false)
    }
  }

  const fetchHistory = async (agentId: string) => {
    try {
      const res = await fetch(`/api/admin/ratings?agentId=${encodeURIComponent(agentId)}&limit=30`)
      const data = await res.json()
      setHistory(data.history ?? [])
    } catch (error) {
      console.error("Failed to fetch history:", error)
    }
  }

  useEffect(() => {
    fetchLeaderboard()
    const interval = setInterval(fetchLeaderboard, 8000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (selectedAgent) {
      fetchHistory(selectedAgent.agentId)
    }
  }, [selectedAgent])

  const topAgent = leaderboard[0]

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Agent Ratings</h1>
          <p className="text-sm text-muted-foreground">
            Peer-reviewed performance scores — agents race to stay at the top
          </p>
        </div>

        {stats && (
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <MetricCard
              title="Agents Ranked"
              value={stats.totalAgents}
              subtitle="Active competitors"
              color="blue"
            />
            <MetricCard
              title="Total Ratings Cast"
              value={stats.totalRatings}
              subtitle="Peer evaluations recorded"
              color="default"
            />
            <MetricCard
              title="Global Average"
              value={`${stats.globalAverage.toFixed(1)}%`}
              subtitle="Across all agents"
              color={stats.globalAverage >= 75 ? "green" : stats.globalAverage >= 55 ? "yellow" : "red"}
            />
          </div>
        )}

        {topAgent && (
          <div className="mb-6 rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-5">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🏆</span>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Current Leader</p>
                <p className="text-xl font-bold text-foreground">{topAgent.agentType}</p>
                <p className="text-sm text-muted-foreground font-mono">{topAgent.agentId}</p>
              </div>
              <div className="ml-auto text-right">
                <p className="text-3xl font-bold text-emerald-400">{topAgent.averageScore.toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">{topAgent.totalRatings} ratings</p>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Leaderboard */}
          <div className="lg:col-span-2">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Leaderboard
            </h2>
            {loading ? (
              <p className="text-muted-foreground">Loading…</p>
            ) : leaderboard.length === 0 ? (
              <p className="text-muted-foreground">No ratings yet — tasks will trigger peer reviews automatically.</p>
            ) : (
              <div className="space-y-2">
                {leaderboard.map((agent) => (
                  <div
                    key={agent.agentId}
                    onClick={() => setSelectedAgent(agent)}
                    className={`cursor-pointer rounded-xl border p-4 transition-colors ${
                      selectedAgent?.agentId === agent.agentId
                        ? "border-primary bg-primary/10"
                        : "border-border bg-card hover:border-primary/40"
                    }`}
                  >
                    <div className="mb-2 flex items-center gap-3">
                      <span className="text-xl w-8 shrink-0">
                        {agent.rank <= 3 ? RANK_MEDALS[agent.rank - 1] : `#${agent.rank}`}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-foreground leading-tight">{agent.agentType}</p>
                        <p className="truncate text-xs text-muted-foreground font-mono">{agent.agentId}</p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <TrendIcon trend={agent.trend} />
                        <span className="text-xs text-muted-foreground">{agent.totalRatings} ratings</span>
                      </div>
                    </div>
                    <ScoreBar score={agent.averageScore} />
                    {agent.lastScore !== null && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Last score: <span className="font-medium text-foreground">{agent.lastScore.toFixed(1)}%</span>
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* History panel */}
          <div>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              {selectedAgent ? `History — ${selectedAgent.agentType}` : "Rating History"}
            </h2>
            {!selectedAgent ? (
              <p className="text-sm text-muted-foreground">Select an agent to view its rating history.</p>
            ) : history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No history available.</p>
            ) : (
              <div className="rounded-xl border border-border bg-card divide-y divide-border max-h-[600px] overflow-y-auto">
                {history.slice().reverse().map((entry) => (
                  <div key={entry.id} className="p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-foreground">{entry.task}</span>
                      <span
                        className={`shrink-0 text-sm font-bold tabular-nums ${
                          entry.score >= 85 ? "text-emerald-400" :
                          entry.score >= 70 ? "text-blue-400" :
                          entry.score >= 55 ? "text-yellow-400" : "text-red-400"
                        }`}
                      >
                        {entry.score.toFixed(1)}%
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{entry.comment}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground/60">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
