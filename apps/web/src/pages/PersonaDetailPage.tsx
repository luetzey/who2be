import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { Persona, PersonaVersion, Playbook } from '../api/types'
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

export function PersonaDetailPage() {
  const { id } = useParams<{ id: string }>()
  const api = useApi()
  const [persona, setPersona] = useState<Persona | null>(null)
  const [versions, setVersions] = useState<PersonaVersion[]>([])
  const [allPlaybooks, setAllPlaybooks] = useState<Playbook[]>([])
  const [linkedIds, setLinkedIds] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [traits, setTraits] = useState('')

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setError(null)
    Promise.all([
      api.getPersona(id),
      api.listPersonaVersions(id),
      api.listPersonaPlaybooks(id),
      api.listPlaybooks(),
    ])
      .then(([loaded, versionList, linked, playbooks]) => {
        setPersona(loaded)
        setVersions(versionList)
        setAllPlaybooks(playbooks)
        setLinkedIds(linked.map((playbook) => playbook.id))
        setName(loaded.name)
        setDescription(loaded.content.description)
        setSystemPrompt(loaded.content.system_prompt)
        setTraits(loaded.content.traits.join(', '))
      })
      .catch((cause: unknown) => setError(describeError(cause)))
  }, [api, id])

  useEffect(load, [load])

  if (id === undefined) {
    return <Navigate to="/" replace />
  }
  const personaId = id

  async function handleSave(event: FormEvent) {
    event.preventDefault()
    setStatus(null)
    setError(null)
    try {
      await api.updatePersona(personaId, {
        name,
        content: {
          description,
          system_prompt: systemPrompt,
          traits: splitList(traits),
        },
      })
      setStatus('Gespeichert — neue Version erstellt.')
      load()
    } catch (cause) {
      setError(describeError(cause))
    }
  }

  function toggleLink(playbookId: string) {
    setLinkedIds((current) =>
      current.includes(playbookId)
        ? current.filter((entry) => entry !== playbookId)
        : [...current, playbookId],
    )
  }

  async function handleSaveLinks() {
    setStatus(null)
    setError(null)
    try {
      await api.setPersonaPlaybooks(personaId, linkedIds)
      setStatus('Verknüpfungen gespeichert.')
    } catch (cause) {
      setError(describeError(cause))
    }
  }

  return (
    <main>
      <p>
        <Link to="/">← Personae</Link>
      </p>
      {error !== null && <p role="alert">{error}</p>}
      {status !== null && <p role="status">{status}</p>}

      {persona === null ? (
        <p>Lädt…</p>
      ) : (
        <>
          <h1>{persona.name}</h1>
          <p>Aktuelle Version: {persona.current_version}</p>

          <form onSubmit={handleSave}>
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
            <button type="submit">Speichern (neue Version)</button>
          </form>

          <h2>Versionen</h2>
          <ul>
            {versions.map((version) => (
              <li key={version.version}>
                v{version.version} — {new Date(version.created_at).toLocaleString()}
              </li>
            ))}
          </ul>

          <h2>Verknüpfte Playbooks</h2>
          <ul>
            {allPlaybooks.map((playbook) => (
              <li key={playbook.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={linkedIds.includes(playbook.id)}
                    onChange={() => toggleLink(playbook.id)}
                  />
                  {playbook.name}
                </label>
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => void handleSaveLinks()}>
            Verknüpfungen speichern
          </button>
        </>
      )}
    </main>
  )
}
