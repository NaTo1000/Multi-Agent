import { v4 as uuidv4 } from "uuid"
import { recordAudit } from "./audit"
import { logEvent } from "./engine"
import vm from "vm"

// ─── Types ───

export type SnippetStatus = "beta" | "stable" | "deprecated" | "archived"
export type SnippetLanguage = "javascript" | "typescript"

export interface SnippetRunResult {
  id: string
  timestamp: number
  durationMs: number
  memoryDeltaKb: number
  output: string
  error: string | null
  success: boolean
}

export interface ErosionMetrics {
  runCount: number
  errorRate: number          // 0–1
  avgDurationMs: number
  p95DurationMs: number
  latencyTrend: number       // positive = degrading, negative = improving (ms per run)
  memoryTrend: number        // positive = leaking (KB per run)
  erosionScore: number       // 0–100, higher = more eroded
  status: "stable" | "eroding" | "critical" | "insufficient-data"
}

export interface Snippet {
  id: string
  name: string
  description: string
  language: SnippetLanguage
  code: string
  tags: string[]
  status: SnippetStatus
  createdAt: number
  createdBy: string
  updatedAt: number
  updatedBy: string
  runs: SnippetRunResult[]
  erosion: ErosionMetrics
}

// ─── Store ───

const snippets: Map<string, Snippet> = new Map()
const MAX_RUNS_STORED = 200
const EXECUTION_TIMEOUT_MS = 5000

// ─── Erosion Calculation ───

function linearSlope(values: number[]): number {
  const n = values.length
  if (n < 2) return 0
  const xMean = (n - 1) / 2
  const yMean = values.reduce((a, b) => a + b, 0) / n
  let num = 0
  let den = 0
  for (let i = 0; i < n; i++) {
    num += (i - xMean) * (values[i] - yMean)
    den += (i - xMean) ** 2
  }
  return den === 0 ? 0 : num / den
}

function computeErosion(runs: SnippetRunResult[]): ErosionMetrics {
  if (runs.length === 0) {
    return {
      runCount: 0,
      errorRate: 0,
      avgDurationMs: 0,
      p95DurationMs: 0,
      latencyTrend: 0,
      memoryTrend: 0,
      erosionScore: 0,
      status: "insufficient-data",
    }
  }

  const errorRate = runs.filter((r) => !r.success).length / runs.length
  const durations = runs.map((r) => r.durationMs)
  const avgDurationMs = durations.reduce((a, b) => a + b, 0) / durations.length
  const sorted = [...durations].sort((a, b) => a - b)
  const p95DurationMs = sorted[Math.floor(sorted.length * 0.95)] ?? sorted[sorted.length - 1]

  // Use last 20 runs for trend (oldest first for slope calculation)
  const recent = [...runs].slice(-20)
  const latencyTrend = linearSlope(recent.map((r) => r.durationMs))
  const memoryTrend = linearSlope(recent.map((r) => r.memoryDeltaKb))

  // Erosion score: weighted combination
  // - error rate contributes up to 40 pts
  // - latency trend contributes up to 30 pts (normalised at 5ms/run)
  // - memory trend contributes up to 30 pts (normalised at 10 KB/run)
  const errorScore = Math.min(errorRate * 40, 40)
  const latencyScore = Math.min(Math.max(latencyTrend / 5, 0) * 30, 30)
  const memScore = Math.min(Math.max(memoryTrend / 10, 0) * 30, 30)
  const erosionScore = Math.round(errorScore + latencyScore + memScore)

  let status: ErosionMetrics["status"] = "stable"
  if (runs.length < 3) {
    status = "insufficient-data"
  } else if (erosionScore >= 60) {
    status = "critical"
  } else if (erosionScore >= 25) {
    status = "eroding"
  }

  return {
    runCount: runs.length,
    errorRate,
    avgDurationMs: Math.round(avgDurationMs),
    p95DurationMs: Math.round(p95DurationMs),
    latencyTrend: parseFloat(latencyTrend.toFixed(3)),
    memoryTrend: parseFloat(memoryTrend.toFixed(3)),
    erosionScore,
    status,
  }
}

// ─── Execution Engine ───

