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

export function PlaybookNewPage() {
  const api = useApi()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [type, setType] = useState('workflow')
  const [description, setDescription] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState('')
  const [triggers, setTriggers] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const created = await api.createPlaybook({
        name,
        content: {
          description,
          body,
          type,
          tags: splitList(tags),
          triggers: triggers.trim() === '' ? null : triggers.trim(),
        },
      })
      navigate(`/playbooks/${created.id}`)
    } catch (cause) {
      setError(describeError(cause))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <p>
        <Link to="/playbooks">← Playbooks</Link>
      </p>
      <h1>Neues Playbook</h1>
      <form onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Typ
          <input value={type} onChange={(event) => setType(event.target.value)} required />
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
          Inhalt
          <textarea value={body} onChange={(event) => setBody(event.target.value)} required />
        </label>
        <label>
          Tags (kommagetrennt)
          <input value={tags} onChange={(event) => setTags(event.target.value)} />
        </label>
        <label>
          Trigger
          <input value={triggers} onChange={(event) => setTriggers(event.target.value)} />
        </label>
        <button type="submit" disabled={busy}>
          Anlegen
        </button>
      </form>
      {error !== null && <p role="alert">{error}</p>}
    </main>
  )
}
