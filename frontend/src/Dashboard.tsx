import { useEffect, useRef, useState } from 'react'
import { api, type Bot, type Doc, type Me, type Msg } from './api'

function TopBar({ me, onSignOut }: { me: Me; onSignOut: () => void }) {
  return (
    <header className="topbar">
      <span className="seal">D</span>
      <span className="brand">Deskpal</span>
      <span className="muted" style={{ fontSize: 13 }}>{me.org_name}</span>
      <span className="spacer" />
      <span className="user-chip">
        {me.full_name}
        <span className="role-badge">{me.role}</span>
      </span>
      <button className="btn btn-ghost" onClick={onSignOut}>Sign out</button>
    </header>
  )
}

export function BotsView({ me, onSignOut, onOpen }: { me: Me; onSignOut: () => void; onOpen: (b: Bot) => void }) {
  const [bots, setBots] = useState<Bot[]>([])
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const refresh = () => api.bots().then(setBots).catch((e) => setError(e.message))
  useEffect(() => { refresh() }, [])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await api.createBot(name.trim())
      setName('')
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed')
    }
  }

  const remove = async (b: Bot) => {
    if (!confirm(`Delete “${b.name}” and all its documents?`)) return
    await api.deleteBot(b.id).catch((e) => setError(e.message))
    refresh()
  }

  return (
    <div className="app-shell">
      <TopBar me={me} onSignOut={onSignOut} />
      <main>
        <h1 className="page-title">Your bots</h1>
        <p className="page-sub">Upload documents, test in the playground, then embed the widget on your site.</p>
        {error && <div className="error-banner">{error}</div>}

        <div className="card">
          <form onSubmit={create} className="row">
            <input
              type="text"
              className="grow"
              placeholder="Name your bot — e.g. “Storefront Support”"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <button className="btn btn-primary" disabled={!name.trim()}>Create bot</button>
          </form>
        </div>

        {bots.length === 0 ? (
          <div className="card empty-state">No bots yet — create your first one above.</div>
        ) : (
          bots.map((b) => (
            <div className="card row" key={b.id} style={{ cursor: 'pointer' }} onClick={() => onOpen(b)}>
              <div className="grow">
                <div style={{ fontWeight: 600, fontSize: 16 }}>{b.name}</div>
                <div className="muted">Created {new Date(b.created_at).toLocaleDateString()}</div>
              </div>
              <button
                className="btn btn-danger"
                onClick={(e) => { e.stopPropagation(); remove(b) }}
              >
                Delete
              </button>
              <button className="btn btn-ghost">Open →</button>
            </div>
          ))
        )}
      </main>
    </div>
  )
}

const TABS = ['documents', 'playground', 'conversations'] as const
type Tab = (typeof TABS)[number]