function captureOutput(logs: string[]): Console {
  return {
    ...console,
    log: (...args: unknown[]) => logs.push(args.map(String).join(" ")),
    warn: (...args: unknown[]) => logs.push("[warn] " + args.map(String).join(" ")),
    error: (...args: unknown[]) => logs.push("[error] " + args.map(String).join(" ")),
    info: (...args: unknown[]) => logs.push("[info] " + args.map(String).join(" ")),
  } as Console
}

async function executeSnippet(code: string): Promise<{ output: string; error: string | null; durationMs: number; memoryDeltaKb: number }> {
  const logs: string[] = []
  const memBefore = process.memoryUsage().heapUsed
  const t0 = Date.now()

  let error: string | null = null

  try {
    const sandbox: Record<string, unknown> = {
      console: captureOutput(logs),
      setTimeout: undefined,
      setInterval: undefined,
      process: undefined,
      require: undefined,
      __dirname: undefined,
      __filename: undefined,
      fetch: undefined,
    }

    vm.createContext(sandbox)

    // Intentional: this module is an admin-only snippet execution tool. Code is
    // submitted exclusively by authenticated administrators who already hold full
    // system access. The vm sandbox provides runtime isolation (output capture,
    // timeout enforcement, stripped globals) rather than a security boundary.
    // The API route enforces session authentication before reaching this path.
    const wrapped = `(async () => { ${code} })()`
    const script = new vm.Script(wrapped, { filename: "snippet.js" })
    const result = script.runInContext(sandbox, { timeout: EXECUTION_TIMEOUT_MS })

    if (result && typeof result.then === "function") {
      await Promise.race([
        result,
        new Promise((_, reject) => setTimeout(() => reject(new Error("Execution timed out")), EXECUTION_TIMEOUT_MS)),
      ])
    }
  } catch (e) {
    error = e instanceof Error ? e.message : String(e)
  }

  const durationMs = Date.now() - t0
  const memAfter = process.memoryUsage().heapUsed
  const memoryDeltaKb = Math.round((memAfter - memBefore) / 1024)
  const output = logs.join("\n")

  return { output, error, durationMs, memoryDeltaKb }
}

// ─── Default Snippets ───

function initDefaults() {
  const defaults: Array<{ name: string; description: string; code: string; tags: string[]; status: SnippetStatus }> = [
    {
      name: "Hello World",
      description: "Basic console output sanity check",
      code: `console.log("Hello from snippet runtime!");\nconsole.log("Timestamp:", Date.now());`,
      tags: ["basic", "sanity"],
      status: "stable",
    },
    {
      name: "Fibonacci Stress",
      description: "Recursive fibonacci — tests CPU under load",
      code: `function fib(n) {\n  if (n <= 1) return n;\n  return fib(n - 1) + fib(n - 2);\n}\nconsole.log("fib(30) =", fib(30));`,
      tags: ["cpu", "stress", "beta"],
      status: "beta",
    },
    {
      name: "Array Allocation",
      description: "Allocates and fills large arrays — tests memory behaviour",
      code: `const arr = new Array(100000).fill(0).map((_, i) => i * 2);\nconst sum = arr.reduce((a, b) => a + b, 0);\nconsole.log("Sum:", sum, "| Length:", arr.length);`,
      tags: ["memory", "allocation", "beta"],
      status: "beta",
    },
    {
      name: "String Builder",
      description: "Repeated string concatenation erosion test",
      code: `let s = "";\nfor (let i = 0; i < 1000; i++) s += "x";\nconsole.log("Built string length:", s.length);`,
      tags: ["string", "loop"],
      status: "beta",
    },
    {
      name: "JSON Round-trip",
      description: "Serialise and parse a large object — measures serialisation overhead",
      code: `const obj = { items: Array.from({ length: 500 }, (_, i) => ({ id: i, value: Math.random(), label: \`item-\${i}\` })) };\nconst json = JSON.stringify(obj);\nconst back = JSON.parse(json);\nconsole.log("Items:", back.items.length, "| JSON size:", json.length, "bytes");`,
      tags: ["json", "serialisation", "beta"],
      status: "beta",
    },
  ]

  for (const d of defaults) {
    const snippet: Snippet = {
      id: uuidv4(),
      name: d.name,
      description: d.description,
      language: "javascript",
      code: d.code,
      tags: d.tags,
      status: d.status,
      createdAt: Date.now(),
      createdBy: "system",
      updatedAt: Date.now(),
      updatedBy: "system",
      runs: [],
      erosion: computeErosion([]),
    }
    snippets.set(snippet.id, snippet)
  }
}

