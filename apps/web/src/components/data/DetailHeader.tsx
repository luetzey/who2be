import { Activity, ArrowLeft, Ellipsis, type LucideIcon } from 'lucide-react'
import { useEffect, useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Api } from '@/api/client'
import type { UsageEntityType, UsageStats } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { EntityIcon, type EntityTone } from './EntityIcon'
import { ExpandableText } from './ExpandableText'
import { LocaleBadge } from './LocaleBadge'

// Geteilter Detail-Page-Header (Design-Handoff „Detail-Redesign"). Identischer
// Block in allen *DetailPage: optionaler Zurueck-Link, EntityIcon-Kachel, H1,
// Meta-Chips in fester Slot-Reihenfolge (Audit A8:
// Status · Version · Sprache · Slug · Tags), Beschreibung und ein rechter
// Action-Slot.
//
// Lebt unter `components/data/`, weil er die geteilte EntityIcon-Kachel + das
// Back-Link-Muster kapselt (ueber PageHeader hinaus).

interface DetailHeaderProps {
  icon: LucideIcon
  iconTone: EntityTone
  title: string
  /** Ziel des Zurueck-Links; ohne diesen Prop wird kein Link gerendert. */
  backHref?: string
  backLabel?: string
  /**
   * Audit A8: feste Meta-Slots in fester Reihenfolge
   * `Status · Version · Sprache · Slug · Tags` (PM-Entscheidung A). Die
   * Reihenfolge legt der Header fest, nicht die Seite — so kann sie nicht
   * mehr je Entitaetstyp auseinanderlaufen. Leere Slots entfallen.
   */
  status?: ReactNode
  /** Aktuelle Versionsnummer; der Header rendert daraus den Chip `v<n>`. */
  version?: number
  /** Inhaltssprache (ADR-0045); rendert `LocaleBadge`. */
  locale?: string
  /** Technischer Bezeichner (Slug, Tool-Alias), monospace mit Umbruch. */
  slug?: string
  /** Tag-Liste (z. B. `TagList`); der Tag-Stil bleibt Sache der Seite. */
  tags?: ReactNode
  /**
   * Freie Badges hinter den festen Slots — nur fuer unversionierte Seiten
   * (Feedback, Arbeitsbereich), die keine der Slot-Angaben haben.
   */
  badges?: ReactNode
  description?: string
  /** Rechter Action-Slot (z. B. „Duplizieren"). */
  actions?: ReactNode
  /**
   * Audit A13 / Issue #624 (Owner-Entscheidung C): unterhalb `md` liegen die
   * Aktionen hinter einem „Mehr"-Knopf neben dem Titel, damit Statusleiste
   * und erster Inhalt im ersten Viewport stehen. Nur fuer reine
   * Sekundaeraktionen (Feedback, Duplizieren, Export) setzen — traegt der
   * Slot die primaere Aktion der Seite (Agent: „Copy"), bleibt er offen.
   * Ab `md` wirkt der Prop nicht.
   */
  collapseActionsBelowMd?: boolean
  /**
   * Nutzung U4b: Element, dessen Nutzungszeile („n× in 30 Tagen · zuletzt
   * vor …“) unter der Beschreibung steht. Die Zeile laedt ihre Daten selbst;
   * ohne Prop entfaellt sie (und mit ihr jeder API-Aufruf).
   */
  usage?: { entityType: UsageEntityType; entityId: string }
  className?: string
}

// Fenster der Nutzungszeile — fest im Server (`uses_30d`, Konzept §5.2).
const USAGE_WINDOW_DAYS = 30

/**
 * „vor 2 Stunden“ in der Sprache der Oberflaeche. Gleiche Regel wie die
 * Kachel „Nutzung“ im Agent-Ueberblick: mindestens eine Minute, damit eine
 * Uhrabweichung nie „in 1 Minute“ zeigt.
 */
function formatAge(iso: string, language: string, now: number = Date.now()): string {
  const format = new Intl.RelativeTimeFormat(language, { numeric: 'auto' })
  const seconds = Math.min((new Date(iso).getTime() - now) / 1000, -60)
  if (Number.isNaN(seconds)) throw new Error('invalid date')
  const abs = Math.abs(seconds)
  if (abs < 3600) return format.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return format.format(Math.round(seconds / 3600), 'hour')
  return format.format(Math.round(seconds / 86400), 'day')
}

