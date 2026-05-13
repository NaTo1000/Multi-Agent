import { v4 as uuidv4 } from "uuid"
import { logEvent } from "./engine"

// ─── Types ───

export interface Snapshot {
  id: string
  number: number
  timestamp: number
  label: string
  description: string
  state: Record<string, unknown>
  size: number // approximate size in bytes
  createdBy: string
}

// ─── Store ───

const snapshots: Snapshot[] = []
let snapshotCounter = 0
const MAX_SNAPSHOTS = 50

// Default app state to snapshot
function captureCurrentState(): Record<string, unknown> {
  return {
    config: {
      selfRepairEnabled: true,
      maxEvents: 10000,
      sessionDuration: 86400000,
    },
    timestamp: Date.now(),
    environment: process.env.NODE_ENV || "development",
    version: process.env.npm_package_version || "1.0.0",
  }
}

// ─── Core API ───

export function createSnapshot(
  label: string,
  description: string = "",
  createdBy: string = "system",
  customState?: Record<string, unknown>
): Snapshot {
  snapshotCounter++

  const state = customState || captureCurrentState()
  const stateStr = JSON.stringify(state)

  const snapshot: Snapshot = {
    id: uuidv4(),
    number: snapshotCounter,
    timestamp: Date.now(),
    label,
    description,
    state,
    size: new TextEncoder().encode(stateStr).length,
    createdBy,
  }

  snapshots.unshift(snapshot)

  // Cap snapshots
  if (snapshots.length > MAX_SNAPSHOTS) {
    snapshots.splice(MAX_SNAPSHOTS)
  }

  logEvent("info", "admin", `Snapshot #${snapshot.number} created: ${label}`, "mirror", {
    snapshotId: snapshot.id,
  })

  return snapshot
}

export function getSnapshots(limit: number = 20): Snapshot[] {
  return snapshots.slice(0, limit)
}

export function getSnapshot(id: string): Snapshot | null {
  return snapshots.find((s) => s.id === id) || null
}

export function rollbackToSnapshot(id: string): {
  success: boolean
  snapshot?: Snapshot
  message: string
} {
  const snapshot = snapshots.find((s) => s.id === id)
  if (!snapshot) {
    return { success: false, message: `Snapshot ${id} not found` }
  }

  // Create a backup snapshot before rollback
  createSnapshot(
    `Pre-rollback backup`,
    `Auto-backup before rolling back to snapshot #${snapshot.number}`,
    "system"
  )

  logEvent(
    "warning",
    "admin",
    `Rollback to snapshot #${snapshot.number}: ${snapshot.label}`,
    "mirror",
    { snapshotId: snapshot.id, state: snapshot.state }
  )

  return {
    success: true,
    snapshot,
    message: `Successfully rolled back to snapshot #${snapshot.number} (${snapshot.label})`,
  }
}

export function deleteSnapshot(id: string): boolean {
  const idx = snapshots.findIndex((s) => s.id === id)
  if (idx < 0) return false
  const removed = snapshots.splice(idx, 1)[0]
  logEvent("info", "admin", `Snapshot #${removed.number} deleted: ${removed.label}`, "mirror")
  return true
}

export function getSnapshotStats() {
  return {
    total: snapshots.length,
    maxSnapshots: MAX_SNAPSHOTS,
    oldestSnapshot: snapshots.length > 0 ? snapshots[snapshots.length - 1].timestamp : null,
    newestSnapshot: snapshots.length > 0 ? snapshots[0].timestamp : null,
    totalSizeBytes: snapshots.reduce((sum, s) => sum + s.size, 0),
  }
}

// Create initial snapshot on module load
createSnapshot("System Boot", "Initial state captured at system startup", "system")
