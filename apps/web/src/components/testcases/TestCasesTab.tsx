import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import type { VersionedEntityType } from '@/api/types'
import { useAgents } from '@/hooks/useAgents'

import { TestCaseList } from './TestCaseList'

// Einstiege in die Prueffall-Liste (Lernschleife B4b, Spec S10 / §2.2):
// Tab „Prüffälle" (`?tab=tests`) auf Persona-, Playbook-, System-Prompt- und
// Agent-Detail (Agent: Navigation-Spec §3.1; der alte Anker `#tests` leitet
// dort auf `?tab=tests` um).

/** Wert des Tab-Parameters `?tab=` fuer die Prueffaelle (Spec §2.2). */
export const TESTS_TAB = 'tests'

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
  // Ueberschriften-Hierarchie lueckenlos, wie der Tab am Agenten.
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
 * Inhalt des Tabs „Prüffälle" auf der Agent-Detailseite (Navigation-Spec
 * §3.1): die an den Agenten gebundenen Prueffaelle. Nur gemountet, solange
 * der Tab aktiv ist — ohne Bedarf also keine Requests.
 */
export function AgentTestCasesSection({ agentId, agentName }: AgentTestCasesSectionProps) {
  const { t } = useTranslation('learning')
  const { agents } = useAgents()
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} data-testid="agent-test-cases" className="min-w-0">
      <h2 id={headingId} className="sr-only">
        {t('testCases.title')}
      </h2>
      <TestCaseList agentId={agentId} agents={agents} subjectLabel={agentName} />
    </section>
  )
}
