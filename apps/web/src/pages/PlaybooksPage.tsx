import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { usePlaybooks } from '../hooks/usePlaybooks'

export function PlaybooksPage() {
  const { playbooks, loading, error } = usePlaybooks()
  const [tagFilter, setTagFilter] = useState('')
  const [triggerFilter, setTriggerFilter] = useState('')

  const filtered = useMemo(() => {
    const tag = tagFilter.trim().toLowerCase()
    const trigger = triggerFilter.trim().toLowerCase()
    return playbooks.filter((playbook) => {
      const tagMatch =
        tag === '' || playbook.tags.some((entry) => entry.toLowerCase().includes(tag))
      const triggerMatch =
        trigger === '' || (playbook.triggers ?? '').toLowerCase().includes(trigger)
      return tagMatch && triggerMatch
    })
  }, [playbooks, tagFilter, triggerFilter])

  return (
    <main>
      <header>
        <h1>Playbooks</h1>
        <nav>
          <Link to="/playbooks/new">Neues Playbook</Link>{' '}
          <Link to="/">Zu den Personae</Link>{' '}
          <Link to="/settings/tokens">API-Tokens</Link>
        </nav>
      </header>

      <section>
        <label>
          Tag-Filter
          <input value={tagFilter} onChange={(event) => setTagFilter(event.target.value)} />
        </label>{' '}
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
        {filtered.map((playbook) => (
          <li key={playbook.id}>
            <Link to={`/playbooks/${playbook.id}`}>{playbook.name}</Link> ({playbook.type},
            v{playbook.current_version}){' '}
            {playbook.tags.length > 0 && (
              <span aria-label="Tags">
                {playbook.tags.map((tag) => (
                  <span key={tag} className="tag-chip">
                    {' '}
                    [{tag}]
                  </span>
                ))}
              </span>
            )}
          </li>
        ))}
      </ul>
    </main>
  )
}
