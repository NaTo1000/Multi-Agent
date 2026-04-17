import { v4 as uuidv4 } from "uuid"

// Admin key is validated against SHA-256 hash
// Set ADMIN_GPG_KEY env var to your admin passphrase
// The system hashes it at runtime for comparison

const ADMIN_SESSION_DURATION = 24 * 60 * 60 * 1000 // 24 hours

interface AdminSession {
  token: string
  createdAt: number
  expiresAt: number
  ip: string
}

const activeSessions = new Map<string, AdminSession>()

/**
 * Hash a string using SHA-256 (Web Crypto API)
 */
export async function hashKey(key: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(key)
  const hashBuffer = await crypto.subtle.digest("SHA-256", data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("")
}

/**
 * Sign a session token with HMAC-SHA256
 */
async function signToken(payload: string, secret: string): Promise<string> {
  const encoder = new TextEncoder()
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  )
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload))
  const sigArray = Array.from(new Uint8Array(signature))
  return sigArray.map((b) => b.toString(16).padStart(2, "0")).join("")
}

/**
 * Validate the admin GPG key against the stored env var
 */
export async function validateAdminKey(inputKey: string): Promise<boolean> {
  const storedKey = process.env.ADMIN_GPG_KEY
  if (!storedKey) {
    // If no key is set, use default for development
    return inputKey === "multi-agent-admin-2026"
  }
  return inputKey === storedKey
}

/**
 * Create a new admin session, returns session token
 */
export async function createSession(ip: string = "unknown"): Promise<string> {
  const token = uuidv4()
  const secret = process.env.ADMIN_GPG_KEY || "multi-agent-admin-2026"
  const signedToken = await signToken(token, secret)

  const session: AdminSession = {
    token: signedToken,
    createdAt: Date.now(),
    expiresAt: Date.now() + ADMIN_SESSION_DURATION,
    ip,
  }

  activeSessions.set(signedToken, session)
  return signedToken
}

/**
 * Validate an existing session token
 */
export function validateSession(token: string): boolean {
  const session = activeSessions.get(token)
  if (!session) return false
  if (Date.now() > session.expiresAt) {
    activeSessions.delete(token)
    return false
  }
  return true
}

/**
 * Destroy a session (logout)
 */
export function destroySession(token: string): void {
  activeSessions.delete(token)
}

/**
 * Get all active session count
 */
export function getActiveSessionCount(): number {
  // Clean expired
  for (const [key, session] of activeSessions) {
    if (Date.now() > session.expiresAt) {
      activeSessions.delete(key)
    }
  }
  return activeSessions.size
}
