"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { AdminSidebar } from "@/components/admin/sidebar"

interface TerminalLine {
  type: "input" | "output" | "error" | "system"
  text: string
  timestamp: number
}

export default function TerminalPage() {
  const [lines, setLines] = useState<TerminalLine[]>([
    { type: "system", text: "Multi-Agent Admin Terminal v1.0.0", timestamp: Date.now() },
    { type: "system", text: "Type 'help' for available commands.", timestamp: Date.now() },
    { type: "system", text: "", timestamp: Date.now() },
  ])
  const [input, setInput] = useState("")
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [executing, setExecuting] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [lines])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  async function executeCommand(command: string) {
    if (!command.trim()) return

    const trimmed = command.trim()

    // Add to history
    setHistory((prev) => [trimmed, ...prev.slice(0, 49)])
    setHistoryIndex(-1)

    // Add input line
    setLines((prev) => [...prev, { type: "input", text: `$ ${trimmed}`, timestamp: Date.now() }])

    // Handle local clear command
    if (trimmed === "clear") {
      setLines([
        { type: "system", text: "Terminal cleared.", timestamp: Date.now() },
        { type: "system", text: "", timestamp: Date.now() },
      ])
      setInput("")
      return
    }

    setExecuting(true)

    try {
      const res = await fetch("/api/admin/terminal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: trimmed }),
      })

      if (res.status === 401) {
        router.push("/admin/login")
        return
      }

      const data = await res.json()

      if (data.output) {
        const newLines: TerminalLine[] = data.output
          .filter((line: string) => line !== "__CLEAR__")
          .map((line: string) => ({
            type: data.status === "error" ? ("error" as const) : ("output" as const),
            text: line,
            timestamp: Date.now(),
          }))

        setLines((prev) => [...prev, ...newLines, { type: "system", text: "", timestamp: Date.now() }])
      }
    } catch {
      setLines((prev) => [
        ...prev,
        { type: "error", text: "Failed to execute command", timestamp: Date.now() },
      ])
    } finally {
      setExecuting(false)
      setInput("")
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !executing) {
      executeCommand(input)
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      if (historyIndex < history.length - 1) {
        const newIndex = historyIndex + 1
        setHistoryIndex(newIndex)
        setInput(history[newIndex])
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault()
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1
        setHistoryIndex(newIndex)
        setInput(history[newIndex])
      } else {
        setHistoryIndex(-1)
        setInput("")
      }
    }
  }

  const lineColors: Record<string, string> = {
    input: "text-primary",
    output: "text-foreground",
    error: "text-red-400",
    system: "text-muted-foreground",
  }

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex flex-1 flex-col overflow-hidden p-6">
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-foreground">Admin Terminal</h1>
          <p className="text-sm text-muted-foreground">Execute system commands and manage your infrastructure</p>
        </div>

        <div
          className="flex flex-1 flex-col rounded-xl border border-border bg-card font-mono"
          onClick={() => inputRef.current?.focus()}
        >
          <div className="flex items-center gap-2 border-b border-border px-4 py-2">
            <div className="h-3 w-3 rounded-full bg-red-500/60" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
            <div className="h-3 w-3 rounded-full bg-emerald-500/60" />
            <span className="ml-2 text-xs text-muted-foreground">admin@multi-agent</span>
          </div>

          <div className="flex-1 overflow-auto p-4">
            {lines.map((line, i) => (
              <div key={i} className={`text-sm leading-relaxed ${lineColors[line.type]}`}>
                {line.text || "\u00A0"}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="flex items-center border-t border-border px-4 py-3">
            <span className="mr-2 text-sm text-primary">$</span>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="flex-1 bg-transparent text-sm text-foreground placeholder-muted-foreground focus:outline-none"
              placeholder={executing ? "Executing..." : "Type a command..."}
              disabled={executing}
              autoComplete="off"
              spellCheck={false}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
