import { v4 as uuidv4 } from "uuid"
import { recordAudit } from "./audit"
import { logEvent } from "./engine"

// ─── Types ───

export interface ModelParams {
  temperature: number
  maxTokens: number
  topP: number
  frequencyPenalty: number
  presencePenalty: number
}

export interface ModelDefinition {
  id: string
  name: string
  provider: string
  color: string
  defaultParams: ModelParams
  paramLimits: {
    temperature: { min: number; max: number; step: number }
    maxTokens: { min: number; max: number; step: number }
    topP: { min: number; max: number; step: number }
    frequencyPenalty: { min: number; max: number; step: number }
    presencePenalty: { min: number; max: number; step: number }
  }
}

export interface ModelState {
  modelId: string
  params: ModelParams
  updatedAt: number
  updatedBy: string
}

export interface ModelParamChange {
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

// ─── Available Models ───

export const MODELS: ModelDefinition[] = [
  {
    id: "gpt-4o",
    name: "GPT-4o",
    provider: "OpenAI",
    color: "#10B981",
    defaultParams: { temperature: 0.7, maxTokens: 4096, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 2, step: 0.01 },
      maxTokens: { min: 1, max: 16384, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: -2, max: 2, step: 0.01 },
      presencePenalty: { min: -2, max: 2, step: 0.01 },
    },
  },
  {
    id: "gpt-4-turbo",
    name: "GPT-4 Turbo",
    provider: "OpenAI",
    color: "#3B82F6",
    defaultParams: { temperature: 0.7, maxTokens: 4096, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 2, step: 0.01 },
      maxTokens: { min: 1, max: 128000, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: -2, max: 2, step: 0.01 },
      presencePenalty: { min: -2, max: 2, step: 0.01 },
    },
  },
  {
    id: "claude-3-opus",
    name: "Claude 3 Opus",
    provider: "Anthropic",
    color: "#8B5CF6",
    defaultParams: { temperature: 1.0, maxTokens: 4096, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 1, step: 0.01 },
      maxTokens: { min: 1, max: 4096, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: 0, max: 0, step: 0 },
      presencePenalty: { min: 0, max: 0, step: 0 },
    },
  },
  {
    id: "claude-3-sonnet",
    name: "Claude 3 Sonnet",
    provider: "Anthropic",
    color: "#A855F7",
    defaultParams: { temperature: 1.0, maxTokens: 4096, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 1, step: 0.01 },
      maxTokens: { min: 1, max: 4096, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: 0, max: 0, step: 0 },
      presencePenalty: { min: 0, max: 0, step: 0 },
    },
  },
  {
    id: "gemini-pro",
    name: "Gemini Pro",
    provider: "Google",
    color: "#F59E0B",
    defaultParams: { temperature: 0.9, maxTokens: 2048, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 1, step: 0.01 },
      maxTokens: { min: 1, max: 8192, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: 0, max: 0, step: 0 },
      presencePenalty: { min: 0, max: 0, step: 0 },
    },
  },
  {
    id: "mistral-large",
    name: "Mistral Large",
    provider: "Mistral",
    color: "#14B8A6",
    defaultParams: { temperature: 0.7, maxTokens: 4096, topP: 1.0, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 1, step: 0.01 },
      maxTokens: { min: 1, max: 32000, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: 0, max: 0, step: 0 },
      presencePenalty: { min: 0, max: 0, step: 0 },
    },
  },
  {
    id: "llama-3-70b",
    name: "Llama 3 70B",
    provider: "Meta",
    color: "#EF4444",
    defaultParams: { temperature: 0.6, maxTokens: 4096, topP: 0.9, frequencyPenalty: 0.0, presencePenalty: 0.0 },
    paramLimits: {
      temperature: { min: 0, max: 2, step: 0.01 },
      maxTokens: { min: 1, max: 8192, step: 1 },
      topP: { min: 0, max: 1, step: 0.01 },
      frequencyPenalty: { min: 0, max: 0, step: 0 },
      presencePenalty: { min: 0, max: 0, step: 0 },
    },
  },
]

// ─── Store ───

let activeState: ModelState = {
  modelId: MODELS[0].id,
  params: { ...MODELS[0].defaultParams },
  updatedAt: Date.now(),
  updatedBy: "system",
}

const changeLog: ModelParamChange[] = []
const MAX_CHANGES = 1000

// ─── Core API ───

export function getActiveModel(): { model: ModelDefinition; state: ModelState } {
  const model = MODELS.find((m) => m.id === activeState.modelId) ?? MODELS[0]
  return { model, state: { ...activeState } }
}

export function getAllModels(): ModelDefinition[] {
  return MODELS
}

export function switchModel(toModelId: string, actor: string = "admin"): ModelState | null {
  const toModel = MODELS.find((m) => m.id === toModelId)
  if (!toModel) return null

  const fromModelId = activeState.modelId
  const change: ModelParamChange = {
    id: uuidv4(),
    timestamp: Date.now(),
    actor,
    action: "switch_model",
    fromModelId,
    toModelId,
    detail: `Switched model from ${fromModelId} to ${toModelId}`,
  }

  activeState = {
    modelId: toModelId,
    params: { ...toModel.defaultParams },
    updatedAt: Date.now(),
    updatedBy: actor,
  }

  changeLog.unshift(change)
  if (changeLog.length > MAX_CHANGES) changeLog.splice(MAX_CHANGES)

  recordAudit("switch_model", actor, "success", `Switched to model: ${toModel.name}`)
  logEvent("info", "admin", `Model switched to ${toModel.name} by ${actor}`, "models")

  return { ...activeState }
}

export function updateModelParam(
  paramKey: keyof ModelParams,
  value: number,
  actor: string = "admin"
): ModelState | null {
  const model = MODELS.find((m) => m.id === activeState.modelId)
  if (!model) return null

  const limits = model.paramLimits[paramKey]
  const clamped = Math.min(limits.max, Math.max(limits.min, value))

  const change: ModelParamChange = {
    id: uuidv4(),
    timestamp: Date.now(),
    actor,
    action: "update_params",
    paramKey,
    oldValue: activeState.params[paramKey],
    newValue: clamped,
    detail: `Updated ${paramKey} from ${activeState.params[paramKey]} to ${clamped} on ${model.name}`,
  }

  activeState = {
    ...activeState,
    params: { ...activeState.params, [paramKey]: clamped },
    updatedAt: Date.now(),
    updatedBy: actor,
  }

  changeLog.unshift(change)
  if (changeLog.length > MAX_CHANGES) changeLog.splice(MAX_CHANGES)

  recordAudit("update_model_params", actor, "success", change.detail)
  logEvent("info", "admin", change.detail, "models")

  return { ...activeState }
}

export function getChangeLog(limit: number = 50): ModelParamChange[] {
  return changeLog.slice(0, limit)
}

export function resetModelParams(actor: string = "admin"): ModelState | null {
  const model = MODELS.find((m) => m.id === activeState.modelId)
  if (!model) return null

  const change: ModelParamChange = {
    id: uuidv4(),
    timestamp: Date.now(),
    actor,
    action: "update_params",
    detail: `Reset all parameters to defaults for model: ${model.name}`,
  }

  activeState = {
    ...activeState,
    params: { ...model.defaultParams },
    updatedAt: Date.now(),
    updatedBy: actor,
  }

  changeLog.unshift(change)
  if (changeLog.length > MAX_CHANGES) changeLog.splice(MAX_CHANGES)

  recordAudit("update_model_params", actor, "success", change.detail)
  logEvent("info", "admin", change.detail, "models")

  return { ...activeState }
}
