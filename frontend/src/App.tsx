import { useEffect, useState } from 'react'
import { api, loadSession, saveSession, type Bot, type Me } from './api'
import { AuthView } from './AuthView'
import { BotsView, BotView } from './Dashboard'
import './styles.css'

type Route =
  | { view: 'auth'; mode: 'signin' | 'signup' }
  | { view: 'bots' }
  | { view: 'bot'; bot: Bot }

function parseHash(): Route | null {
  const hash = window.location.hash.replace(/^#/, '') || '/'
  if (hash.startsWith('/signup')) return { view: 'auth', mode: 'signup' }
  if (hash.startsWith('/signin')) return { view: 'auth', mode: 'signin' }
  return null // in-app navigation (bots, bot detail) is state-driven
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [route, setRoute] = useState<Route>(parseHash() ?? { view: 'bots' })
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    const onHash = () => {
      const r = parseHash()
      if (r) setRoute(r)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    // Restore a stored session on load.
    if (!loadSession()) {
      setChecking(false)
      return
    }
    api.me()
      .then(setMe)
      .catch(() => saveSession(null))
      .finally(() => setChecking(false))
  }, [])

  if (checking) return null

  const signOut = () => {
    saveSession(null)
    setMe(null)
    window.location.hash = '#/signin'
  }

  if (!me) {
    const mode = route.view === 'auth' ? route.mode : 'signin'
    return (
      <AuthView
        mode={mode}
        onDone={(user) => {
          setMe(user)
          window.location.hash = '#/'
          setRoute({ view: 'bots' })
        }}
      />
    )
  }

  if (route.view === 'bot') {
    return <BotView me={me} bot={route.bot} onSignOut={signOut} onBack={() => { window.location.hash = '#/'; setRoute({ view: 'bots' }) }} />
  }

  return (
    <BotsView
      me={me}
      onSignOut={signOut}
      onOpen={(bot) => {
        window.location.hash = `#/bots/${bot.id}`
        setRoute({ view: 'bot', bot })
      }}
    />
  )
}
