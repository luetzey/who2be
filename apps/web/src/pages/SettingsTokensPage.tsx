import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { useApi } from '../api/useApi'
import type { TokenCreated } from '../api/types'
import { useAuthTokenContext } from '../auth/auth-token-context'
import { useTokens } from '../hooks/useTokens'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

function maskTail(token: string): string {
  return token.length <= 6 ? token : `…${token.slice(-6)}`
}

export function SettingsTokensPage() {
  const api = useApi()
  const { tokens, loading, error, reload } = useTokens()
  const { overrideToken, setOverrideToken } = useAuthTokenContext()

  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [created, setCreated] = useState<TokenCreated | null>(null)

  const [overrideInput, setOverrideInput] = useState('')

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreating(true)
    setCreateError(null)
    try {
      const result = await api.createToken({ name: newName })
      setCreated(result)
      setNewName('')
      reload()
    } catch (cause) {
      setCreateError(describeError(cause))
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke(id: string) {
    try {
      await api.revokeToken(id)
      reload()
    } catch (cause) {
      setCreateError(describeError(cause))
    }
  }

  function handleOverrideActivate(event: FormEvent) {
    event.preventDefault()
    if (overrideInput === '') {
      return
    }
    setOverrideToken(overrideInput)
    setOverrideInput('')
  }

  return (
    <main>
      <header>
        <h1>API-Tokens</h1>
        <nav>
          <Link to="/">Zurueck zu Personae</Link>
        </nav>
      </header>

      {loading && <p>Lädt…</p>}
      {error !== null && <p role="alert">{error}</p>}

      <ul>
        {tokens.map((token) => {
          const isRevoked = token.revoked_at !== null
          return (
            <li key={token.id}>
              <strong>{token.name}</strong>{' '}
              <small>
                erstellt {token.created_at}
                {token.last_used_at !== null && ` · zuletzt benutzt ${token.last_used_at}`}
                {isRevoked && ` · widerrufen ${token.revoked_at ?? ''}`}
              </small>{' '}
              <button
                type="button"
                onClick={() => void handleRevoke(token.id)}
                disabled={isRevoked}
              >
                Widerrufen
              </button>
            </li>
          )
        })}
      </ul>

      <section aria-labelledby="new-token">
        <h2 id="new-token">Neuen Token anlegen</h2>
        <form onSubmit={handleCreate}>
          <label>
            Name
            <input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={creating}>
            Anlegen
          </button>
        </form>
        {createError !== null && <p role="alert">{createError}</p>}
      </section>

      {created !== null && (
        <section aria-labelledby="new-token-banner" role="status">
          <h2 id="new-token-banner">Neuer Token — jetzt kopieren</h2>
          <p>
            Der Klartext wird genau einmal angezeigt. Nach dem Schliessen ist er
            nicht mehr abrufbar.
          </p>
          <textarea
            readOnly
            aria-label="Klartext-Token"
            value={created.token}
            rows={2}
            onFocus={(event) => event.currentTarget.select()}
          />
          <div>
            <button
              type="button"
              onClick={() => {
                if (typeof navigator !== 'undefined' && navigator.clipboard) {
                  void navigator.clipboard.writeText(created.token)
                }
              }}
            >
              In Zwischenablage kopieren
            </button>{' '}
            <button type="button" onClick={() => setCreated(null)}>
              Schliessen
            </button>
          </div>
        </section>
      )}

      <section aria-labelledby="override">
        <h2 id="override">Headless-Token aktivieren</h2>
        <p>
          Override fuer kuenftige Headless-Use-Cases: Der eingegebene Token
          wird ab sofort statt des Supabase-JWT an die API gesendet. Lebt nur
          in dieser Tab-Sitzung — Reload entfernt ihn.
        </p>
        <p>
          Status:{' '}
          {overrideToken === null
            ? 'kein Override (Supabase-JWT aktiv)'
            : `Override aktiv (${maskTail(overrideToken)})`}
        </p>
        <form onSubmit={handleOverrideActivate}>
          <label>
            w2b_-Token
            <input
              type="password"
              value={overrideInput}
              onChange={(event) => setOverrideInput(event.target.value)}
              placeholder="w2b_..."
            />
          </label>
          <button type="submit" disabled={overrideInput === ''}>
            Aktivieren
          </button>{' '}
          <button
            type="button"
            onClick={() => setOverrideToken(null)}
            disabled={overrideToken === null}
          >
            Override entfernen
          </button>
        </form>
      </section>
    </main>
  )
}
