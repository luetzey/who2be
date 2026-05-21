import { type FormEvent, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useSession } from '../auth/session-context'

export function LoginPage() {
  const { session, signIn } = useSession()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (session !== null) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(email, password)
      navigate('/')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Login fehlgeschlagen.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <h1>Who2Be — Anmeldung</h1>
      <form onSubmit={handleSubmit}>
        <label>
          E-Mail
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label>
          Passwort
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={busy}>
          Anmelden
        </button>
      </form>
      {error !== null && <p role="alert">{error}</p>}
    </main>
  )
}
