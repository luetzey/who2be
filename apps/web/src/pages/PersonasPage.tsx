import { Link } from 'react-router-dom'

import { useSession } from '../auth/session-context'
import { usePersonas } from '../hooks/usePersonas'

export function PersonasPage() {
  const { personas, loading, error } = usePersonas()
  const { signOut } = useSession()

  return (
    <main>
      <header>
        <h1>Personae</h1>
        <nav>
          <Link to="/personas/new">Neue Persona</Link>{' '}
          <Link to="/playbooks">Zu den Playbooks</Link>{' '}
          <Link to="/settings/tokens">API-Tokens</Link>{' '}
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
    </main>
  )
}
