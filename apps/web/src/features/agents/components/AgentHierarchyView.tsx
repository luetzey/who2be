import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  FileText,
  GitBranch,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Agent, Persona, Playbook, SystemPromptTemplate, VersionStatus } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EntityIcon, type EntityTone } from '@/components/data/EntityIcon'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/utils'

/**
 * Playbook-Liste unter `md`: zuerst 4 im Seitenfluss (PM-Entscheidung zu P7:
 * die Tabs sollen bei 320 px nahe an einen Bildschirm rutschen, 8 Zeilen à
 * ≥ 40 px passten nicht), danach je 8 weitere (Mobil-Spec M9).
 */
const PLAYBOOK_INITIAL = 4
const PLAYBOOK_STEP = 8

interface AgentHierarchyViewProps {
  agent: Agent
  persona: Persona | null
  template: SystemPromptTemplate | null
  playbooks: Playbook[]
}

// Kleine Uppercase-Bereichsueberschrift (Design-Handoff „Detail-Redesign":
// „Zusammensetzung" / „System-Prompt" / „Persona").
// `as="span"` fuer den Schalter unter `md`: kein Block-Element im `<button>`.
function SectionLabel({ children, as: Tag = 'div' }: { children: ReactNode; as?: 'div' | 'span' }) {
  return (
    <Tag className="block text-xs font-semibold tracking-wide text-muted-foreground uppercase">
      {children}
    </Tag>
  )
}

// Prominente Verweiszeile fuer System-Prompt/Persona: Icon-Kachel + Caption
// (System-Prompt/Persona) + Name-Link + Versions-Badge + optionaler Status.
// Der `<Link>` umschliesst bewusst nur den Namen — der zugaengliche Name der
// Verknuepfung bleibt exakt der Entitaetsname (Caption/Badges liegen daneben).
function PrimaryRow({
  icon,
  tone,
  caption,
  name,
  href,
  version,
  status,
  testId,
}: {
  icon: LucideIcon
  tone: EntityTone
  caption: string
  name: string
  href: string
  version?: number
  status?: VersionStatus
  testId?: string
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-lg px-2 py-2 transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/50"
      data-testid={testId}
    >
      <EntityIcon icon={icon} tone={tone} size="sm" />
      <div className="min-w-0 flex-1">
        <SectionLabel>{caption}</SectionLabel>
        <div className="mt-0.5 flex flex-wrap items-center gap-2">
          <Link
            to={href}
            className="line-clamp-2 min-w-0 rounded-sm font-semibold wrap-anywhere text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {name}
          </Link>
          {version !== undefined ? (
            <Badge variant="outline" className="tabular-nums">
              v{version}
            </Badge>
          ) : null}
          {status !== undefined ? <StatusBadge status={status} /> : null}
        </div>
      </div>
      <ChevronRight className="size-4 flex-none text-muted-foreground/60" aria-hidden="true" />
    </div>
  )
}

// Kompakte Chip-/Link-Zeile fuer ein verknuepftes Playbook (Icon + Name + v).
//
// `min-h-10 md:min-h-0` an der Zeile: die Playbook-Zeilen sind die primaeren
// Navigationsziele der Karte. `px-2 py-1.5` bei `text-sm` ergibt gemessen
// 32 px Zeilenhoehe — das haelt den Floor aus
// `docs/frontend/design-language.md` §11 (>= 32 px, dort die einzige Quelle),
// erreicht aber nicht die 40 px, die AK 4 von #570 unterhalb `md` verlangt.
// `min-h-*` kollidiert in `tailwind-merge` nicht mit der Polsterung; ab `md`
// faellt die Zeile auf die Desktop-Dichte zurueck.
function PlaybookRow({
  name,
  href,
  version,
}: {
  name: string
  href: string
  version?: number
}) {
  // Mobil-Spec M6: Der Name bricht um statt bei kurzen Namen unnoetig mit „…“
  // zu enden; als Link darf er nach zwei Zeilen kuerzen (Spec M6.1).
  return (
    <Link
      to={href}
      data-testid="agent-hierarchy-playbook"
      className="flex min-h-10 items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none md:min-h-0"
    >
      <GitBranch className="size-4 flex-none text-pill-playbook-fg" aria-hidden="true" />
      <span className="line-clamp-2 min-w-0 flex-1 font-medium wrap-anywhere text-foreground">
        {name}
      </span>
      {version !== undefined ? (
        <span className="flex-none text-xs text-muted-foreground tabular-nums">v{version}</span>
      ) : null}
    </Link>
  )
}

