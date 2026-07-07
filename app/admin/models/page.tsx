"use client"

import { useState, useEffect, useCallback } from "react"
import { AdminSidebar } from "@/components/admin/sidebar"

interface ModelParams {
  temperature: number
  maxTokens: number
  topP: number
  frequencyPenalty: number
  presencePenalty: number
}

interface ParamLimits {
  min: number
  max: number
  step: number
}

interface ModelDefinition {
  id: string
  name: string
  provider: string
  color: string
  defaultParams: ModelParams
  paramLimits: Record<keyof ModelParams, ParamLimits>
}

interface ModelState {
  modelId: string
  params: ModelParams
  updatedAt: number
  updatedBy: string
}

interface ModelParamChange {
  id: string
  timestamp: number
  actor: string
  action: "switch_model" | "update_params"
  fromModelId?: string
  toModelId?: string
  paramKey?: keyof ModelParams
  oldValue?: number
  newValue?: number
  detail: string
}

const PARAM_LABELS: Record<keyof ModelParams, string> = {
  temperature: "Temperature",
  maxTokens: "Max Tokens",
  topP: "Top P",
  frequencyPenalty: "Frequency Penalty",
  presencePenalty: "Presence Penalty",
}

const PARAM_DESCRIPTIONS: Record<keyof ModelParams, string> = {
  temperature: "Controls randomness — lower is more focused, higher is more creative",
  maxTokens: "Maximum number of tokens in the response",
  topP: "Nucleus sampling — limits token selection to the top cumulative probability",
  frequencyPenalty: "Reduces repetition of tokens based on existing frequency",
  presencePenalty: "Increases likelihood of new topics by penalising repeated tokens",
}

