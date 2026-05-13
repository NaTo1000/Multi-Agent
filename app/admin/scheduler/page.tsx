"use client"

import { useState, useEffect } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"
import { Button } from "@/components/ui/button"
import { MetricCard } from "@/components/admin/metric-card"

interface ScheduledJob {
  id: string
  name: string
  description: string
  schedule: string
  taskType: string
  taskConfig: Record<string, unknown>
  enabled: boolean
  lastRun?: string
  nextRun?: string
  runCount: number
  createdAt: string
}

interface JobHistory {
  jobId: string
  executedAt: string
  status: "success" | "failure"
  duration: number
  result?: unknown
  error?: string
}

export default function SchedulerPage() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([])
  const [stats, setStats] = useState({ total: 0, enabled: 0, disabled: 0, totalRuns: 0 })
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [selectedJob, setSelectedJob] = useState<ScheduledJob | null>(null)
  const [jobHistory, setJobHistory] = useState<JobHistory[]>([])
  const [newJob, setNewJob] = useState({
    name: "",
    description: "",
    schedule: "*/5 * * * *",
    taskType: "http",
    taskConfig: { url: "", method: "GET" },
  })

  const fetchJobs = async () => {
    try {
      const res = await fetch("/api/admin/scheduler")
      const data = await res.json()
      setJobs(data.jobs || [])
      setStats(data.stats || { total: 0, enabled: 0, disabled: 0, totalRuns: 0 })
    } catch (error) {
      console.error("Failed to fetch jobs:", error)
    } finally {
      setLoading(false)
    }
  }

  const fetchJobHistory = async (jobId: string) => {
    try {
      const res = await fetch(`/api/admin/scheduler?action=history&jobId=${jobId}`)
      const data = await res.json()
      setJobHistory(data.history || [])
    } catch (error) {
      console.error("Failed to fetch job history:", error)
    }
  }

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (selectedJob) {
      fetchJobHistory(selectedJob.id)
    }
  }, [selectedJob])

  const createJob = async () => {
    if (!newJob.name || !newJob.schedule) return
    try {
      const res = await fetch("/api/admin/scheduler", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "create", job: newJob }),
      })
      const data = await res.json()
      if (data.job) {
        fetchJobs()
        setNewJob({ name: "", description: "", schedule: "*/5 * * * *", taskType: "http", taskConfig: { url: "", method: "GET" } })
        setShowCreate(false)
      }
    } catch (error) {
      console.error("Failed to create job:", error)
    }
  }

  const triggerJob = async (id: string) => {
    try {
      await fetch("/api/admin/scheduler", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "trigger", jobId: id }),
      })
      fetchJobs()
      if (selectedJob?.id === id) fetchJobHistory(id)
    } catch (error) {
      console.error("Failed to trigger job:", error)
    }
  }

  const toggleJob = async (id: string, enable: boolean) => {
    try {
      await fetch("/api/admin/scheduler", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: enable ? "enable" : "disable", jobId: id }),
      })
      fetchJobs()
    } catch (error) {
      console.error("Failed to toggle job:", error)
    }
  }

  const deleteJob = async (id: string) => {
    if (!confirm("Delete this scheduled job?")) return
    try {
      await fetch("/api/admin/scheduler", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", jobId: id }),
      })
      fetchJobs()
      if (selectedJob?.id === id) setSelectedJob(null)
    } catch (error) {
      console.error("Failed to delete job:", error)
    }
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 p-8">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Scheduler Engine</h1>
            <p className="text-muted-foreground">Manage scheduled jobs and cron tasks</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={fetchJobs}>Refresh</Button>
            <Button onClick={() => setShowCreate(true)}>Create Job</Button>
          </div>
        </div>

        <div className="mb-8 grid gap-4 md:grid-cols-4">
          <MetricCard title="Total Jobs" value={stats.total} subtitle="Scheduled tasks" />
          <MetricCard title="Enabled" value={stats.enabled} subtitle="Active jobs" />
          <MetricCard title="Disabled" value={stats.disabled} subtitle="Paused jobs" />
          <MetricCard title="Total Runs" value={stats.totalRuns} subtitle="All time executions" />
        </div>

        {showCreate && (
          <div className="mb-6 rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-foreground">New Scheduled Job</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <input
                type="text"
                placeholder="Job name"
                value={newJob.name}
                onChange={(e) => setNewJob({ ...newJob, name: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <input
                type="text"
                placeholder="Cron schedule (e.g., */5 * * * *)"
                value={newJob.schedule}
                onChange={(e) => setNewJob({ ...newJob, schedule: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <select
                value={newJob.taskType}
                onChange={(e) => setNewJob({ ...newJob, taskType: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              >
                <option value="http">HTTP Request</option>
                <option value="cleanup">Cleanup</option>
                <option value="report">Generate Report</option>
                <option value="backup">Backup</option>
                <option value="custom">Custom</option>
              </select>
              <input
                type="text"
                placeholder="Target URL (for HTTP jobs)"
                value={newJob.taskConfig.url as string}
                onChange={(e) => setNewJob({ ...newJob, taskConfig: { ...newJob.taskConfig, url: e.target.value } })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground"
              />
              <textarea
                placeholder="Description"
                value={newJob.description}
                onChange={(e) => setNewJob({ ...newJob, description: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-2 text-foreground md:col-span-2"
                rows={2}
              />
              <div className="flex gap-2 md:col-span-2">
                <Button onClick={createJob}>Create</Button>
                <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h2 className="mb-4 text-lg font-semibold text-foreground">Scheduled Jobs ({jobs.length})</h2>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : jobs.length === 0 ? (
              <p className="text-muted-foreground">No scheduled jobs</p>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => (
                  <div
                    key={job.id}
                    onClick={() => setSelectedJob(job)}
                    className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                      selectedJob?.id === job.id
                        ? "border-primary bg-primary/10"
                        : "border-border bg-card hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-medium text-foreground">{job.name}</h3>
                        <p className="text-sm text-muted-foreground">{job.description}</p>
                      </div>
                      <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                        job.enabled ? "bg-green-400/20 text-green-400" : "bg-muted text-muted-foreground"
                      }`}>
                        {job.enabled ? "Active" : "Paused"}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span className="font-mono">{job.schedule}</span>
                      <span>{job.taskType}</span>
                      <span>{job.runCount} runs</span>
                      {job.nextRun && <span>Next: {new Date(job.nextRun).toLocaleString()}</span>}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <Button size="sm" onClick={(e) => { e.stopPropagation(); triggerJob(job.id) }}>
                        Run Now
                      </Button>
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={(e) => { e.stopPropagation(); toggleJob(job.id, !job.enabled) }}
                      >
                        {job.enabled ? "Pause" : "Enable"}
                      </Button>
                      <Button 
                        size="sm" 
                        variant="destructive"
                        onClick={(e) => { e.stopPropagation(); deleteJob(job.id) }}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h2 className="mb-4 text-lg font-semibold text-foreground">
              {selectedJob ? `History: ${selectedJob.name}` : "Job History"}
            </h2>
            {selectedJob ? (
              <div className="rounded-lg border border-border bg-card">
                {jobHistory.length === 0 ? (
                  <p className="p-4 text-muted-foreground">No execution history</p>
                ) : (
                  <div className="max-h-96 divide-y divide-border overflow-y-auto">
                    {jobHistory.map((entry, i) => (
                      <div key={i} className="p-3">
                        <div className="flex items-center justify-between">
                          <span className={`rounded px-2 py-0.5 text-xs font-medium ${
                            entry.status === "success" 
                              ? "bg-green-400/20 text-green-400" 
                              : "bg-red-400/20 text-red-400"
                          }`}>
                            {entry.status}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {new Date(entry.executedAt).toLocaleString()}
                          </span>
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          Duration: {entry.duration}ms
                        </div>
                        {entry.error && (
                          <p className="mt-1 text-xs text-red-400">{entry.error}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">Select a job to view history</p>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
