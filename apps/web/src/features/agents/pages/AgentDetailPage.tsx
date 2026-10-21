import { Bot } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'

import type { Agent, Persona, SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ReportCaseDialog } from '@/components/cases/ReportCaseForm'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { AgentMemoryCard } from '@/components/memory/AgentMemoryCard'
import { AgentTestCasesSection, TESTS_TAB } from '@/components/testcases/TestCasesTab'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useVersionDeepLink } from '@/components/version/versionDeepLink'
import {
  AgentEvolutionTab,
  EvolutionTabCount,
} from '@/components/evolution/AgentEvolutionTab'
import { useInboxCounts } from '@/hooks/useInboxCounts'

import { AgentConnectorSection } from '../components/AgentConnectorSection'
import { AgentEditorForm } from '../components/AgentEditorForm'
import { AgentHierarchyView } from '../components/AgentHierarchyView'
import { AgentOverview } from '../components/AgentOverview'
import { AgentTokensSection } from '../components/AgentTokensSection'
import { CopyPromptButton } from '../components/CopyPromptButton'
import { DeleteAgentButton } from '../components/DeleteAgentButton'
import { DuplicateAgentButton } from '../components/DuplicateAgentButton'
import { useAgent } from '../hooks/useAgent'
import { useAgentForm } from '../hooks/useAgentForm'

// Tabs der Agent-Seite (Navigation-Spec §3.1). Die URL (`?tab=`) ist die
// einzige Quelle fuer den aktiven Tab; der Ueberblick ist Default und steht
// ohne Parameter in der URL.
const AGENT_TABS = ['overview', 'evolution', 'memory', TESTS_TAB, 'settings'] as const
type AgentTab = (typeof AGENT_TABS)[number]

// Alte Anker der Stapel-Seite → Tab (Spec §3.1). `#memory` und `#delegations`
// bleiben als Hash stehen: die Gedaechtnis-Karte hebt sich darauf hervor, die
// Delegation-Karte (Orchestrator-Spec 2.1) wird im Ueberblick angesprungen.
const ANCHOR_TABS: Record<string, { tab: AgentTab; keepHash: boolean }> = {
  '#tests': { tab: TESTS_TAB, keepHash: false },
  '#memory': { tab: 'memory', keepHash: true },
  // Alter Abschnitt „Gespraeche“ (E5-Delta) → Tab „Weiterentwicklung“ (Neuschnitt §2).
  '#sessions': { tab: 'evolution', keepHash: false },
  '#delegations': { tab: 'overview', keepHash: true },
}

/** Schreibt einen alten Anker einmalig in `?tab=` um (History ersetzt). */
function useLegacyAnchorRedirect() {
  const { hash, search } = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    const target = ANCHOR_TABS[hash]
    if (target === undefined) return
    const params = new URLSearchParams(search)
    // Ein expliziter `?tab=` gewinnt; der Anker waehlt nur, wenn keiner da ist.
    if (!params.has('tab') && target.tab !== 'overview') params.set('tab', target.tab)
    const nextSearch = params.toString() === '' ? '' : `?${params.toString()}`
    const nextHash = target.keepHash ? hash : ''
    if (nextSearch === search && nextHash === hash) return
    void navigate({ search: nextSearch, hash: nextHash }, { replace: true })
  }, [hash, search, navigate])
}

