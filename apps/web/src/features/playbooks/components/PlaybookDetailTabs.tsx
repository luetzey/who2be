import { ClipboardCheck, GitBranch, Layers, Pencil, type LucideIcon } from 'lucide-react'
import { useRef, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { TESTS_TAB } from '@/components/testcases/TestCasesTab'
import { cn } from '@/lib/utils'

// Design-Handoff „Playbooks-Redesign" §Detail: Tab-Leiste Bearbeiten /
// Beziehungen / Prüffälle / Versionen (Prüffälle: Lernschleife B4b, Spec
// S10 — ohne Zaehler, §2.3; auf allen Element-Detailseiten direkt vor
// „Versionen"). Aktiver Tab traegt einen 2px-Brand-Unterstrich.
// ARIA-Tabs-Pattern inkl. Pfeiltasten-Navigation (roving tabindex).

export type PlaybookDetailTab = 'edit' | 'relations' | 'versions' | typeof TESTS_TAB

const TABS: { key: PlaybookDetailTab; icon: LucideIcon; label: string }[] = [
  { key: 'edit', icon: Pencil, label: 'detail.tabs.edit' },
  { key: 'relations', icon: Layers, label: 'detail.tabs.relations' },
  { key: TESTS_TAB, icon: ClipboardCheck, label: 'learning:testCases.title' },
  { key: 'versions', icon: GitBranch, label: 'detail.tabs.versions' },
]

/**
 * Audit A8: einzige Quelle der Tab-Reihenfolge
 * (`Bearbeiten · Beziehungen · Prüffälle · Versionen`). Die Seite nutzt sie
 * fuer den Deep-Link-Hook, statt eine zweite Liste zu fuehren.
 */
export const PLAYBOOK_DETAIL_TABS: readonly PlaybookDetailTab[] = TABS.map((tab) => tab.key)

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
    // `flex-wrap`: die drei Tabs messen mit den deutschen Labels zusammen
    // 379,8px und laufen auf 320px aus dem 288px-Innenraum (gemessen am
    // gebauten CSS: bodyScroll 84px). Umbruch statt Scroll-Container ist die
    // Festlegung von #573 (Vorentscheidung 1); design-language.md §4.4
    // Checklistenpunkt 1 verlangt lediglich, dass bei 320px kein
    // horizontaler Body-Scroll entsteht, und nennt kein Mittel.
    <div
      role="tablist"
      aria-label={t('detail.tabs.label')}
      className="flex flex-wrap gap-1 border-b"
    >
      {TABS.map(({ key, icon: Icon, label }) => {
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
            {t(label)}
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