function ParamSlider({
  label,
  description,
  value,
  limits,
  disabled,
  onChange,
}: {
  label: string
  description: string
  value: number
  limits: ParamLimits
  disabled: boolean
  onChange: (v: number) => void
}) {
  const isFixed = limits.min === limits.max

  return (
    <div className={`rounded-lg border border-border bg-card p-4 ${isFixed ? "opacity-40" : ""}`}>
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
        <span className="ml-4 min-w-[4rem] rounded-md border border-border bg-background px-2 py-1 text-right text-sm font-mono text-foreground">
          {value}
        </span>
      </div>
      {isFixed ? (
        <p className="text-xs text-muted-foreground italic">Not supported by this model</p>
      ) : (
        <input
          type="range"
          min={limits.min}
          max={limits.max}
          step={limits.step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="mt-2 w-full accent-primary"
        />
      )}
      {!isFixed && (
        <div className="mt-1 flex justify-between text-xs text-muted-foreground">
          <span>{limits.min}</span>
          <span>{limits.max}</span>
        </div>
      )}
    </div>
  )
}

export default function ModelsPage() {
  const [models, setModels] = useState<ModelDefinition[]>([])
  const [activeModel, setActiveModel] = useState<ModelDefinition | null>(null)
  const [activeState, setActiveState] = useState<ModelState | null>(null)
  const [changeLog, setChangeLog] = useState<ModelParamChange[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [localParams, setLocalParams] = useState<ModelParams | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/models?limit=100")
      if (!res.ok) return
      const data = await res.json()
      setModels(data.models ?? [])
      setActiveModel(data.activeModel ?? null)
      setActiveState(data.activeState ?? null)
      setChangeLog(data.changeLog ?? [])
      if (!localParams) {
        setLocalParams(data.activeState?.params ?? null)
      }
    } catch (err) {
      console.error("Failed to fetch model data:", err)
    } finally {
      setLoading(false)
    }
  }, [localParams])

  useEffect(() => {
    fetchData()
    const interval = setInterval(() => {
      fetch("/api/admin/models?limit=100")
        .then((r) => r.json())
        .then((data) => {
          setModels(data.models ?? [])
          setChangeLog(data.changeLog ?? [])
        })
        .catch(() => {})
    }, 5000)
    return () => clearInterval(interval)
  }, [fetchData])

  async function handleSwitchModel(modelId: string) {
    setSaving(true)
    try {
      const res = await fetch("/api/admin/models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "switch", modelId }),
      })
      const data = await res.json()
      if (data.state) {
        const newModel = models.find((m) => m.id === modelId) ?? null
        setActiveModel(newModel)
        setActiveState(data.state)
        setLocalParams(data.state.params)
        await fetchData()
      }
    } catch (err) {
      console.error("Failed to switch model:", err)
    } finally {
      setSaving(false)
    }
  }

  async function handleParamChange(paramKey: keyof ModelParams, value: number) {
    setLocalParams((prev) => prev ? { ...prev, [paramKey]: value } : prev)
    setSaving(true)
    try {
      const res = await fetch("/api/admin/models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "update_param", paramKey, value }),
      })
      const data = await res.json()
      if (data.state) {
        setActiveState(data.state)
        setLocalParams(data.state.params)
        await fetchData()
      }
    } catch (err) {
      console.error("Failed to update param:", err)
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    setSaving(true)
    try {
      const res = await fetch("/api/admin/models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset" }),
      })
      const data = await res.json()
      if (data.state) {
        setActiveState(data.state)
        setLocalParams(data.state.params)
        await fetchData()
      }
    } catch (err) {
      console.error("Failed to reset params:", err)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  const params = localParams ?? activeState?.params ?? null

  return (
    <div className="flex min-h-screen bg-background">
      <AdminSidebar />
      <main className="flex-1 overflow-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Model Control</h1>
          <p className="text-sm text-muted-foreground">Select the active AI model and tune its parameters</p>
        </div>

        {/* ── Colour Bar ── */}
        <div className="mb-6 overflow-hidden rounded-xl border border-border">
          <div className="flex h-3">
            {models.map((m) => (
              <div
                key={m.id}
                title={m.name}
                style={{
                  backgroundColor: m.color,
                  flex: 1,
                  opacity: activeModel?.id === m.id ? 1 : 0.25,
                  transition: "opacity 0.3s",
                }}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-2 bg-card px-4 py-3">
            {models.map((m) => (
              <button
                key={m.id}
                disabled={saving}
                onClick={() => handleSwitchModel(m.id)}
                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-all ${
                  activeModel?.id === m.id
                    ? "border-transparent text-white shadow-md"
                    : "border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground"
                }`}
                style={
                  activeModel?.id === m.id
                    ? { backgroundColor: m.color, borderColor: m.color }
                    : {}
                }
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: m.color }}
                />
                {m.name}
                <span className="opacity-70">· {m.provider}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── Parameter Control Bar ── */}
        {activeModel && params && (
          <div className="mb-6 rounded-xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-3">
                <span
                  className="h-4 w-4 rounded-full"
                  style={{ backgroundColor: activeModel.color }}
                />
                <div>
                  <h2 className="text-sm font-semibold text-foreground">{activeModel.name} Parameters</h2>
                  {activeState && (
                    <p className="text-xs text-muted-foreground">
                      Last updated {new Date(activeState.updatedAt).toLocaleString()} by{" "}
                      <span className="text-foreground">{activeState.updatedBy}</span>
                    </p>
                  )}
                </div>
              </div>
              <button
                disabled={saving}
                onClick={handleReset}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:border-primary/50 hover:text-foreground disabled:opacity-50"
              >
                Reset to Defaults
              </button>
            </div>

            <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
              {(Object.keys(PARAM_LABELS) as (keyof ModelParams)[]).map((key) => (
                <ParamSlider
                  key={key}
                  label={PARAM_LABELS[key]}
                  description={PARAM_DESCRIPTIONS[key]}
                  value={params[key]}
                  limits={activeModel.paramLimits[key]}
                  disabled={saving}
                  onChange={(v) => handleParamChange(key, v)}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Activity Log ── */}
        <div className="rounded-xl border border-border bg-card">
          <div className="border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Activity Log — who changed what, when
            </h2>
          </div>
          {changeLog.length === 0 ? (
            <p className="p-5 text-sm text-muted-foreground">No activity yet</p>
          ) : (
            <div className="divide-y divide-border">
              {changeLog.map((entry) => {
                const model =
                  entry.action === "switch_model"
                    ? models.find((m) => m.id === entry.toModelId)
                    : models.find((m) => m.id === activeModel?.id)
                return (
                  <div key={entry.id} className="flex items-start gap-4 px-5 py-3">
                    <div
                      className="mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full"
                      style={{ backgroundColor: model?.color ?? "#6B7280" }}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-foreground">{entry.detail}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">{entry.actor}</span>
                        {" · "}
                        {new Date(entry.timestamp).toLocaleString()}
                      </p>
                    </div>
                    <span
                      className={`flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                        entry.action === "switch_model"
                          ? "bg-purple-500/10 text-purple-400"
                          : "bg-blue-500/10 text-blue-400"
                      }`}
                    >
                      {entry.action === "switch_model" ? "model switch" : "param update"}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
