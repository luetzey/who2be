import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { useApi } from '../api/useApi'
import { usePlaybooks } from '../hooks/usePlaybooks'

function splitTags(raw: string): string[] {
  return raw
    .split(',')
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0)
}

export function PlaybooksPage() {
  const [tagFilter, setTagFilter] = useState('')
  const [triggerFilter, setTriggerFilter] = useState('')
  const { playbooks, loading, error, reload } = usePlaybooks(tagFilter, triggerFilter)
  const api = useApi()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [body, setBody] = useState('')
  const [type, setType] = useState('workflow')
  const [tags, setTags] = useState('')
  const [triggers, setTriggers] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    try {
      await api.createPlaybook({
        name,
        content: {
          description,
          body,
          type,
          tags: splitTags(tags),
          triggers: triggers.trim() === '' ? null : triggers.trim(),
        },
      })
      setName('')
      setDescription('')
      setBody('')
      setTags('')
      setTriggers('')
      reload()
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
    }
  }

  return (
    <main>
      <header>
        <h1>Playbooks</h1>
        <nav>
          <Link to="/">Zu den Personae</Link>
        </nav>
      </header>

      <section>
        <label>
          Tag-Filter
          <input value={tagFilter} onChange={(event) => setTagFilter(event.target.value)} />
        </label>
        <label>
          Trigger-Filter
          <input
            value={triggerFilter}
            onChange={(event) => setTriggerFilter(event.target.value)}
          />
        </label>
      </section>

      {loading && <p>Lädt…</p>}
      {error !== null && <p role="alert">{error}</p>}
      <ul>
        {playbooks.map((playbook) => (
          <li key={playbook.id}>
            <Link to={`/playbooks/${playbook.id}`}>{playbook.name}</Link> (
            {playbook.type}, v{playbook.current_version})
          </li>
        ))}
      </ul>

      <h2>Neues Playbook</h2>
      <form onSubmit={handleCreate}>
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
        <button type="submit">Anlegen</button>
      </form>
      {formError !== null && <p role="alert">{formError}</p>}
    </main>
  )
}
