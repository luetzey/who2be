import { ChevronRight, Layers, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook, PlaybookRef, VersionStatus } from '@/api/types'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { splitTriggers } from '@/lib/triggers'

import { PlaybookTypeIcon } from './PlaybookTypeIcon'

// Design-Handoff „Playbooks-Redesign" §Row: eine Karte pro Playbook mit
// Typ-Icon, sanftem Status (Dot statt Badge), sichtbaren Triggern,
// aufklappbarem Composite-Footer und „Teil von"-Marker. Die ganze Karte ist
// per Stretched-Link klickbar (Name-Link mit after-Overlay); innenliegende
// Links/Buttons liegen via `relative` darueber.

// Maximal sichtbare Trigger-Chips pro Zeile — der Rest wird zu „+N".
const MAX_VISIBLE_TRIGGERS = 3

interface PlaybookRowProps {
  playbook: Playbook
  /** Workspace-Pfad-Builder der Page (useWorkspacePath). */
  wsPath: (path: string) => string
  /** Eltern-Composite (Rueckrichtung aus compose_children der Liste). */
  parent?: PlaybookRef
  /** Voll-Objekt eines Sub-Playbooks fuer Status/Version in der Kind-Zeile. */
  resolveChild?: (ref: PlaybookRef) => Playbook | undefined
}

function StatusDotLabel({
  status,
  version,
  dotClassName,
}: {
  status: VersionStatus | undefined
  version: number
  dotClassName?: string
}) {
  const { t } = useTranslation('common')
  if (status === undefined) return null
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span
        className={cn('inline-block size-2 rounded-full', dotClassName)}
        style={{ backgroundColor: `var(--status-${status})` }}
        aria-hidden="true"
      />
      {t(`status.${status}`)} · v{version}
    </span>
  )
}

