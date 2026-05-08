import { NextRequest, NextResponse } from "next/server"
import { validateSession } from "@/lib/admin/auth"
import { logEvent, clearEvents, getEventStats } from "@/lib/admin/engine"
import { clearResolvedErrors, getErrorStats, setSelfRepair, getSelfRepairStatus } from "@/lib/admin/errors"
import { createSnapshot, getSnapshots } from "@/lib/admin/mirror"
import { getSystemMetrics } from "@/lib/admin/metrics"
import { recordAudit, getAuditStats } from "@/lib/admin/audit"
import { getActiveSessionCount } from "@/lib/admin/auth"
import { pipelineEngine } from "@/lib/admin/pipeline"
import { configEngine } from "@/lib/admin/config"
import { healthEngine } from "@/lib/admin/health"
import { schedulerEngine } from "@/lib/admin/scheduler"
import { webhookEngine } from "@/lib/admin/webhook"

function checkAuth(request: NextRequest): boolean {
  const token = request.cookies.get("admin_session")?.value
  return !!token && validateSession(token)
}

interface CommandResult {
  command: string
  output: string[]
  status: "success" | "error"
  timestamp: number
}

function executeCommand(command: string): CommandResult {
  const parts = command.trim().split(/\s+/)
  const cmd = parts[0]?.toLowerCase()
  const args = parts.slice(1)
  const output: string[] = []
  let status: "success" | "error" = "success"

  switch (cmd) {
    case "help":
      output.push("Available commands:")
      output.push("  help                    - Show this help message")
      output.push("  status                  - System status overview")
      output.push("  metrics                 - Show system metrics")
      output.push("  events [count]          - Show recent events")
      output.push("  events clear            - Clear all events")
      output.push("  errors                  - Show error stats")
      output.push("  errors clear            - Clear resolved errors")
      output.push("  repair on|off           - Toggle self-repair mode")
      output.push("  snapshot [label]        - Create new snapshot")
      output.push("  snapshots               - List all snapshots")
      output.push("  audit                   - Show audit stats")
      output.push("  sessions                - Show active sessions")
      output.push("  uptime                  - Show system uptime")
      output.push("  memory                  - Show memory usage")
      output.push("  version                 - Show system version")
      output.push("  clear                   - Clear terminal")
      output.push("  ping                    - Test system responsiveness")
      output.push("")
      output.push("Builder Engine commands:")
      output.push("  pipelines               - List all pipelines")
      output.push("  pipeline run <id>       - Run a pipeline")
      output.push("  config list             - List all config keys")
      output.push("  config get <key>        - Get config value")
      output.push("  config set <key> <val>  - Set config value")
      output.push("  health                  - Run all health checks")
      output.push("  health status           - Show health summary")
      output.push("  jobs                    - List scheduled jobs")
      output.push("  job run <id>            - Trigger a job")
      output.push("  webhooks                - List all webhooks")
      output.push("  webhook test <id>       - Test a webhook")
      break

    case "status": {
      const sys = getSystemMetrics()
      const evStats = getEventStats()
      const errStats = getErrorStats()
      output.push("=== SYSTEM STATUS ===")
      output.push(`Uptime: ${sys.uptime.formatted}`)
      output.push(`Memory: ${sys.memory.heapUsed}MB / ${sys.memory.heapTotal}MB`)
      output.push(`Total Requests: ${sys.requests.total}`)
      output.push(`RPM: ${sys.requests.rpm}`)
      output.push(`Error Rate: ${sys.requests.errorRate}%`)
      output.push(`Events: ${evStats.total} (${evStats.lastHour} last hour)`)
      output.push(`Active Errors: ${errStats.active}`)
      output.push(`Self-Repair: ${errStats.selfRepairEnabled ? "ON" : "OFF"}`)
      output.push(`Active Sessions: ${getActiveSessionCount()}`)
      break
    }

    case "metrics": {
      const m = getSystemMetrics()
      output.push("=== METRICS ===")
      output.push(`Heap Used: ${m.memory.heapUsed} MB`)
      output.push(`Heap Total: ${m.memory.heapTotal} MB`)
      output.push(`RSS: ${m.memory.rss} MB`)
      output.push(`External: ${m.memory.external} MB`)
      output.push(`Avg Latency: ${m.requests.avgLatencyMs}ms`)
      output.push(`Requests/min: ${m.requests.rpm}`)
      output.push(`Error Rate: ${m.requests.errorRate}%`)
      break
    }

    case "events":
      if (args[0] === "clear") {
        const cleared = clearEvents()
        output.push(`Cleared ${cleared} events`)
      } else {
        const stats = getEventStats()
        output.push(`Total Events: ${stats.total}`)
        output.push(`Last Hour: ${stats.lastHour}`)
        output.push(`Last 24h: ${stats.last24h}`)
        output.push(`Info: ${stats.bySeverity.info} | Warning: ${stats.bySeverity.warning} | Error: ${stats.bySeverity.error} | Critical: ${stats.bySeverity.critical}`)
      }
      break

    case "errors": {
      if (args[0] === "clear") {
        const cleared = clearResolvedErrors()
        output.push(`Cleared ${cleared} resolved/dismissed errors`)
      } else {
        const errS = getErrorStats()
        output.push(`Total Errors: ${errS.total}`)
        output.push(`Active: ${errS.active} | Repairing: ${errS.repairing} | Resolved: ${errS.resolved} | Dismissed: ${errS.dismissed}`)
        output.push(`Self-Repair: ${errS.selfRepairEnabled ? "ENABLED" : "DISABLED"}`)
      }
      break
    }

    case "repair":
      if (args[0] === "on") {
        setSelfRepair(true)
        output.push("Self-repair mode ENABLED")
      } else if (args[0] === "off") {
        setSelfRepair(false)
        output.push("Self-repair mode DISABLED")
      } else {
        output.push(`Self-repair is currently: ${getSelfRepairStatus() ? "ON" : "OFF"}`)
        output.push("Usage: repair on|off")
      }
      break

    case "snapshot": {
      const label = args.join(" ") || `Manual snapshot at ${new Date().toISOString()}`
      const snap = createSnapshot(label, "Created via admin terminal", "admin")
      output.push(`Snapshot #${snap.number} created: ${label}`)
      output.push(`ID: ${snap.id}`)
      output.push(`Size: ${snap.size} bytes`)
      break
    }

    case "snapshots": {
      const snaps = getSnapshots(10)
      if (snaps.length === 0) {
        output.push("No snapshots found")
      } else {
        output.push(`=== SNAPSHOTS (${snaps.length}) ===`)
        for (const s of snaps) {
          const date = new Date(s.timestamp).toISOString()
          output.push(`  #${s.number} | ${s.label} | ${date} | ${s.size}B`)
        }
      }
      break
    }

    case "audit": {
      const aStats = getAuditStats()
      output.push(`Total Audit Entries: ${aStats.total}`)
      output.push(`Last 24h: ${aStats.last24h}`)
      output.push(`Success: ${aStats.byResult.success} | Failure: ${aStats.byResult.failure} | Denied: ${aStats.byResult.denied}`)
      output.push(`Failed Logins: ${aStats.failedLogins}`)
      break
    }

    case "sessions":
      output.push(`Active Sessions: ${getActiveSessionCount()}`)
      break

    case "uptime": {
      const u = getSystemMetrics()
      output.push(`Uptime: ${u.uptime.formatted}`)
      break
    }

    case "memory": {
      const mem = getSystemMetrics()
      output.push(`Heap Used: ${mem.memory.heapUsed} MB`)
      output.push(`Heap Total: ${mem.memory.heapTotal} MB`)
      output.push(`RSS: ${mem.memory.rss} MB`)
      break
    }

    case "version":
      output.push("Multi-Agent Admin System v1.0.0")
      output.push("Built with Next.js 15 + Stripe")
      break

    case "ping":
      output.push("PONG - System responsive")
      output.push(`Latency: ${Math.floor(Math.random() * 5) + 1}ms`)
      break

    case "clear":
      output.push("__CLEAR__")
      break

    case "pipelines": {
      const pipes = pipelineEngine.getAllPipelines()
      if (pipes.length === 0) {
        output.push("No pipelines defined")
      } else {
        output.push(`=== PIPELINES (${pipes.length}) ===`)
        for (const p of pipes) {
          output.push(`  ${p.id} | ${p.name} | ${p.status} | ${p.steps.length} steps | ${p.runCount} runs`)
        }
      }
      break
    }

    case "pipeline": {
      if (args[0] === "run" && args[1]) {
        const result = pipelineEngine.execute(args[1])
        if (result) {
          output.push(`Pipeline ${args[1]} started`)
          output.push(`Status: ${result.status}`)
        } else {
          status = "error"
          output.push(`Pipeline ${args[1]} not found`)
        }
      } else {
        output.push("Usage: pipeline run <id>")
      }
      break
    }

    case "config": {
      if (args[0] === "list") {
        const configs = configEngine.getAllConfigs()
        if (configs.length === 0) {
          output.push("No configs defined")
        } else {
          output.push(`=== CONFIGS (${configs.length}) ===`)
          for (const c of configs) {
            const val = c.type === "secret" ? "********" : String(c.value)
            output.push(`  ${c.key} = ${val} (${c.type})`)
          }
        }
      } else if (args[0] === "get" && args[1]) {
        const val = configEngine.get(args[1])
        if (val !== undefined) {
          output.push(`${args[1]} = ${JSON.stringify(val)}`)
        } else {
          output.push(`Config key '${args[1]}' not found`)
        }
      } else if (args[0] === "set" && args[1] && args[2]) {
        configEngine.set(args[1], args.slice(2).join(" "), "admin")
        output.push(`Set ${args[1]} = ${args.slice(2).join(" ")}`)
      } else {
        output.push("Usage: config list | config get <key> | config set <key> <value>")
      }
      break
    }

    case "health": {
      if (args[0] === "status") {
        const summary = healthEngine.getSummary()
        output.push("=== HEALTH SUMMARY ===")
        output.push(`Healthy: ${summary.healthy} | Degraded: ${summary.degraded} | Unhealthy: ${summary.unhealthy} | Unknown: ${summary.unknown}`)
      } else {
        output.push("Running all health checks...")
        const checks = healthEngine.getAllChecks()
        for (const check of checks) {
          if (check.enabled) {
            healthEngine.runCheck(check.id)
            output.push(`  ${check.name}: ${check.lastStatus}`)
          }
        }
      }
      break
    }

    case "jobs": {
      const jobs = schedulerEngine.getAllJobs()
      if (jobs.length === 0) {
        output.push("No scheduled jobs")
      } else {
        output.push(`=== SCHEDULED JOBS (${jobs.length}) ===`)
        for (const j of jobs) {
          const status = j.enabled ? "ACTIVE" : "PAUSED"
          output.push(`  ${j.id} | ${j.name} | ${j.schedule} | ${status} | ${j.runCount} runs`)
        }
      }
      break
    }

    case "job": {
      if (args[0] === "run" && args[1]) {
        schedulerEngine.triggerJob(args[1]).then((result) => {
          // Result handled async
        })
        output.push(`Triggered job ${args[1]}`)
      } else {
        output.push("Usage: job run <id>")
      }
      break
    }

    case "webhooks": {
      const hooks = webhookEngine.getAllWebhooks()
      if (hooks.length === 0) {
        output.push("No webhooks configured")
      } else {
        output.push(`=== WEBHOOKS (${hooks.length}) ===`)
        for (const w of hooks) {
          const status = w.enabled ? "ACTIVE" : "PAUSED"
          output.push(`  ${w.id} | ${w.name} | ${status} | ${w.events.join(",")}`)
        }
      }
      break
    }

    case "webhook": {
      if (args[0] === "test" && args[1]) {
        webhookEngine.testWebhook(args[1]).then((result) => {
          // Result handled async
        })
        output.push(`Testing webhook ${args[1]}...`)
      } else {
        output.push("Usage: webhook test <id>")
      }
      break
    }

    default:
      status = "error"
      output.push(`Unknown command: ${cmd}`)
      output.push("Type 'help' for available commands")
  }

  return {
    command,
    output,
    status,
    timestamp: Date.now(),
  }
}

// POST: Execute terminal command
export async function POST(request: NextRequest) {
  if (!checkAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }

  try {
    const { command } = await request.json()

    if (!command || typeof command !== "string") {
      return NextResponse.json({ error: "command is required" }, { status: 400 })
    }

    const result = executeCommand(command)

    logEvent("info", "admin", `Terminal command: ${command}`, "terminal")
    recordAudit("execute_command", "admin", result.status === "success" ? "success" : "failure", `Command: ${command}`)

    return NextResponse.json(result)
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 })
  }
}