/**
 * „Zusammensetzung"-Karte: System-Prompt, Persona und die verknuepften
 * Playbooks des Agenten als klickbare Verweiszeilen (Plan §"Agent-Detail-
 * Page", Design-Handoff „Detail-Redesign"). Reines Read — die Aktionen
 * (Kopieren/Duplizieren/Loeschen) sitzen im DetailHeader eine Ebene drueber.
 */
export function AgentHierarchyView({
  persona,
  template,
  playbooks,
}: AgentHierarchyViewProps) {
  const { t } = useTranslation('agents')
  const { t: tc } = useTranslation('common')
  const wsPath = useWorkspacePath()

  // PM-Zusatz zu Mobil-Spec P7 (Muster M9): Unter `md` stehen zuerst
  // `PLAYBOOK_INITIAL` Playbooks im Seitenfluss, jeder Klick auf
  // „N weitere anzeigen“ haengt die naechsten `PLAYBOOK_STEP` an. Vorher schob die Karte mit
  // 14 Playbooks (942 px bei 320) die Tabs des Agenten auf 2,6 Bildschirme.
  // Ab `md` alle, wie bisher. Die Anzahl ist Logik, deshalb `useIsMobile`
  // statt CSS.
  const isMobile = useIsMobile()
  const listRef = useRef<HTMLUListElement>(null)
  const pendingFocus = useRef<number | null>(null)
  const [shown, setShown] = useState(PLAYBOOK_INITIAL)
  const [announced, setAnnounced] = useState(false)
  const visiblePlaybooks = isMobile ? playbooks.slice(0, shown) : playbooks
  const nextCount = isMobile
    ? Math.min(PLAYBOOK_STEP, playbooks.length - visiblePlaybooks.length)
    : 0

  const showMore = () => {
    pendingFocus.current = visiblePlaybooks.length
    setShown((count) => count + PLAYBOOK_STEP)
    setAnnounced(true)
  }

  // Der Knopf verschwindet mit dem letzten Schritt; ohne Fokus-Sprung landete
  // der Tastatur-Fokus auf `body`. Deshalb: erster neuer Eintrag.
  useLayoutEffect(() => {
    const index = pendingFocus.current
    if (index === null) return
    pendingFocus.current = null
    listRef.current?.children.item(index)?.querySelector<HTMLElement>('a[href]')?.focus()
  }, [shown])

  // Designer-Delta t_42bff43b (Option a): Unter `md` startet die Karte bei
  // jedem Besuch zugeklappt; nur der Schalter mit Persona und Playbook-Zahl
  // steht vor den Tabs. Vorher lag die Tab-Oberkante bei 320 px auf
  // 1,80 Bildschirmen (Mobil-Spec M2: Ziel <= 1,2). Ab `md` gibt es keinen
  // Schalter, die Karte ist immer offen. `open` bleibt beim Wechsel der
  // Breite erhalten, ebenso `shown` beim Zu- und Aufklappen.
  const [open, setOpen] = useState(false)
  const collapsed = isMobile && !open
  const contentId = useId()
  const summary = [
    persona?.name ?? t('hierarchy.summaryNoPersona'),
    playbooks.length === 0
      ? t('hierarchy.summaryNoPlaybooks')
      : t('hierarchy.summaryPlaybooks', { count: playbooks.length }),
  ].join(t('hierarchy.summarySeparator'))

  return (
    <Card data-testid="agent-hierarchy">
      {isMobile ? (
        // Keine Animation (Spec §4): `transition-none` hebt die Farb-
        // Transition der Button-Basis auf; der Chevron wird getauscht, nicht
        // gedreht. Volle Breite, Text links, zwei Zeilen: dieselben
        // Overrides wie der Zeilen-Schalter in TestResultsPanel.
        <Button
          type="button"
          variant="ghost"
          aria-expanded={open}
          aria-controls={contentId}
          data-testid="agent-hierarchy-toggle"
          onClick={() => setOpen((value) => !value)}
          className="h-auto min-h-11 w-full justify-start gap-3 rounded-lg px-4 py-3 text-left font-normal whitespace-normal transition-none hover:bg-muted/50 hover:text-foreground"
        >
          <span className="flex min-w-0 flex-1 flex-col gap-1">
            <SectionLabel as="span">{t('hierarchy.title')}</SectionLabel>{' '}
            {/* Eine Zeile, auch aufgeklappt: so behaelt der Schalter beim
                Umschalten seine Hoehe und der Fokus springt optisch nicht
                (Spec §3.1). Der volle Persona-Name steht aufgeklappt direkt
                darunter in der Persona-Zeile (R-F1). */}
            <span
              className="truncate text-sm text-foreground"
              data-testid="agent-hierarchy-summary"
            >
              {summary}
            </span>
          </span>
          {open ? (
            <ChevronUp className="size-4 flex-none text-muted-foreground" aria-hidden="true" />
          ) : (
            <ChevronDown className="size-4 flex-none text-muted-foreground" aria-hidden="true" />
          )}
        </Button>
      ) : null}
      {/* `hidden` statt Nicht-Rendern: `aria-controls` zeigt immer auf ein
          vorhandenes Element, zugeklappt ist der Inhalt trotzdem weder im
          Tab-Fluss noch im A11y-Tree (Preflight: `[hidden]` ist
          `display: none !important`, `flex` ueberstimmt es nicht). */}
      <CardContent
        id={contentId}
        hidden={collapsed}
        className={cn('flex flex-col gap-4', isMobile ? 'pt-0' : 'pt-6')}
      >
        {isMobile ? null : <SectionLabel>{t('hierarchy.title')}</SectionLabel>}

        <div className="flex flex-col gap-2">
          {template !== null ? (
            <PrimaryRow
              icon={FileText}
              tone="date"
              caption={t('hierarchy.systemPrompt')}
              name={template.name}
              href={wsPath(`/system-prompts/${template.id}`)}
              version={template.current_version}
              status={template.current_status}
            />
          ) : (
            <div className="flex flex-col gap-1">
              <SectionLabel>{t('hierarchy.systemPrompt')}</SectionLabel>
              <p className="px-2 text-sm text-muted-foreground">{t('hierarchy.notLoaded')}</p>
            </div>
          )}

          {persona !== null ? (
            <PrimaryRow
              icon={Users}
              tone="persona"
              caption={t('hierarchy.persona')}
              name={persona.name}
              href={wsPath(`/personas/${persona.id}`)}
              version={persona.current_version}
              status={persona.current_status}
            />
          ) : (
            <div className="flex flex-col gap-1">
              <SectionLabel>{t('hierarchy.persona')}</SectionLabel>
              <p className="px-2 text-sm text-muted-foreground">{t('hierarchy.notLoaded')}</p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <SectionLabel>
            {playbooks.length === 0
              ? t('hierarchy.noPlaybooks')
              : t('hierarchy.playbooksLinked', { count: playbooks.length })}
          </SectionLabel>
          {playbooks.length > 0 ? (
            <ul
              ref={listRef}
              aria-label={t('hierarchy.playbooksLinked', { count: playbooks.length })}
              className="flex flex-col gap-1.5"
            >
              {visiblePlaybooks.map((playbook) => (
                <li key={playbook.id}>
                  <PlaybookRow
                    name={playbook.name}
                    href={wsPath(`/playbooks/${playbook.id}`)}
                    version={playbook.current_version}
                  />
                </li>
              ))}
            </ul>
          ) : null}
          {nextCount > 0 ? (
            <Button
              type="button"
              variant="link"
              className="min-h-11 self-start px-2"
              data-testid="agent-hierarchy-show-more"
              onClick={showMore}
            >
              {tc('actions.showMoreCount', { count: nextCount })}
            </Button>
          ) : null}
          <p className="sr-only" aria-live="polite">
            {announced
              ? tc('list.shownOfTotal', {
                  shown: visiblePlaybooks.length,
                  total: playbooks.length,
                })
              : ''}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
