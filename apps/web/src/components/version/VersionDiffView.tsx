import { Fragment, useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import type { VersionDiff, VersionDiffChange, VersionDiffOp } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { computeLineDiff, formatHunkHeader, type DiffLineKind } from '@/lib/lineDiff'
import { cn } from '@/lib/utils'

import type { StatusBadgeVariant } from './versionStatus'

interface VersionDiffViewProps {
  diff: VersionDiff
}

const OP_KEY: Record<VersionDiffOp, string> = {
  added: 'diff.added',
  removed: 'diff.removed',
  changed: 'diff.changed',
}

const OP_VARIANT: Record<VersionDiffOp, StatusBadgeVariant> = {
  added: 'default',
  removed: 'destructive',
  changed: 'secondary',
}

// Content-Pfade, die im Zeilen-Diff aufgehen: BlockNote-Bodies/-Blocklisten
// und strukturierte Sektionen (Modi/Skills), deren JSON-Badge-Rendering
// entfaellt, sobald `before_text`/`after_text` vorhanden sind (WP-C).
const CONTENT_PATH = /^(body$|blocks\[|content$|content\.|modes|skills|system_prompt$)/

const LINE_PREFIX: Record<DiffLineKind, string> = {
  context: ' ',
  added: '+',
  removed: '-',
}

const LINE_CLASS: Record<DiffLineKind, string> = {
  context: 'text-muted-foreground',
  added: 'bg-diff-added text-diff-added-fg',
  removed: 'bg-diff-removed text-diff-removed-fg',
}

// Rendert einen unbekannten JSON-Wert kompakt als Text. Strings unverändert,
// alles andere als (gekürztes) JSON — die Diff-Ansicht ist read-only.
function formatValue(value: unknown, emptyLabel: string): string {
  if (value === null || value === undefined) {
    return '—'
  }
  if (typeof value === 'string') {
    return value === '' ? emptyLabel : value
  }
  const serialized = JSON.stringify(value)
  return serialized.length > 200 ? `${serialized.slice(0, 200)}…` : serialized
}

/** Unified Zeilen-Diff im Git-Stil (+/−-Zeilen, Hunk-Trenner, Mono-Font). */
function UnifiedTextDiff({ beforeText, afterText }: { beforeText: string; afterText: string }) {
  const { t } = useTranslation('version')
  const hunks = useMemo(() => computeLineDiff(beforeText, afterText), [beforeText, afterText])
  if (hunks.length === 0) {
    return null
  }
  const srLabel: Partial<Record<DiffLineKind, string>> = {
    added: t('diff.lineAdded'),
    removed: t('diff.lineRemoved'),
  }
  // Mobil-Spec M4, Owner-Weiche W2=a: Zeilen brechen auf jeder Breite um,
  // es gibt keinen horizontalen Scroller. Verglichen wird Prosa, kein Code.
  // Vorher war jede Zeile `whitespace-pre` in `min-w-max`, und der Wrapper
  // scrollte 12.919 px bei 210 px Breite. Jede Zeile ist ein Grid: links die
  // feste Rinne mit `+`/`-`, rechts der Text. Umbrochene Folgezeilen stehen
  // dadurch unter dem Text und nicht unter dem Zeichen. `pre-wrap` haelt
  // Einrueckungen, `wrap-anywhere` bricht auch URLs ohne Trennstelle.
  return (
    <div className="rounded-md border border-border">
      <ul className="font-mono text-xs leading-5" aria-label={t('diff.textDiffLabel')}>
        {hunks.map((hunk) => (
          <Fragment key={formatHunkHeader(hunk)}>
            <li className="bg-muted/50 px-2 py-1 wrap-anywhere text-muted-foreground select-none">
              {formatHunkHeader(hunk)}
            </li>
            {hunk.lines.map((line) => (
              <li
                key={`${line.kind}-${line.beforeLine ?? 'x'}-${line.afterLine ?? 'x'}`}
                data-kind={line.kind}
                className={cn('grid grid-cols-[1.25rem_1fr] px-2', LINE_CLASS[line.kind])}
              >
                {/* Das Zeichen bleibt sichtbar: Farbe ist nicht das einzige Merkmal.
                    `whitespace-pre` haelt das Leerzeichen der Kontextzeile, damit
                    eine leere Zeile nicht auf 0 px zusammenfaellt. */}
                <span
                  aria-hidden="true"
                  data-testid="diff-gutter"
                  className="whitespace-pre select-none"
                >
                  {LINE_PREFIX[line.kind]}
                </span>
                <span
                  data-testid="diff-line-text"
                  className="min-w-0 wrap-anywhere whitespace-pre-wrap"
                >
                  {srLabel[line.kind] ? (
                    <span className="sr-only">{srLabel[line.kind]} </span>
                  ) : null}
                  {line.text}
                </span>
              </li>
            ))}
          </Fragment>
        ))}
      </ul>
    </div>
  )
}

/** Kompakte Feld-Badges (name, tags, triggers, …) — Bestandsverhalten. */
function FieldChangeList({ changes }: { changes: VersionDiffChange[] }) {
  const { t } = useTranslation('version')
  const emptyLabel = t('diff.empty')
  return (
    <ul className="flex flex-col gap-2" aria-label={t('diff.changesLabel')}>
      {changes.map((change) => (
        <li
          key={`${change.op}-${change.path}`}
          className="rounded-md border border-border bg-muted/30 p-2"
        >
          <div className="flex items-center gap-2">
            <Badge variant={OP_VARIANT[change.op]}>{t(OP_KEY[change.op])}</Badge>
            <code className="text-xs break-all text-foreground">{change.path}</code>
          </div>
          {change.op !== 'added' ? (
            <p className="mt-1 text-xs text-muted-foreground">
              <span className="font-medium">{t('diff.before')}</span>{' '}
              {formatValue(change.before, emptyLabel)}
            </p>
          ) : null}
          {change.op !== 'removed' ? (
            <p className="mt-1 text-xs text-muted-foreground">
              <span className="font-medium">{t('diff.after')}</span>{' '}
              {formatValue(change.after, emptyLabel)}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

/**
 * Read-only Darstellung eines serverseitig berechneten Versions-Diffs
 * (Track A). Mit `before_text`/`after_text` (WP-C) rendert der Content als
 * unified Zeilen-Diff im Git-Stil; Nicht-Content-Felder bleiben kompakte
 * Badges. Ohne die Texte (aeltere API) faellt die Ansicht auf den reinen
 * Feld-Diff zurueck.
 */
export function VersionDiffView({ diff }: VersionDiffViewProps) {
  const { t } = useTranslation('version')
  const againstLabel =
    diff.against_version !== null ? `v${diff.against_version}` : t('diff.noBaseline')

  if (diff.identical) {
    return (
      <p className="text-sm text-muted-foreground">
        {t('diff.identical', { version: diff.version, against: againstLabel })}
      </p>
    )
  }

  const hasText = typeof diff.before_text === 'string' && typeof diff.after_text === 'string'
  const fieldChanges = hasText
    ? diff.changes.filter((change) => !CONTENT_PATH.test(change.path))
    : diff.changes

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        {t('diff.comparing', { version: diff.version, against: againstLabel })}
      </p>
      {fieldChanges.length > 0 ? <FieldChangeList changes={fieldChanges} /> : null}
      {hasText ? (
        <UnifiedTextDiff beforeText={diff.before_text ?? ''} afterText={diff.after_text ?? ''} />
      ) : null}
    </div>
  )
}