/** Zaehlbeginn `YYYY-MM-DD` als Datum der Oberflaeche („08.10.2026“). */
function formatCountingSince(day: string, language: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) throw new Error('invalid date')
  return new Intl.DateTimeFormat(language, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

type UsageState = { status: 'loading' } | { status: 'ok'; text: string } | { status: 'error' }

/**
 * Nutzungszeile (U4b). Gezaehlt wird nur, was an Agenten ausgeliefert wurde
 * (Owner Z1a). Der Zaehlbeginn steht immer dabei, sonst wirkt alles Aeltere
 * ungenutzt (Konzept §5.1). Laden: Platzhalter; Fehler: die Zeile entfaellt
 * still — sie ist Zusatzinformation, kein Seiteninhalt.
 */
function UsageLine({ entityType, entityId }: { entityType: UsageEntityType; entityId: string }) {
  const { t, i18n } = useTranslation('common')
  const language = i18n.language
  const api = useApi()
  const key = `${entityType}|${entityId}`
  const [result, setResult] = useState<{ api: Api; key: string; stats: UsageStats | null } | null>(
    null,
  )

  useEffect(() => {
    let alive = true
    // Ueber `Promise.resolve().then`: auch ein synchroner Wurf beim
    // Anfragebau landet im Fehlerzweig, nie auf der Seite.
    Promise.resolve()
      .then(() => api.getUsage(entityType, entityId))
      .then(
        (stats) => {
          if (alive) setResult({ api, key, stats })
        },
        () => {
          if (alive) setResult({ api, key, stats: null })
        },
      )
    return () => {
      alive = false
    }
  }, [api, key, entityType, entityId])

  let state: UsageState = { status: 'loading' }
  if (result !== null && result.api === api && result.key === key) {
    const stats = result.stats
    try {
      if (stats === null || typeof stats.uses_30d !== 'number') throw new Error('no usage')
      const since = formatCountingSince(stats.counting_since, language)
      state = {
        status: 'ok',
        text:
          stats.last_used_at === null
            ? t('usageLine.never', { date: since })
            : t('usageLine.used', {
                n: stats.uses_30d,
                days: USAGE_WINDOW_DAYS,
                age: formatAge(stats.last_used_at, language),
                date: since,
              }),
      }
    } catch {
      state = { status: 'error' }
    }
  }

  if (state.status === 'error') return null
  if (state.status === 'loading') {
    return (
      <Skeleton
        className="mt-1.5 h-4 w-56 max-w-full"
        aria-hidden="true"
        data-testid="detail-header-usage-loading"
      />
    )
  }
  return (
    <p
      className="mt-1.5 flex min-w-0 items-start gap-1.5 text-xs text-muted-foreground"
      data-testid="detail-header-usage"
    >
      <Activity className="mt-px size-3.5 shrink-0" aria-hidden="true" />
      <span className="min-w-0 wrap-anywhere">
        <span className="sr-only">{t('usageLine.label')}: </span>
        {state.text}
      </span>
    </p>
  )
}

export function DetailHeader({
  icon,
  iconTone,
  title,
  backHref,
  backLabel,
  status,
  version,
  locale,
  slug,
  tags,
  badges,
  description,
  actions,
  collapseActionsBelowMd = false,
  usage,
  className,
}: DetailHeaderProps) {
  const { t } = useTranslation('common')
  const [actionsOpen, setActionsOpen] = useState(false)
  const actionsId = useId()
  const collapsible = collapseActionsBelowMd && Boolean(actions)

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {backHref !== undefined ? (
        <Button asChild variant="ghost" size="sm" className="w-fit gap-2 text-muted-foreground">
          <Link to={backHref}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            {backLabel}
          </Link>
        </Button>
      ) : null}

      <header className="flex flex-wrap items-start justify-between gap-4">
        {/* `flex-1` (Basis 0) haelt den „Mehr"-Knopf auf dem Phone in der
            Titelzeile, statt ihn bei langem Titel in eine eigene Zeile zu
            umbrechen. Ab `md` gilt wieder `flex-initial` (Basis auto): sonst
            teilt sich der Titel die Zeile mit den offenen Aktionen und wird
            auf Tablet-Breite auf einen Buchstaben je Zeile gequetscht (CI,
            tablet-ipad-gen-7). Ohne Einklappen bleibt alles wie bisher. */}
        <div className={cn('flex min-w-0 gap-4', collapsible && 'flex-1 md:flex-initial')}>
          <EntityIcon icon={icon} tone={iconTone} size="lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="min-w-0 text-2xl font-semibold tracking-tight break-words">{title}</h1>
              {status}
              {version !== undefined ? (
                <Badge variant="secondary" data-testid="detail-header-version">
                  v{version}
                </Badge>
              ) : null}
              <LocaleBadge locale={locale} />
              {slug !== undefined && slug !== '' ? (
                // #564/#566: Slug ohne Trennstellen — `break-all` + Cap,
                // sonst 497 px breit bei 320 px Viewport.
                <Badge
                  variant="outline"
                  className="max-w-full font-mono text-xs break-all"
                  data-testid="detail-header-slug"
                >
                  {slug}
                </Badge>
              ) : null}
              {tags}
              {badges}
            </div>
            {description !== undefined && description !== '' ? (
              // Mobil-Spec M2: 3 Zeilen unter `md`, 6 ab `md`, „Mehr anzeigen"
              // klappt im Seitenfluss auf. Vorher belegte die Beschreibung bei
              // 320 px bis zu 1.600 px, die Tabs lagen erst nach 2,8
              // Bildschirmen. `ExpandableText` setzt `wrap-anywhere` selbst
              // (M1: nur `anywhere` senkt die min-content-Breite einer URL).
              <ExpandableText
                text={description}
                lines={3}
                mdLines={6}
                wrapperClassName="mt-1.5"
                className="text-sm text-muted-foreground"
                data-testid="detail-header-description"
              />
            ) : null}
            {usage !== undefined ? (
              <UsageLine entityType={usage.entityType} entityId={usage.entityId} />
            ) : null}
          </div>
        </div>
        {collapsible ? (
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0 md:hidden"
            aria-label={t('actions.more')}
            aria-expanded={actionsOpen}
            aria-controls={actionsId}
            data-testid="detail-header-more"
            onClick={() => setActionsOpen((open) => !open)}
          >
            <Ellipsis aria-hidden="true" />
          </Button>
        ) : null}
        {actions ? (
          <div
            id={actionsId}
            className={cn(
              'flex-wrap items-center gap-2',
              // Mobile-first (§4.4): Basis ist der Phone-Fall — eingeklappt
              // `hidden`, aufgeklappt eigene volle Zeile; `md:flex` schaltet
              // die Aktionen ab Tablet immer ein.
              collapsible ? cn(actionsOpen ? 'flex w-full' : 'hidden', 'md:flex md:w-auto') : 'flex',
            )}
          >
            {actions}
          </div>
        ) : null}
      </header>
    </div>
  )
}