export function BotView({ me, bot, onBack, onSignOut }: { me: Me; bot: Bot; onBack: () => void; onSignOut: () => void }) {
  const [tab, setTab] = useState<Tab>('documents')
  return (
    <div className="app-shell">
      <TopBar me={me} onSignOut={onSignOut} />
      <main>
        <button className="btn btn-ghost" style={{ marginBottom: 18 }} onClick={onBack}>← All bots</button>
        <h1 className="page-title">{bot.name}</h1>
        <p className="page-sub">Train it on your documents, then let it take the night shift.</p>
        <div className="tabs">
          {TABS.map((t) => (
            <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        {tab === 'documents' && <DocumentsTab bot={bot} />}
        {tab === 'playground' && <PlaygroundTab bot={bot} />}
        {tab === 'conversations' && <ConversationsTab bot={bot} />}
      </main>
    </div>
  )
}

function DocumentsTab({ bot }: { bot: Bot }) {
  const [docs, setDocs] = useState<Doc[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const refresh = () => api.documents(bot.id).then(setDocs).catch((e) => setError(e.message))
  useEffect(() => {
    refresh()
    // Poll while any document is still being processed.
    const timer = setInterval(() => {
      setDocs((current) => {
        if (current.some((d) => d.status === 'pending' || d.status === 'processing')) refresh()
        return current
      })
    }, 1500)
    return () => clearInterval(timer)
  }, [bot.id])

  const upload = async (file: File) => {
    setError('')
    setBusy(true)
    try {
      await api.upload(bot.id, file)
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const remove = async (d: Doc) => {
    await api.deleteDocument(bot.id, d.id).catch((e) => setError(e.message))
    refresh()
  }

  return (
    <>
      {error && <div className="error-banner">{error}</div>}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row">
          <div className="grow">
            <div style={{ fontWeight: 600 }}>Upload a document</div>
            <div className="muted">PDF, DOCX or TXT — up to 10MB. Re-uploading the same filename replaces its content.</div>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
          <button className="btn btn-primary" disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? 'Uploading…' : 'Choose file'}
          </button>
        </div>
      </div>

      {docs.length === 0 ? (
        <div className="card empty-state">The bot knows nothing yet — upload its first document.</div>
      ) : (
        docs.map((d) => (
          <div className="card row" key={d.id}>
            <div className="grow">
              <div style={{ fontWeight: 600 }}>{d.filename}</div>
              <div className="muted row" style={{ gap: 8, marginTop: 4 }}>
                <span className={`badge badge-${d.status}`}>{d.status}</span>
                {d.quarantined_chunks > 0 && (
                  <span className="badge badge-quarantine">
                    {d.quarantined_chunks} hostile sentence{d.quarantined_chunks > 1 ? 's' : ''} quarantined
                  </span>
                )}
              </div>
            </div>
            <button className="btn btn-danger" onClick={() => remove(d)}>Delete</button>
          </div>
        ))
      )}
    </>
  )
}

function PlaygroundTab({ bot }: { bot: Bot }) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setError('')
    setBusy(true)
    const optimistic: Msg = {
      id: Date.now(), role: 'user', content: text, sources: [], created_at: new Date().toISOString(),
    }
    setMessages((m) => [...m, optimistic])
    setInput('')
    try {
      const reply = await api.chat(bot.id, text)
      setMessages((m) => [
        ...m,
        {
          id: Date.now() + 1, role: 'assistant', content: reply.answer,
          sources: reply.sources, created_at: new Date().toISOString(),
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat failed')
      setMessages((m) => m.slice(0, -1))
      setInput(text)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      {error && <div className="error-banner">{error}</div>}
      <div className="chat-log" ref={logRef}>
        {messages.length === 0 && (
          <div className="empty-state">Test the bot here before it meets your customers.</div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-bot'}`}>
            {m.content}
            {m.sources.length > 0 && (
              <div>
                {m.sources.map((s, i) => (
                  <span key={i} className="source-chip">ⓘ {s.document_name}</span>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg msg-bot muted">thinking…</div>}
      </div>
      <form className="chat-input-row" onSubmit={send}>
        <input
          type="text"
          className="grow"
          placeholder="Ask a question your documents should answer…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>Send</button>
      </form>
    </div>
  )
}

function ConversationsTab({ bot }: { bot: Bot }) {
  const [messages, setMessages] = useState<Msg[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.conversations(bot.id).then(setMessages).catch((e) => setError(e.message))
  }, [bot.id])

  if (error) return <div className="error-banner">{error}</div>
  if (messages.length === 0) return <div className="card empty-state">No conversations yet.</div>
  return (
    <div className="card">
      <div className="chat-log" style={{ maxHeight: 600 }}>
        {[...messages].reverse().map((m) => (
          <div key={m.id} className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-bot'}`}>
            <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
              {m.role} · {new Date(m.created_at).toLocaleString()}
            </div>
            {m.content}
            {m.sources?.length > 0 && (
              <div>{m.sources.map((s, i) => <span key={i} className="source-chip">ⓘ {s.document_name}</span>)}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
