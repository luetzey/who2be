// ResourceUsedByList — read-only Backlinks aus GET /resources/{id}/used_by.
// Zeigt welche Resources diese Resource als Sub-Resource fuehren (Track E §3.3).
// Muster: ComposedByList.

import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { ResourceRef } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

interface ResourceUsedByListProps {
  parents: ResourceRef[]
}

export function ResourceUsedByList({ parents }: ResourceUsedByListProps) {
  const { t } = useTranslation('resources')
  const wsPath = useWorkspacePath()

  if (parents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {t('usedBy.empty')}
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-1" aria-label={t('usedBy.ariaLabel')}>
      {parents.map((parent) => (
        <li key={parent.id} className="text-sm">
          <Link
            to={wsPath(`/resources/${parent.id}`)}
            className="rounded-sm text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
          >
            {parent.name}
          </Link>
        </li>
      ))}
    </ul>
  )
}