export function PlaybookRow({ playbook, wsPath, parent, resolveChild }: PlaybookRowProps) {
  const { t } = useTranslation(['playbooks', 'data', 'common'])
  const [expanded, setExpanded] = useState(false)

  const triggers = splitTriggers(playbook.triggers)
  const visibleTriggers = triggers.slice(0, MAX_VISIBLE_TRIGGERS)
  const hiddenTriggerCount = triggers.length - visibleTriggers.length
  const composeChildren = playbook.compose_children ?? []

  return (
    <article
      // Umbruch unterhalb `md` (#573 Weiche 3): die Meta-Spalte unten ist
      // `shrink-0` und belegte mit zwei Tags gemessene 193,3px, wodurch die
      // `min-w-0`-Textspalte bei 320px auf 0px gerechnet wurde und Name,
      // Beschreibung und Kind-Links 102px aus ihrer Box liefen (gemessen am
      // gebauten CSS). `shrink-0` bleibt — es schuetzt die Badges; geloest
      // wird die einzeilige Anordnung. Ab `md` traegt die Meta-Spalte einen
      // Deckel (`md:max-w-40 lg:max-w-xs`), sonst drueckten 12 Tags sie auf
      // 1236px und die Textspalte wieder auf 0px (t_2a3882b4).
      className="relative flex flex-wrap gap-4 rounded-xl border bg-card p-4 shadow-card transition-[box-shadow,border-color] duration-[var(--duration-fast)] ease-spring hover:shadow-popover md:flex-nowrap"
      data-testid="playbook-row"
    >
      {/* Icon-Kachel auf die geteilte `EntityIcon`-Geometrie (md: 44px,
          rounded-xl) angeglichen, damit Persona-/Playbook-/Resource-Karten
          dieselbe Kachel teilen — der typ-spezifische Icon-Glyph bleibt.
          Unter `md` sitzt eine kleine Kachel (32 px) in der Titelzeile, damit
          die Textspalte die volle Kartenbreite nutzt (Mobil-Spec M3). */}
      <PlaybookTypeIcon type={playbook.type} className="hidden size-11 rounded-xl md:flex" />

      <div className="flex min-w-0 flex-1 basis-full flex-col gap-1 md:basis-0">
        <div className="flex flex-wrap items-center gap-2">
          <PlaybookTypeIcon type={playbook.type} className="size-8 rounded-md md:hidden" />
          {/* Unter `md` nimmt der Name den Rest der Kachel-Zeile, Status und
              Badges folgen darunter (sonst stuende die Kachel allein). */}
          <Link
            to={wsPath(`/playbooks/${playbook.id}`)}
            className="min-w-0 basis-[calc(100%-2.5rem)] rounded-sm text-sm font-semibold wrap-anywhere text-foreground after:absolute after:inset-0 after:rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none md:basis-auto"
          >
            {playbook.name}
          </Link>
          <StatusDotLabel status={playbook.current_status} version={playbook.current_version} />
          <LocaleBadge locale={playbook.locale} />
          {playbook.has_pending_draft === true ? (
            <span className="rounded-full bg-brand/10 px-2 py-0.5 text-xs font-semibold text-brand">
              {t('data:filter.pendingDraft')}
            </span>
          ) : null}
        </div>

        {playbook.content.description !== '' ? (
          // `wrap-anywhere`: lange URL bricht um, statt die Liste zu
          // verbreitern (Mobil-Spec M1). Vorschau statt Volltext (M3, W3):
          // 2 Zeilen unter `md`, 3 ab `md`, harte Kuerzung mit „…"; der
          // Stretched-Link des Namens fuehrt zur Detailseite mit Volltext.
          <p className="line-clamp-2 text-sm wrap-anywhere text-muted-foreground md:line-clamp-3">
            {playbook.content.description}
          </p>
        ) : null}

        {parent !== undefined ? (
          <Link
            to={wsPath(`/playbooks/${parent.id}`)}
            className="relative mt-1 inline-flex w-fit items-center gap-1.5 rounded-md bg-pill-catalog px-2 py-0.5 text-xs font-medium text-pill-catalog-fg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {/* size-3 bewusst (funktionaler Sonderfall §8): Icon in der
                kompakten text-xs-Pill, size-4 wuerde die Pille dominieren. */}
            <Layers className="size-3" aria-hidden="true" />
            {t('playbooks:list.partOf', { name: parent.name })}
          </Link>
        ) : null}

        {visibleTriggers.length > 0 ? (
          // Unter `md` ausgeblendet (Owner-Entscheidung W6=b): auf dem Telefon
          // zeigt die Zeile nur Name, Status und Beschreibung; die Trigger
          // stehen vollstaendig auf der Detailseite. `hidden` ist
          // `display:none` und nimmt die Liste auch aus dem Accessibility-Tree.
          <div
            className="mt-1 hidden flex-wrap items-center gap-2 md:flex"
            role="list"
            aria-label={t('playbooks:detail.triggerList')}
          >
            <Zap className="size-3.5 text-muted-foreground" aria-hidden="true" />
            {visibleTriggers.map((trigger) => (
              // `min-w-0 wrap-anywhere`: ein Trigger mit langer URL bricht in
              // der Pille um, statt die Liste zu verbreitern (Mobil-Spec M1/M12).
              // `max-w-[calc(100%-1.375rem)]`: die Pille passt neben den Blitz
              // (14 px + 8 px Luecke), statt ihn allein in einer Zeile stehen
              // zu lassen — gemessen 22 px pro Karte bei 320 px (Spec M3).
              <span
                key={trigger}
                role="listitem"
                className="max-w-[calc(100%-1.375rem)] min-w-0 rounded-md bg-muted px-2 py-0.5 text-xs wrap-anywhere text-foreground"
              >
                {trigger}
              </span>
            ))}
            {hiddenTriggerCount > 0 ? (
              <span
                className="text-xs text-muted-foreground"
                aria-label={t('playbooks:list.moreTriggers', { count: hiddenTriggerCount })}
              >
                +{hiddenTriggerCount}
              </span>
            ) : null}
          </div>
        ) : null}

        {composeChildren.length > 0 ? (
          <div className="relative mt-2 overflow-hidden rounded-lg bg-pill-catalog/40">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-expanded={expanded}
              onClick={() => setExpanded((open) => !open)}
              // Gemessen 32px hoch (`h-auto px-3 py-2` bei `text-xs`).
              // Issue #573 AK 5 fordert unterhalb `md` mindestens 40px;
              // `min-h-10` gewinnt dort gegen das `h-auto`, ab `md` faellt
              // die Zeile auf die alte Dichte zurueck.
              className="h-auto min-h-10 w-full justify-start gap-2 px-3 py-2 text-xs font-normal text-pill-catalog-fg hover:bg-pill-catalog/60 hover:text-pill-catalog-fg md:min-h-0"
            >
              <Layers className="size-3.5" aria-hidden="true" />
              <span className="font-semibold">
                {t('playbooks:list.subPlaybooksCount', { count: composeChildren.length })}
              </span>
              {/* Namensliste erst ab `md` (Mobil-Spec M6): bei 320 px
                  blieben ihr 17 px. Unter `md` nennt der Knopf die Anzahl. */}
              <span className="hidden min-w-24 truncate opacity-80 md:inline">
                {composeChildren.map((child) => child.name).join(' · ')}
              </span>
              <ChevronRight
                className={cn(
                  'ml-auto size-3.5 transition-transform duration-[var(--duration-fast)] ease-standard',
                  expanded && 'rotate-90',
                )}
                aria-hidden="true"
              />
            </Button>
            {expanded ? (
              <ol
                className="flex flex-col gap-1.5 px-2 pb-2"
                aria-label={t('playbooks:list.subPlaybooksListLabel')}
              >
                {composeChildren.map((child, index) => {
                  const detail = resolveChild?.(child)
                  return (
                    <li key={child.id}>
                      <Link
                        to={wsPath(`/playbooks/${child.id}`)}
                        className="flex min-h-10 items-center gap-2 rounded-lg border border-pill-catalog-fg/20 bg-card px-3 py-2 text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none md:min-h-0"
                      >
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-pill-catalog text-xs font-bold text-pill-catalog-fg">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm font-medium">
                          {child.name}
                        </span>
                        {detail !== undefined ? (
                          <StatusDotLabel
                            status={detail.current_status}
                            version={detail.current_version}
                          />
                        ) : null}
                        <ChevronRight
                          className="size-4 text-muted-foreground/60"
                          aria-hidden="true"
                        />
                      </Link>
                    </li>
                  )
                })}
              </ol>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Ab `md` gedeckelt, damit die Tags darin umbrechen statt die
          Textspalte zu verdraengen (`shrink-0` greift nur mit Deckel).
          Gemessen am gebauten CSS, 12 Tags: ohne Deckel 1236px breit, Text
          0px, scrollWidth 1593 bei 768. Mit 10rem bleiben der Textspalte bei
          768 (Karte 480px neben der Sidebar) 210px; 20rem ab `lg` gibt den
          Tags mehr Zeilenbreite (Text 306/546px bei 1024/1280). 20rem schon
          ab `md` liesse bei 768 nur 50px, 40% nur 192px.
          Unter `md` faellt die ganze Spalte weg (Owner-Entscheidung W6=b):
          Tags stehen auf der Detailseite, der Chevron ist dekorativ, und
          allein stehend kostete er eine leere Zeile samt `gap-4`. */}
      <div className="hidden shrink-0 flex-col items-end justify-between gap-2 md:flex md:max-w-40 lg:max-w-xs">
        {playbook.tags.length > 0 ? (
          // Ein einzelner Tag ohne Leerzeichen (TagStr: bis 100 Zeichen) bricht
          // nicht um und ragte nach links ueber die Textspalte — gemessen
          // 579/419/419px bei 768/1024/1280 (t_97e7a2be). Zwei Deckel noetig:
          // `max-w-full` am Wrapper, weil er als Item der `items-end`-Spalte
          // sonst so breit wird wie sein laengster Tag; `max-w-full min-w-0`
          // an der Badge. Der innere Span kuerzt mit „…" (`text-overflow`
          // greift nicht am `inline-flex`-Container selbst); der volle Name
          // steht im `title` und bleibt als Text im DOM.
          <div
            className="flex max-w-full flex-wrap justify-end gap-1"
            aria-label={t('common:fields.tags')}
          >
            {playbook.tags.map((tag) => (
              <Badge key={tag} variant="secondary" title={tag} className="max-w-full min-w-0">
                <span className="truncate">{tag}</span>
              </Badge>
            ))}
          </div>
        ) : null}
        <ChevronRight className="size-4 text-muted-foreground/60" aria-hidden="true" />
      </div>
    </article>
  )
}
