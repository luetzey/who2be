import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { Playbook, PlaybookVersion } from '../api/types'
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

export function PlaybookDetailPage() {
  const { id } = useParams<{ id: string }>()
  const api = useApi()
  const [playbook, setPlaybook] = useState<Playbook | null>(null)
  const [versions, setVersions] = useState<PlaybookVersion[]>([])
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [name, setName] = useState('')
  const [type, setType] = useState('')
  const [description, setDescription] = useState('')
  const [body, setBody] = useState('')
  const [tags, setTags] = useState('')
  const [triggers, setTriggers] = useState('')

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setError(null)
    Promise.all([api.getPlaybook(id), api.listPlaybookVersions(id)])
      .then(([loaded, versionList]) => {
        setPlaybook(loaded)
        setVersions(versionList)
        setName(loaded.name)
        setType(loaded.content.type)
        setDescription(loaded.content.description)
        setBody(loaded.content.body)
        setTags(loaded.content.tags.join(', '))
        setTriggers(loaded.content.triggers ?? '')
      })
      .catch((cause: unknown) => setError(describeError(cause)))
  }, [api, id])

  useEffect(load, [load])

  if (id === undefined) {
    return <Navigate to="/playbooks" replace />
  }
  const playbookId = id

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    setStatus(null)
    setError(null)
    setSaving(true)
    try {
      await api.updatePlaybook(playbookId, {
        name,
        content: {
          description,
          body,
          type,
          tags: splitList(tags),
          triggers: triggers.trim() === '' ? null : triggers.trim(),
        },
      })
      setStatus('Gespeichert — neue Version erstellt.')
      load()
    } catch (cause) {
      setError(describeError(cause))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main>
      <p>
        <Link to="/playbooks">← Playbooks</Link>
      </p>
      {error !== null && <p role="alert">{error}</p>}
      {status !== null && <p role="status">{status}</p>}

      {playbook === null ? (
        <p>Lädt…</p>
      ) : (
        <>
          <h1>{playbook.name}</h1>
          <p>Aktuelle Version: {playbook.current_version}</p>
          {playbook.tags.length > 0 && (
            <p aria-label="Tags">
              Tags:{' '}
              {playbook.tags.map((tag) => (
                <span key={tag}> [{tag}]</span>
              ))}
            </p>
          )}

          <form onSubmit={handleSave}>
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
            <button type="submit" disabled={saving}>
              Speichern (neue Version)
            </button>
          </form>

          <h2>Versionen</h2>
          <ul>
            {versions.map((version) => (
              <li key={version.version}>
                v{version.version} — {new Date(version.created_at).toLocaleString()}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  )
}
