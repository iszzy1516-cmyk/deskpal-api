// Tiny API client. Token lives in localStorage; 401s clear the session.

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Session = { access_token: string; refresh_token: string }
export type Me = {
  id: number; email: string; full_name: string; role: string
  org_id: number; org_name: string; org_plan: string
}
export type Bot = { id: number; name: string; widget_settings: Record<string, unknown>; created_at: string }
export type Doc = {
  id: number; bot_id: number; filename: string; status: string
  quarantined_chunks: number; created_at: string
}
export type Source = { document_name: string; chunk_index: number; snippet: string }
export type ChatReply = { answer: string; sources: Source[]; used_documents: boolean }
export type Msg = { id: number; role: string; content: string; sources: Source[]; created_at: string }

const TOKENS_KEY = 'deskpal_tokens'

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(TOKENS_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveSession(s: Session | null) {
  if (s) localStorage.setItem(TOKENS_KEY, JSON.stringify(s))
  else localStorage.removeItem(TOKENS_KEY)
}

async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  const session = loadSession()
  if (auth && session) headers['Authorization'] = `Bearer ${session.access_token}`
  if (init.body && typeof init.body === 'string') headers['Content-Type'] = 'application/json'

  const resp = await fetch(`${BASE}${path}`, { ...init, headers })
  if (resp.status === 401 && auth) {
    saveSession(null)
    window.location.reload()
    throw new Error('Session expired')
  }
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`
    try {
      const body = await resp.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep default */ }
    throw new Error(detail)
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const api = {
  signup: (payload: { org_name: string; full_name: string; email: string; password: string }) =>
    request<Session>('/api/auth/signup', { method: 'POST', body: JSON.stringify(payload) }, false),
  login: (payload: { email: string; password: string }) =>
    request<Session>('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) }, false),
  me: () => request<Me>('/api/auth/me'),
  bots: () => request<Bot[]>('/api/bots'),
  createBot: (name: string) =>
    request<Bot>('/api/bots', { method: 'POST', body: JSON.stringify({ name }) }),
  deleteBot: (id: number) => request<void>(`/api/bots/${id}`, { method: 'DELETE' }),
  documents: (botId: number) => request<Doc[]>(`/api/bots/${botId}/documents`),
  upload: (botId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Doc>(`/api/bots/${botId}/documents`, { method: 'POST', body: form })
  },
  deleteDocument: (botId: number, docId: number) =>
    request<void>(`/api/bots/${botId}/documents/${docId}`, { method: 'DELETE' }),
  chat: (botId: number, message: string) =>
    request<ChatReply>(`/api/bots/${botId}/chat`, { method: 'POST', body: JSON.stringify({ message }) }),
  conversations: (botId: number) => request<Msg[]>(`/api/bots/${botId}/conversations`),
}
