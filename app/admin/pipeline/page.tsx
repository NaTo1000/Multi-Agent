"use client"

import { useState, useEffect } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"
import { Button } from "@/components/ui/button"

interface PipelineStep {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  status: "pending" | "running" | "completed" | "failed" | "skipped"
  result?: unknown
  error?: string
  startedAt?: string
  completedAt?: string
}

interface Pipeline {
  id: string
  name: string
  description: string
  steps: PipelineStep[]
  status: "idle" | "running" | "completed" | "failed" | "paused"
  createdAt: string
  lastRun?: string
  runCount: number
}

export default function PipelinePage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newPipeline, setNewPipeline] = useState({ name: "", description: "" })

  const fetchPipelines = async () => {
    try {
      const res = await fetch("/api/admin/pipeline")
      const data = await res.json()
      setPipelines(data.pipelines || [])
    } catch (error) {
      console.error("Failed to fetch pipelines:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPipelines()
    const interval = setInterval(fetchPipelines, 5000)
    return () => clearInterval(interval)
  }, [])

  const createPipeline = async () => {
    if (!newPipeline.name) return
    try {
      const res = await fetch("/api/admin/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "create", pipeline: newPipeline }),
      })
      const data = await res.json()
      if (data.pipeline) {
        setPipelines([...pipelines, data.pipeline])
        setNewPipeline({ name: "", description: "" })
        setShowCreate(false)
      }
    } catch (error) {
      console.error("Failed to create pipeline:", error)
    }
  }

  const executePipeline = async (id: string) => {
    try {
      await fetch("/api/admin/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "execute", pipelineId: id }),
      })
      fetchPipelines()
    } catch (error) {
      console.error("Failed to execute pipeline:", error)
    }
  }

  const pausePipeline = async (id: string) => {
    try {
      await fetch("/api/admin/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pause", pipelineId: id }),
      })
      fetchPipelines()
    } catch (error) {
      console.error("Failed to pause pipeline:", error)
    }
  }

  const deletePipeline = async (id: string) => {
    if (!confirm("Delete this pipeline?")) return
    try {
      await fetch("/api/admin/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", pipelineId: id }),
      })
      setPipelines(pipelines.filter((p) => p.id !== id))
      if (selectedPipeline?.id === id) setSelectedPipeline(null)
    } catch (error) {
      console.error("Failed to delete pipeline:", error)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running": return "text-blue-400"
      case "completed": return "text-green-400"
      case "failed": return "text-red-400"
      case "paused": return "text-yellow-400"
      default: return "text-muted-foreground"
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Pipeline Builder</h1>
            <p className="text-muted-foreground">Create and manage task orchestration pipelines</p>
          </div>
          <Button onClick={() => setShowCreate(true)}>Create Pipeline</Button>
        </div>

        {showCreate && (
          <div className="mb-6 rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">New Pipeline</h2>
            <div className="space-y-4">
              <input
                type="text"
                placeholder="Pipeline name"
                value={newPipeline.name}
                onChange={(e) => setNewPipeline({ ...newPipeline, name: e.target.value })}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <textarea
                placeholder="Description"
                value={newPipeline.description}
                onChange={(e) => setNewPipeline({ ...newPipeline, description: e.target.value })}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
                rows={3}
              />
              <div className="flex gap-2">
                <Button onClick={createPipeline}>Create</Button>
                <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-foreground">Pipelines ({pipelines.length})</h2>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : pipelines.length === 0 ? (
              <p className="text-muted-foreground">No pipelines created yet</p>
            ) : (
              pipelines.map((pipeline) => (
                <div
                  key={pipeline.id}
                  onClick={() => setSelectedPipeline(pipeline)}
                  className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                    selectedPipeline?.id === pipeline.id
                      ? "border-primary bg-primary/10"
                      : "border-border bg-card hover:border-primary/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-foreground">{pipeline.name}</h3>
                      <p className="text-sm text-muted-foreground">{pipeline.description}</p>
                    </div>
                    <span className={`text-sm font-medium ${getStatusColor(pipeline.status)}`}>
                      {pipeline.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{pipeline.steps.length} steps</span>
                    <span>{pipeline.runCount} runs</span>
                    {pipeline.lastRun && (
                      <span>Last: {new Date(pipeline.lastRun).toLocaleString()}</span>
                    )}
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={(e) => { e.stopPropagation(); executePipeline(pipeline.id) }}>
                      Run
                    </Button>
                    {pipeline.status === "running" && (
                      <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); pausePipeline(pipeline.id) }}>
                        Pause
                      </Button>
                    )}
                    <Button size="sm" variant="destructive" onClick={(e) => { e.stopPropagation(); deletePipeline(pipeline.id) }}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div>
            <h2 className="mb-4 text-lg font-semibold text-foreground">Pipeline Steps</h2>
            {selectedPipeline ? (
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="mb-4 font-medium text-foreground">{selectedPipeline.name}</h3>
                {selectedPipeline.steps.length === 0 ? (
                  <p className="text-muted-foreground">No steps defined</p>
                ) : (
                  <div className="space-y-3">
                    {selectedPipeline.steps.map((step, index) => (
                      <div key={step.id} className="flex items-center gap-3">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                          step.status === "completed" ? "bg-green-500/20 text-green-400" :
                          step.status === "running" ? "bg-blue-500/20 text-blue-400" :
                          step.status === "failed" ? "bg-red-500/20 text-red-400" :
                          "bg-muted text-muted-foreground"
                        }`}>
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-foreground">{step.name}</p>
                          <p className="text-xs text-muted-foreground">{step.type}</p>
                        </div>
                        <span className={`text-xs ${getStatusColor(step.status)}`}>
                          {step.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">Select a pipeline to view steps</p>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