initDefaults()

// ─── Core API ───

export function getSnippet(id: string): Snippet | null {
  return snippets.get(id) ?? null
}

export function getAllSnippets(options?: { status?: SnippetStatus; search?: string }): Snippet[] {
  let list = Array.from(snippets.values())
  if (options?.status) list = list.filter((s) => s.status === options.status)
  if (options?.search) {
    const q = options.search.toLowerCase()
    list = list.filter((s) =>
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.tags.some((t) => t.toLowerCase().includes(q))
    )
  }
  return list.sort((a, b) => b.updatedAt - a.updatedAt)
}

export function createSnippet(
  name: string,
  description: string,
  code: string,
  language: SnippetLanguage = "javascript",
  tags: string[] = [],
  createdBy: string = "admin"
): Snippet {
  const snippet: Snippet = {
    id: uuidv4(),
    name,
    description,
    language,
    code,
    tags,
    status: "beta",
    createdAt: Date.now(),
    createdBy,
    updatedAt: Date.now(),
    updatedBy: createdBy,
    runs: [],
    erosion: computeErosion([]),
  }
  snippets.set(snippet.id, snippet)
  recordAudit("create_snippet", createdBy, "success", `Created snippet: ${name}`)
  logEvent("info", "admin", `Snippet created: ${name}`, "snippets")
  return snippet
}

export function updateSnippet(
  id: string,
  updates: Partial<Pick<Snippet, "name" | "description" | "code" | "language" | "tags" | "status">>,
  updatedBy: string = "admin"
): Snippet | null {
  const snippet = snippets.get(id)
  if (!snippet) return null
  Object.assign(snippet, updates, { updatedAt: Date.now(), updatedBy })
  logEvent("info", "admin", `Snippet updated: ${snippet.name}`, "snippets")
  return snippet
}

export function deleteSnippet(id: string, deletedBy: string = "admin"): boolean {
  const snippet = snippets.get(id)
  if (!snippet) return false
  snippets.delete(id)
  recordAudit("delete_snippet", deletedBy, "success", `Deleted snippet: ${snippet.name}`)
  logEvent("info", "admin", `Snippet deleted: ${snippet.name}`, "snippets")
  return true
}

export async function runSnippet(id: string, actor: string = "admin"): Promise<SnippetRunResult | null> {
  const snippet = snippets.get(id)
  if (!snippet) return null

  const { output, error, durationMs, memoryDeltaKb } = await executeSnippet(snippet.code)

  const run: SnippetRunResult = {
    id: uuidv4(),
    timestamp: Date.now(),
    durationMs,
    memoryDeltaKb,
    output,
    error,
    success: error === null,
  }

  snippet.runs.unshift(run)
  if (snippet.runs.length > MAX_RUNS_STORED) snippet.runs.splice(MAX_RUNS_STORED)
  snippet.erosion = computeErosion(snippet.runs)

  recordAudit("run_snippet", actor, run.success ? "success" : "failure", `Ran snippet: ${snippet.name} (${durationMs}ms)`)
  logEvent(
    run.success ? "info" : "warning",
    "admin",
    `Snippet run: ${snippet.name} — ${run.success ? "ok" : "error"} in ${durationMs}ms`,
    "snippets",
    { durationMs, memoryDeltaKb, error }
  )

  return run
}

export function getSnippetStats() {
  const list = Array.from(snippets.values())
  return {
    total: list.length,
    beta: list.filter((s) => s.status === "beta").length,
    stable: list.filter((s) => s.status === "stable").length,
    deprecated: list.filter((s) => s.status === "deprecated").length,
    archived: list.filter((s) => s.status === "archived").length,
    eroding: list.filter((s) => s.erosion.status === "eroding").length,
    critical: list.filter((s) => s.erosion.status === "critical").length,
    totalRuns: list.reduce((acc, s) => acc + s.runs.length, 0),
  }
}
