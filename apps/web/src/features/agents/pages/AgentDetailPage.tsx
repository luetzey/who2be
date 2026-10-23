import { Bot } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useVersionDeepLink } from '@/components/version/versionDeepLink'
import {
  AgentEvolutionTab,
  EvolutionTabCount,
} from '@/components/evolution/AgentEvolutionTab'
import { useInboxCounts } from '@/hooks/useInboxCounts'
import { AGENT_CONNECT_HASH } from '@/lib/installLinks'
import { notify } from '@/lib/feedback'

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
  // Startliste „Builder verbinden“ (UX-Audit B1): Karte „Verbindung“ im Ueberblick.
  [AGENT_CONNECT_HASH]: { tab: 'overview', keepHash: true },
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

/**
 * Sprung `#connect` (Startliste „Builder verbinden“, UX-Audit B1+B3): sobald
 * die Karte „Verbindung“ steht, an den oberen Rand scrollen und den Fokus auf
 * ihre Ueberschrift setzen — einmal je Navigation (`location.key`), nicht bei
 * jedem Tab-Wechsel zurueck in den Ueberblick.
 */
function useConnectJump(ready: boolean) {
  const { hash, key } = useLocation()
  const ref = useRef<HTMLDivElement>(null)
  const handled = useRef<string | null>(null)
  useEffect(() => {
    if (!ready || hash !== AGENT_CONNECT_HASH || handled.current === key) return
    const target = ref.current
    if (target === null) return
    handled.current = key
    target.scrollIntoView?.({ block: 'start' })
    const heading = target.querySelector<HTMLElement>('h2')
    if (heading !== null) {
      // Ueberschrift nur programmatisch fokussierbar, nicht in der Tab-Folge.
      heading.tabIndex = -1
      heading.focus({ preventScroll: true })
    }
  }, [ready, hash, key])
  return ref
}

/**
 * Frisch angelegter Agent (UX-Audit B4): die Liste springt mit
 * `state.focusPersona` direkt in Einstellungen › Konfiguration, hier wird der
 * Fokus auf „Persona“ gesetzt — einmal je Navigation (`location.key`).
 */
function useFocusPersonaOnCreate(ready: boolean, focus: () => void) {
  const { state, key } = useLocation()
  const handled = useRef<string | null>(null)
  const wanted =
    typeof state === 'object' && state !== null && (state as { focusPersona?: unknown }).focusPersona === true
  useEffect(() => {
    if (!ready || !wanted || handled.current === key) return
    // Erst im naechsten Task: `form.reset()` (useAgentForm) leert im selben
    // Commit die Feld-Refs von react-hook-form, sie stehen erst nach dem
    // folgenden Render wieder bereit. `handled` erst im Timer setzen, sonst
    // verliert ein StrictMode-Doppellauf (Cleanup + Re-Run) den Fokus.
    const timer = window.setTimeout(() => {
      handled.current = key
      focus()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [ready, wanted, key, focus])
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
  const navigate = useNavigate()
  const role = useCurrentWorkspaceRole()
  const isEditor = role === 'editor' || role === 'admin'
  const { agent, persona, template, playbooks, loading, error, reload } = useAgent(id)
  // UX-Audit B4 / Owner W-D: nach dem Speichern eines vollstaendigen, aber
  // inaktiven Agenten nachfragen statt automatisch zu aktivieren. Den Status
  // aendern darf wie im Formular nur editor/admin, verwaltete Agenten nie.
  const [activateOpen, setActivateOpen] = useState(false)
  const [activating, setActivating] = useState(false)
  const onSaved = useCallback(
    (saved: Agent) => {
      reload()
      if (isEditor && saved.is_managed !== true && saved.activatable && saved.status === 'disabled') {
        setActivateOpen(true)
      }
    },
    [reload, isEditor],
  )
  const { form, onSubmit, saveError } = useAgentForm(agent, onSaved)
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
  const { tab, setTab } = useVersionDeepLink(tabs, 'overview')
  useLegacyAnchorRedirect()
  const connectRef = useConnectJump(agent !== null && tab === 'overview')
  const focusPersona = useCallback(() => form.setFocus('persona_id'), [form])
  useFocusPersonaOnCreate(agent !== null && tab === 'settings', focusPersona)

  // „Aktivieren“ nutzt den vorhandenen Status-Weg (PUT nur mit `status`),
  // danach Ueberblick mit Sprung auf die Karte „Verbindung“ (`#connect`).
  const activate = async () => {
    if (agent === null) return
    setActivating(true)
    try {
      await api.updateAgent(agent.id, { status: 'enabled' })
      notify.success(t('activatePrompt.success'))
      setActivateOpen(false)
      reload()
      void navigate({ search: '', hash: AGENT_CONNECT_HASH })
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('agents:toast.unknownError'))
    } finally {
      setActivating(false)
    }
  }

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
                  // UX-Audit B3: unter `md` liegen Kopieren, Duplizieren,
                  // Rueckmeldung und Loeschen hinter „…“, damit die Karte
                  // „Verbindung“ (die Brand-Aktion der Seite) frueher kommt.
                  collapseActionsBelowMd
                  actions={
                    <>
                      <CopyPromptButton
                        agentId={agent.id}
                        disabled={agent.status !== 'enabled'}
                        // Hoechstens eine Brand-Aktion je Seite (Designsprache
                        // §2.2): die traegt jetzt „Verbindung“ im Ueberblick.
                        variant="outline"
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
                    {/* Reihenfolge im Ueberblick (Onboarding-Spec §10.1): Kopf →
                        Verbindung → Briefing (Editor-Spec §6.1, folgt) →
                        Kennzahlen. */}
                    <Stack gap="lg">
                      {/* Sprungziel `#connect`; `scroll-mt` laesst Luft zum Rand. */}
                      <div ref={connectRef} className="scroll-mt-4">
                        <AgentConnectorSection agent={agent} />
                      </div>
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
                    </Stack>
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
                      connectionSlot={<AgentTokensSection agentId={agent.id} />}
                    />
                  </TabsContent>
                </Tabs>

                <Dialog open={activateOpen} onOpenChange={setActivateOpen}>
                  <DialogContent data-testid="agent-activate-prompt">
                    <DialogHeader>
                      <DialogTitle>{t('activatePrompt.title')}</DialogTitle>
                      <DialogDescription>{t('activatePrompt.body')}</DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline">{t('activatePrompt.later')}</Button>
                      </DialogClose>
                      <Button onClick={() => void activate()} disabled={activating}>
                        {t('activatePrompt.confirm')}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </Stack>
            )
          })()
        ) : null}
      </DataView>
    </Container>
  )
}