// Agent-Status als bordered Capsule fuer den Detail-Header (Design-Handoff
// „Detail-Redesign"). Unvollstaendig hat Vorrang; Farbe aus `--status-*`,
// nie als alleiniges Signal (Punkt + Label, design-language §11).
function AgentStatusBadge({ agent }: { agent: Agent }) {
  const { t } = useTranslation('agents')
  const { token, label } = !agent.activatable
    ? { token: 'draft', label: t('status.incomplete') }
    : agent.status === 'enabled'
      ? { token: 'active', label: t('status.enabled') }
      : { token: 'inactive', label: t('status.disabled') }

  return (
    <span className="inline-flex items-center gap-2 rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground">
      <span
        className="inline-block size-2 rounded-full"
        style={{ backgroundColor: `var(--status-${token})` }}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}

export function AgentDetailPage() {
  const { t } = useTranslation('agents')
  const { id } = useParams<{ id: string }>()
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const { agent, persona, template, playbooks, loading, error, reload } = useAgent(id)
  const { form, onSubmit, saveError } = useAgentForm(agent, reload)
  const [personas, setPersonas] = useState<Persona[]>([])
  const [templates, setTemplates] = useState<SystemPromptTemplate[]>([])

  // Gedaechtnis sieht erst `editor` (ADR-0053 6.4.1) — fuer viewer entfaellt
  // der Tab ganz, ein `?tab=memory` faellt auf den Ueberblick zurueck.
  const canSeeMemory = role !== null && role !== 'viewer'
  const tabs = useMemo(
    () => AGENT_TABS.filter((value) => value !== 'memory' || canSeeMemory),
    [canSeeMemory],
  )
  // Tab-Zaehler „Weiterentwicklung“ (Neuschnitt §3.1): dieselbe Quelle wie die
  // Aufgaben-Zeile im Ueberblick; der Tab bekommt die Zahl fuer ④ mit.
  const inbox = useInboxCounts(id)
  const isEditor = role === 'editor' || role === 'admin'
  const { tab, setTab } = useVersionDeepLink(tabs, 'overview')
  useLegacyAnchorRedirect()

  useEffect(() => {
    void Promise.all([api.listPersonas(), api.listSystemPromptTemplates()]).then(
      ([loadedPersonas, loadedTemplates]) => {
        setPersonas(loadedPersonas)
        setTemplates(loadedTemplates)
      },
    )
  }, [api])

  if (id === undefined) {
    return <Navigate to={wsPath('/agents')} replace />
  }

  return (
    <Container>
      <DataView loading={loading && agent === null} error={error}>
        {agent !== null ? (
          (() => {
            const locked = agent.is_managed === true
            return (
              <Stack gap="lg">
                <DetailHeader
                  icon={Bot}
                  iconTone="catalog"
                  backHref={wsPath('/agents')}
                  backLabel={t('detail.back')}
                  title={agent.name}
                  badges={<AgentStatusBadge agent={agent} />}
                  description={agent.description || undefined}
                  actions={
                    <>
                      <CopyPromptButton
                        agentId={agent.id}
                        disabled={agent.status !== 'enabled'}
                      />
                      <DuplicateAgentButton agent={agent} />
                      {/* Lernschleife D6a (Delta-Spec S6): ab viewer, Agent fest. */}
                      <ReportCaseDialog agent={{ id: agent.id, name: agent.name }} />
                      {locked ? null : <DeleteAgentButton agent={agent} />}
                    </>
                  }
                />
                {locked ? <ManagedNotice showDuplicateHint /> : null}

                <Tabs value={tab} onValueChange={setTab}>
                  <TabsList aria-label={t('detail.pageTabsAria')}>
                    {tabs.map((value) => (
                      <TabsTrigger key={value} value={value}>
                        {t(`detail.pageTabs.${value}`)}
                        {/* Zaehler nur fuer editor (Neuschnitt §3.7: viewer ohne). */}
                        {value === 'evolution' && isEditor ? (
                          <EvolutionTabCount counts={inbox.counts} />
                        ) : null}
                      </TabsTrigger>
                    ))}
                  </TabsList>

                  <TabsContent value="overview">
                    {/* Navigation W2-b (Spec §3.2): Aufgaben-Zeile, Kacheln,
                        Zusammensetzung und Arbeitsbereiche. */}
                    <AgentOverview
                      agent={agent}
                      composition={
                        <AgentHierarchyView
                          agent={agent}
                          persona={persona}
                          template={template}
                          playbooks={playbooks}
                        />
                      }
                    />
                  </TabsContent>

                  <TabsContent value="evolution">
                    {/* W3 Option B (Neuschnitt §3, E5g); Verlauf folgt mit E5k. */}
                    <AgentEvolutionTab agent={{ id: agent.id, name: agent.name }} inbox={inbox} />
                  </TabsContent>

                  <TabsContent value="memory">
                    <AgentMemoryCard agent={agent} framed={false} />
                  </TabsContent>

                  <TabsContent value={TESTS_TAB}>
                    <AgentTestCasesSection agentId={agent.id} agentName={agent.name} />
                  </TabsContent>

                  <TabsContent value="settings">
                    <AgentEditorForm
                      form={form}
                      onSubmit={onSubmit}
                      saveError={saveError}
                      personas={personas}
                      templates={templates}
                      agent={agent}
                      locked={locked}
                      connectionSlot={
                        <Stack gap="lg">
                          <AgentConnectorSection agentId={agent.id} agentName={agent.name} />
                          <AgentTokensSection agentId={agent.id} />
                        </Stack>
                      }
                    />
                  </TabsContent>
                </Tabs>
              </Stack>
            )
          })()
        ) : null}
      </DataView>
    </Container>
  )
}
