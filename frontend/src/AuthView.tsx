import { useState } from 'react'
import { api, saveSession, type Me } from './api'

type Mode = 'signin' | 'signup'

export function AuthView({ mode, onDone }: { mode: Mode; onDone: (me: Me) => void }) {
  const [fullName, setFullName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const session =
        mode === 'signup'
          ? await api.signup({ org_name: orgName, full_name: fullName, email, password })
          : await api.login({ email, password })
      saveSession(session)
      onDone(await api.me())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  const isSignup = mode === 'signup'

  return (
    <div className="auth-wrap">
      <div className="auth-form-side">
        <div className="auth-card">
          <div className="row" style={{ marginBottom: 40 }}>
            <span className="seal">D</span>
            <span className="brand">Deskpal</span>
          </div>
          <h1 className="page-title">{isSignup ? 'Put your documents on duty.' : 'Welcome back.'}</h1>
          <p className="page-sub">
            {isSignup ? 'Create your workspace — free plan, no card required.' : 'Sign in to your workspace.'}
          </p>
          {error && <div className="error-banner">{error}</div>}
          <form onSubmit={submit}>
            {isSignup && (
              <>
                <label className="field">
                  <span>Your name</span>
                  <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
                </label>
                <label className="field">
                  <span>Business name</span>
                  <input type="text" value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
                </label>
              </>
            )}
            <label className="field">
              <span>Work email</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isSignup ? 'At least 8 characters, with a letter and a number' : ''}
                required
              />
            </label>
            <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
              {busy ? 'Working…' : isSignup ? 'Create workspace' : 'Sign in'}
            </button>
          </form>
          <p className="muted" style={{ marginTop: 22, textAlign: 'center' }}>
            {isSignup ? (
              <>Already have a workspace? <a href="#/signin">Sign in</a></>
            ) : (
              <>New to Deskpal? <a href="#/signup">Create a free workspace</a></>
            )}
          </p>
        </div>
      </div>
      <div className="auth-brand-side">
        <blockquote className="auth-quote">
          “The questions never stop.
          <br />
          <em>Now the answers don’t either.”</em>
        </blockquote>
        <p style={{ fontSize: 13, letterSpacing: '0.16em', textTransform: 'uppercase', opacity: 0.75 }}>
          ● Your documents, on duty — 24/7
        </p>
      </div>
    </div>
  )
}
