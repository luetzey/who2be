// ComposedByList — read-only Backlinks aus GET /{id}/composed_by.
// Zeigt welche Composite-Playbooks dieses Playbook als Sub-Playbook enthalten.

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { PlaybookRef } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

interface ComposedByListProps {
  parents: PlaybookRef[]
}

export function ComposedByList({ parents }: ComposedByListProps) {
  const { t } = useTranslation('playbooks')
  const wsPath = useWorkspacePath()

  if (parents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {t('composedBy.empty')}
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-1" aria-label={t('composedBy.ariaLabel')}>
      {parents.map((parent) => (
        <li key={parent.id} className="text-sm">
          <Link
            to={wsPath(`/playbooks/${parent.id}`)}
            className="rounded-sm text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
          >
            {parent.name}
          </Link>
        </li>
      ))}
    </ul>
  )
}
