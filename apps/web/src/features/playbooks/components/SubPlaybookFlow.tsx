import { ArrowRight } from 'lucide-react'
import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook } from '@/api/types'

// Design-Handoff „Playbooks-Redesign" §Beziehungen: die Ausfuehrungs-
// Reihenfolge eines Composites als horizontaler Flow — Nummern-Badges in
// der --ca-Tint (pill-catalog), ArrowRight-Konnektoren, jedes Kind ein Link.

interface SubPlaybookFlowProps {
  children: Playbook[]
  wsPath: (path: string) => string
}

export function SubPlaybookFlow({ children, wsPath }: SubPlaybookFlowProps) {
  const { t } = useTranslation('playbooks')
  if (children.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('detail.subPlaybooksEmpty')}</p>
  }
  return (
    <ol
      className="flex flex-wrap items-stretch gap-3"
      aria-label={t('list.subPlaybooksListLabel')}
    >
      {children.map((child, index) => (
        <Fragment key={child.id}>
          {index > 0 ? (
            <li aria-hidden="true" className="flex items-center text-muted-foreground">
              <ArrowRight className="size-4" />
            </li>
          ) : null}
          <li className="flex min-w-40 flex-1">
            <Link
              to={wsPath(`/playbooks/${child.id}`)}
              className="flex w-full items-center gap-2 rounded-lg border bg-muted/40 px-3 py-3 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span
                className="flex size-5 shrink-0 items-center justify-center rounded-full bg-pill-catalog text-xs font-bold text-pill-catalog-fg"
                aria-hidden="true"
              >
                {index + 1}
              </span>
              <span className="min-w-0 truncate text-sm font-medium text-foreground">
                {child.name}
              </span>
            </Link>
          </li>
        </Fragment>
      ))}
    </ol>
  )
}
