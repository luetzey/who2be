import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { useApi } from '../api/useApi'
import { useSession } from '../auth/session-context'
import { usePersonas } from '../hooks/usePersonas'

export function PersonasPage() {
  const { personas, loading, error, reload } = usePersonas()
  const { signOut } = useSession()
  const api = useApi()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    try {
      await api.createPersona({
        name,
        content: { description, system_prompt: systemPrompt, traits: [] },
      })
      setName('')
      setDescription('')
      setSystemPrompt('')
      reload()
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
    }
  }

  return (
    <main>
      <header>
        <h1>Personae</h1>
        <nav>
          <Link to="/playbooks">Zu den Playbooks</Link>{' '}
          <button type="button" onClick={() => void signOut()}>
            Abmelden
          </button>
        </nav>
      </header>

      {loading && <p>Lädt…</p>}
      {error !== null && <p role="alert">{error}</p>}
      <ul>
        {personas.map((persona) => (
          <li key={persona.id}>
            <Link to={`/personas/${persona.id}`}>{persona.name}</Link> (v
            {persona.current_version})
          </li>
        ))}
      </ul>

      <h2>Neue Persona</h2>
      <form onSubmit={handleCreate}>
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
        <button type="submit">Anlegen</button>
      </form>
      {formError !== null && <p role="alert">{formError}</p>}
    </main>
  )
}
