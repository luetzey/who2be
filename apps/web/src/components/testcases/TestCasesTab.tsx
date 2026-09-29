import { ChevronRight } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'

import type { VersionedEntityType } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAgents } from '@/hooks/useAgents'
import { cn } from '@/lib/utils'

import { TestCaseList } from './TestCaseList'

// Einstiege in die Prueffall-Liste (Lernschleife B4b, Spec S10 / §2.2):
// Tab „Prüffälle" (`?tab=tests`) auf Persona-, Playbook- und System-Prompt-
// Detail, am Agenten eine aufklappbare Sektion mit Anker `#tests`. Die
// Agent-Detailseite hat (noch) keine Tabs — der Umbau aus Spec §2.3 ist ein
// eigenes Paket; bis dahin oeffnet auch `?tab=tests` die Sektion, damit der
// Link der Spec-Route schon heute traegt.

/** Wert des Tab-Parameters `?tab=` fuer die Prueffaelle (Spec §2.2). */
export const TESTS_TAB = 'tests'

/** Anker der Prueffall-Sektion auf der Agent-Detailseite. */
export const TESTS_ANCHOR = 'tests'

type ElementType = Extract<VersionedEntityType, 'persona' | 'playbook' | 'system_prompt_template'>

interface EntityTestCasesProps {
  type: ElementType
  id: string
  /** Anzeigename des Elements, fuer den Kopf „Prüffälle · <Typ> „<Name>"". */
  name: string
}

/**
 * Inhalt des Tabs „Prüffälle" an einem Element: die direkt an diesem Element
 * gebundenen Prueffaelle, gruppiert nach Agent (P4 = a — „ueber Agenten
 * wirkend" folgt, sobald die Versions-UUID lesbar ist). Die Agenten laedt der
 * Tab selbst; nur gemountet, solange der Tab aktiv ist.
 */
export function EntityTestCases({ type, id, name }: EntityTestCasesProps) {
  const { t, i18n } = useTranslation('learning')
  const { agents } = useAgents()
  const headingId = useId()
  // Anfuehrungszeichen je Sprache (DE „…“, EN “…”) wie in den uebrigen
  // Texten. Ein eigener i18n-Schluessel waere sauberer, sprengt aber den
  // Acht-Dateien-Deckel dieses Pakets (de.json + en.json).
  const [open, close] = i18n.resolvedLanguage === 'de' ? ['„', '“'] : ['“', '”']
  const subjectLabel = `${t(`testCases.entityType.${type}`)} ${open}${name}${close}`
  // Die Liste bringt ihr eigenes h3 mit (Kopf mit Anlage-Aktion). Die
  // Detailseite hat darueber nur das h1 — das unsichtbare h2 haelt die
  // Ueberschriften-Hierarchie lueckenlos, wie die Sektion am Agenten.
  return (
    <section aria-labelledby={headingId} className="min-w-0">
      <h2 id={headingId} className="sr-only">
        {t('testCases.title')}
      </h2>
      <TestCaseList entity={{ type, id }} agents={agents} subjectLabel={subjectLabel} />
    </section>
  )
}

interface AgentTestCasesSectionProps {
  agentId: string
  agentName: string
}

/**
 * Prueffall-Sektion auf der Agent-Detailseite. Zugeklappt, damit die Seite
 * ohne Bedarf keine zusaetzlichen Requests absetzt; `#tests` bzw.
 * `?tab=tests` klappt sie auf und scrollt hin.
 */
export function AgentTestCasesSection({ agentId, agentName }: AgentTestCasesSectionProps) {
  const { t } = useTranslation('learning')
  const { hash, search } = useLocation()
  const deepLinked =
    hash === `#${TESTS_ANCHOR}` || new URLSearchParams(search).get('tab') === TESTS_TAB
  // Offen, solange der Deep-Link es verlangt — bis der Nutzer selbst klickt.
  const [toggled, setToggled] = useState<boolean | null>(null)
  const open = toggled ?? deepLinked
  const sectionRef = useRef<HTMLDivElement>(null)
  const contentId = useId()

  useEffect(() => {
    if (!deepLinked) return
    sectionRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }, [deepLinked])

  return (
    <Card id={TESTS_ANCHOR} ref={sectionRef} data-testid="agent-test-cases" className="scroll-mt-6">
      <CardHeader>
        <CardTitle>
          <Button
            type="button"
            variant="ghost"
            aria-expanded={open}
            aria-controls={open ? contentId : undefined}
            onClick={() => setToggled(!open)}
            className="-mx-2 h-auto min-h-10 justify-start gap-2 px-2 text-lg font-semibold md:min-h-0"
          >
            <ChevronRight
              className={cn(
                'size-4 transition-transform duration-[var(--duration-fast)] ease-standard',
                open && 'rotate-90',
              )}
              aria-hidden="true"
            />
            {t('testCases.title')}
          </Button>
        </CardTitle>
      </CardHeader>
      {open ? (
        <CardContent id={contentId}>
          <AgentTestCases agentId={agentId} agentName={agentName} />
        </CardContent>
      ) : null}
    </Card>
  )
}

function AgentTestCases({ agentId, agentName }: AgentTestCasesSectionProps) {
  const { agents } = useAgents()
  return <TestCaseList agentId={agentId} agents={agents} subjectLabel={agentName} />
}
