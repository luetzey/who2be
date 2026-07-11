import { GitBranch, Layers, Pencil, type LucideIcon } from 'lucide-react'
import { useRef, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// Design-Handoff „Playbooks-Redesign" §Detail: Tab-Leiste Bearbeiten /
// Beziehungen / Versionen. Aktiver Tab traegt einen 2px-Brand-Unterstrich.
// ARIA-Tabs-Pattern inkl. Pfeiltasten-Navigation (roving tabindex).

export type PlaybookDetailTab = 'edit' | 'relations' | 'versions'

const TABS: { key: PlaybookDetailTab; icon: LucideIcon }[] = [
  { key: 'edit', icon: Pencil },
  { key: 'relations', icon: Layers },
  { key: 'versions', icon: GitBranch },
]

export function playbookTabPanelId(tab: PlaybookDetailTab): string {
  return `playbook-tabpanel-${tab}`
}

export function playbookTabId(tab: PlaybookDetailTab): string {
  return `playbook-tab-${tab}`
}

interface PlaybookDetailTabsProps {
  active: PlaybookDetailTab
  onChange: (tab: PlaybookDetailTab) => void
}

export function PlaybookDetailTabs({ active, onChange }: PlaybookDetailTabsProps) {
  const { t } = useTranslation('playbooks')
  const refs = useRef(new Map<PlaybookDetailTab, HTMLButtonElement>())

  // Pfeiltasten-Navigation liegt auf den Tab-Buttons (nicht dem tablist-
  // Container) — der Container selbst ist nicht fokussierbar (roving tabindex).
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    event.preventDefault()
    const index = TABS.findIndex((tab) => tab.key === active)
    const delta = event.key === 'ArrowRight' ? 1 : -1
    const next = TABS[(index + delta + TABS.length) % TABS.length].key
    onChange(next)
    refs.current.get(next)?.focus()
  }

  return (
    <div role="tablist" aria-label={t('detail.tabs.label')} className="flex gap-1 border-b">
      {TABS.map(({ key, icon: Icon }) => {
        const selected = key === active
        return (
          <Button
            key={key}
            ref={(node) => {
              if (node !== null) refs.current.set(key, node)
            }}
            type="button"
            variant="ghost"
            role="tab"
            id={playbookTabId(key)}
            aria-selected={selected}
            aria-controls={playbookTabPanelId(key)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(key)}
            onKeyDown={handleKeyDown}
            className={cn(
              'relative h-auto gap-2 rounded-none px-4 py-3 text-sm font-medium hover:bg-transparent',
              selected ? 'text-foreground' : 'text-muted-foreground',
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {t(`detail.tabs.${key}`)}
            {selected ? (
              <span
                className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand"
                aria-hidden="true"
              />
            ) : null}
          </Button>
        )
      })}
    </div>
  )
}
