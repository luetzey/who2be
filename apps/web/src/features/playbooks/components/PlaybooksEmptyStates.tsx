import { BookOpen, Plus, Search, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { playbookTypeMeta } from '../lib/typeMeta'

// Design-Handoff „Playbooks-Redesign" §Leerzustaende (3a/3b): warme
// Onboarding-Hero-Card statt der Standard-Dashed-EmptyState plus ein
// gefilterter Leerzustand mit Reset-Aktion.

const TYPE_HINTS = ['workflow', 'faq', 'checklist', 'snippet'] as const

export function PlaybooksOnboarding({ newHref }: { newHref: string }) {
  const { t } = useTranslation('playbooks')
  return (
    <div className="flex flex-col items-center rounded-xl border bg-muted/40 p-12 text-center">
      <span
        className="mb-6 flex size-16 items-center justify-center rounded-xl bg-pill-catalog text-pill-catalog-fg shadow-card"
        aria-hidden="true"
      >
        <BookOpen className="size-8" />
      </span>
      <h2 className="text-xl font-semibold tracking-tight">
        {t('list.onboarding.title')}
      </h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        {t('list.onboarding.description')}
      </p>
      <Button asChild variant="brand" size="lg" className="mt-6">
        <Link to={newHref}>
          <Plus className="size-4" aria-hidden="true" />
          {t('list.newButton')}
        </Link>
      </Button>
      <div className="mt-8 flex max-w-xl flex-wrap justify-center gap-2">
        {TYPE_HINTS.map((type) => {
          const meta = playbookTypeMeta(type)
          const Icon = meta.icon
          return (
            <span
              key={type}
              className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs text-foreground"
            >
              <span
                className={cn(
                  'flex size-4 items-center justify-center rounded-sm',
                  meta.tint,
                )}
                aria-hidden="true"
              >
                {/* size-3 bewusst (funktionaler Sonderfall §8): Icon muss in
                    den size-4-Tint-Container passen. */}
                <Icon className="size-3" />
              </span>
              {t(`list.onboarding.types.${type}`)}
            </span>
          )
        })}
      </div>
    </div>
  )
}

export function PlaybooksNoResults({
  query,
  onReset,
}: {
  query: string
  onReset: () => void
}) {
  const { t } = useTranslation(['playbooks', 'data'])
  return (
    <div className="flex flex-col items-center rounded-xl border bg-muted/40 p-12 text-center">
      <span
        className="mb-4 flex size-12 items-center justify-center rounded-xl bg-muted text-muted-foreground"
        aria-hidden="true"
      >
        <Search className="size-6" />
      </span>
      <h2 className="text-lg font-semibold tracking-tight">
        {query !== ''
          ? t('playbooks:list.noResults.title', { query })
          : t('data:filter.emptyFilteredTitle')}
      </h2>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        {t('playbooks:list.noResults.description')}
      </p>
      <Button type="button" variant="outline" className="mt-4 gap-2" onClick={onReset}>
        <X className="size-3.5" aria-hidden="true" />
        {t('data:filter.reset')}
      </Button>
    </div>
  )
}
