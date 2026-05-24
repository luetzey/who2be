import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useApi } from '../api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

export function PersonaNewPage() {
  const api = useApi()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [traits, setTraits] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await api.createPersona({
        name,
        content: {
          description,
          system_prompt: systemPrompt,
          traits: splitList(traits),
        },
      })
      navigate(`/personas/${created.id}`)
    } catch (cause) {
      setError(describeError(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <p>
        <Link to="/">← Personae</Link>
      </p>
      <h1>Neue Persona</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Beschreibung
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            required
          />
        </label>
        <label>
          System-Prompt
          <textarea
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            required
          />
        </label>
        <label>
          Eigenschaften (kommagetrennt)
          <input value={traits} onChange={(event) => setTraits(event.target.value)} />
        </label>
        <button type="submit" disabled={busy}>
          Anlegen
        </button>
      </form>
      {error !== null && <p role="alert">{error}</p>}
    </main>
  )
}
