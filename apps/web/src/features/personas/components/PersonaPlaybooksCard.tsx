import { Layers, Plus, Share2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { PersonaContent, Playbook, PlaybookRef } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EntityCard } from '@/components/data/EntityCard'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'
import { splitTriggers } from '@/lib/triggers'

import { PlaybookLinkItem, PlaybookReferencedBadge } from './PlaybookLinkItem'

/**
 * Sammelt alle Playbook-IDs, die im Persona-INHALT tatsaechlich referenziert
 * werden — zwei ehrliche Signale (keine fingierte managed-Herkunft):
 *
 * 1. `content.modes[].playbook_id` — ein Modus, der an ein Playbook gebunden
 *    ist (strukturiert, zuverlaessig).
 * 2. Inline-Placeholder-Pills der Art `playbook` im Profil-Body
 *    (`content.content.blocks`) — BlockNote-Inline-Content mit
 *    `{ type: 'placeholder', props: { kind: 'playbook', target_id } }`.
 *
 * Der Walk ist defensiv gegen die offene `ResourceBlock`-Form getypt (Blocks
 * tragen `content`-Inline-Arrays und `children`-Bloecke); unbekannte Knoten
 * werden ignoriert statt zu werfen.
 */
function collectPlaybookRefsFromNodes(nodes: unknown, into: Set<string>): void {
  if (!Array.isArray(nodes)) return
  for (const node of nodes) {
    if (node === null || typeof node !== 'object') continue
    const record = node as Record<string, unknown>
    if (record.type === 'placeholder' && record.props !== null && typeof record.props === 'object') {
      const props = record.props as Record<string, unknown>
      if (props.kind === 'playbook' && typeof props.target_id === 'string' && props.target_id !== '') {
        into.add(props.target_id)
      }
    }
    // Block-Level: Inline-Content und verschachtelte Kind-Bloecke rekursiv.
    if ('content' in record) collectPlaybookRefsFromNodes(record.content, into)
    if ('children' in record) collectPlaybookRefsFromNodes(record.children, into)
  }
}

function collectReferencedPlaybookIds(content: PersonaContent | undefined): Set<string> {
  const ids = new Set<string>()
  if (content === undefined) return ids
  for (const mode of content.modes ?? []) {
    if (typeof mode.playbook_id === 'string' && mode.playbook_id !== '') {
      ids.add(mode.playbook_id)
    }
  }
  collectPlaybookRefsFromNodes(content.content?.blocks, ids)
  return ids
}

interface PersonaPlaybooksCardProps {
  personaId: string
  /** Editor-/Admin-Rechte und nicht managed — sonst reiner Anzeige-Modus. */
  canEdit: boolean
}

/**
 * Aufklappbare Sub-Playbook-Liste eines Composite-Playbooks. Spiegelt das
 * Sub-Resource-/Sub-Playbook-Muster (PlaybookRow): nummerierte, verlinkte
 * Kind-Zeilen mit Status/Version, sofern das Voll-Objekt aufloesbar ist.
 */
function SubPlaybookList({
  items,
  wsPath,
  resolveChild,
  label,
}: {
  items: PlaybookRef[]
  wsPath: (path: string) => string
  resolveChild: (ref: PlaybookRef) => Playbook | undefined
  label: string
}) {
  return (
    <ol className="flex flex-col gap-1.5" aria-label={label}>
      {items.map((child, index) => {
        const detail = resolveChild(child)
        return (
          <li key={child.id}>
            <Link
              to={wsPath(`/playbooks/${child.id}`)}
              className="flex items-center gap-3 rounded-lg border border-pill-catalog-fg/20 bg-card px-3 py-2 text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-pill-catalog text-xs font-bold text-pill-catalog-fg">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{child.name}</span>
              {detail !== undefined ? (
                <StatusBadge status={detail.current_status} />
              ) : null}
            </Link>
          </li>
        )
      })}
    </ol>
  )
}

/**
 * Playbooks-Sektion der Persona-Detailseite (WP-E). Default ist ein
 * navigierbarer Anzeige-Modus (Karten-Zeilen mit Status/Meta und einem
 * aufklappbaren Composite-Bereich fuer Sub-Playbooks). Hinter
 * „Verknüpfungen bearbeiten“ liegt (Mockup `pbEditing`) ein Zwei-Sektionen-
 * Editor: „Verknüpft“ (aktuelle Links mit „Entfernen“) und „Playbook
 * hinzufügen“ (Suchfeld + verfuegbare Playbooks mit „Verknüpfen“). Beide
 * Aktionen sind `toggle(id)`; Aenderungen bleiben lokal bis „Speichern“,
 * Abbrechen verwirft sie.
 *
 * Bewusst NICHT nachgebaut: der Mockup-Marker „Aus Editor-Text” (managed, nicht
 * entfernbar). Persona→Playbook-Links haben (anders als Sub-Resources) keine
 * managed-/Editor-Herkunft im Datenmodell — ein Lock haette keine Quelle und
 * wird nicht fingiert. Stattdessen ein EHRLICHER, nicht sperrender Hinweis:
 * `referencedIds` markiert Playbooks, die im Persona-Inhalt (Modus oder
 * Profil-Body-Pill) tatsaechlich vorkommen, mit einem rein informativen Badge —
 * das Entfernen bleibt uneingeschraenkt moeglich.
 */
export function PersonaPlaybooksCard({ personaId, canEdit }: PersonaPlaybooksCardProps) {
  const { t } = useTranslation(['personas', 'common', 'playbooks'])
  const wsPath = useWorkspacePath()
  const api = useApi()
  const links = usePersonaPlaybooks(personaId)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  // Referenz-Set aus dem Persona-Inhalt (selbst-enthaltener Fetch, damit die
  // Card keine zusaetzliche Prop von der Detail-Page braucht). Fehler bleiben
  // still — der Badge ist rein informativ, kein blockierender State.
  const [referencedIds, setReferencedIds] = useState<Set<string>>(() => new Set<string>())

  useEffect(() => {
    let active = true
    api
      .getPersona(personaId)
      .then((persona) => {
        if (active) setReferencedIds(collectReferencedPlaybookIds(persona.content))
      })
      .catch(() => {
        if (active) setReferencedIds(new Set<string>())
      })
    return () => {
      active = false
    }
  }, [api, personaId])

  // Bearbeiten-Modus: zwei Sektionen statt eines Checkbox-Pickers. Beide leiten
  // aus der lokalen (ungespeicherten) Auswahl `linkedIds` ab, damit ein Toggle
  // die Zeile sofort zwischen „Verknüpft" und „Hinzufügen" verschiebt.
  const linkedNow = useMemo(
    () => links.playbooks.filter((playbook) => links.linkedIds.includes(playbook.id)),
    [links.playbooks, links.linkedIds],
  )
  const available = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return links.playbooks.filter(
      (playbook) =>
        !links.linkedIds.includes(playbook.id) &&
        (needle === '' || playbook.name.toLowerCase().includes(needle)),
    )
  }, [links.playbooks, links.linkedIds, query])

  // Voll-Objekt eines Sub-Playbooks aus der Workspace-Liste — liefert
  // Status/Version fuer die aufgeklappten Kind-Zeilen (keine neue Query).
  const byId = useMemo(() => {
    const map = new Map<string, Playbook>()
    for (const playbook of links.playbooks) {
      map.set(playbook.id, playbook)
    }
    return map
  }, [links.playbooks])

  const startEditing = () => {
    setQuery('')
    setEditing(true)
  }

  const cancelEditing = () => {
    links.cancel()
    setEditing(false)
  }

  const saveLinks = async () => {
    const saved = await links.save()
    if (saved) {
      setEditing(false)
    }
  }

  const renderLinked = (playbook: Playbook) => {
    const triggerCount = splitTriggers(playbook.triggers).length
    const metaText =
      triggerCount > 0
        ? `${playbook.type} · ${t('personas:detail.playbooks.triggerCount', { count: triggerCount })}`
        : playbook.type
    const composeChildren = playbook.compose_children ?? []
    const hasChildren = composeChildren.length > 0
    const referenced = referencedIds.has(playbook.id)

    return (
      <EntityCard
        key={playbook.id}
        icon={Share2}
        iconTone="playbook"
        title={playbook.name}
        href={wsPath(`/playbooks/${playbook.id}`)}
        status={
          <StatusBadge
            status={playbook.current_status}
            pendingDraft={playbook.has_pending_draft}
          />
        }
        badges={
          playbook.is_composite === true || referenced ? (
            <>
              {playbook.is_composite === true ? (
                <Badge variant="secondary">{t('personas:detail.playbooks.compositeBadge')}</Badge>
              ) : null}
              {referenced ? (
                <PlaybookReferencedBadge
                  label={t('personas:detail.playbooks.referencedBadge')}
                  hint={t('personas:detail.playbooks.referencedHint')}
                />
              ) : null}
            </>
          ) : null
        }
        meta={<span className="text-xs text-muted-foreground">{metaText}</span>}
        expandable={
          hasChildren ? (
            <SubPlaybookList
              items={composeChildren}
              wsPath={wsPath}
              resolveChild={(ref) => byId.get(ref.id)}
              label={t('playbooks:list.subPlaybooksListLabel')}
            />
          ) : undefined
        }
        expandIcon={Layers}
        expandLabel={
          hasChildren
            ? t('playbooks:list.subPlaybooksCount', { count: composeChildren.length })
            : undefined
        }
        expandSummary={
          hasChildren ? composeChildren.map((child) => child.name).join(' · ') : undefined
        }
      />
    )
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2">
          {t('personas:detail.playbooks.title')}
          {links.linked.length > 0 ? (
            <Badge variant="secondary">{links.linked.length}</Badge>
          ) : null}
        </CardTitle>
        {canEdit && !editing ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={startEditing}
            disabled={links.loading}
          >
            {t('personas:detail.playbooks.edit')}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent>
        {editing ? (
          <Stack gap="md">
            <DataView
              loading={links.loading}
              error={links.error}
              empty={links.playbooks.length === 0}
              emptyTitle={t('personas:detail.playbooks.noneAvailable')}
            >
              <Stack gap="md">
                {/* Verknüpft — aktuell gesetzte Links mit „Entfernen". */}
                <div>
                  <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    {t('personas:detail.playbooks.linkedTitle')}
                  </p>
                  {linkedNow.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {t('personas:detail.playbooks.empty')}
                    </p>
                  ) : (
                    <ul className="divide-y divide-border rounded-lg border border-border">
                      {linkedNow.map((playbook) => (
                        <PlaybookLinkItem
                          key={playbook.id}
                          name={playbook.name}
                          status={<StatusBadge status={playbook.current_status} />}
                          referenced={referencedIds.has(playbook.id)}
                          referencedLabel={t('personas:detail.playbooks.referencedBadge')}
                          referencedHint={t('personas:detail.playbooks.referencedHint')}
                          actionLabel={t('personas:detail.playbooks.remove')}
                          actionIcon={X}
                          onAction={() => links.toggle(playbook.id)}
                          disabled={links.saving}
                        />
                      ))}
                    </ul>
                  )}
                </div>

                {/* Playbook hinzufügen — Suche + noch nicht verknüpfte Playbooks. */}
                <div>
                  <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                    {t('personas:detail.playbooks.addTitle')}
                  </p>
                  <Label htmlFor="persona-playbooks-search" className="sr-only">
                    {t('personas:detail.playbooks.searchLabel')}
                  </Label>
                  <Input
                    id="persona-playbooks-search"
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t('personas:detail.playbooks.searchPlaceholder')}
                    className="mb-2"
                  />
                  {available.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      {t('personas:detail.playbooks.searchEmpty')}
                    </p>
                  ) : (
                    <ul className="max-h-72 divide-y divide-border overflow-auto rounded-lg border border-border">
                      {available.map((playbook) => (
                        <PlaybookLinkItem
                          key={playbook.id}
                          name={playbook.name}
                          actionLabel={t('personas:detail.playbooks.link')}
                          actionIcon={Plus}
                          onAction={() => links.toggle(playbook.id)}
                          disabled={links.saving}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              </Stack>
            </DataView>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={cancelEditing}
                disabled={links.saving}
              >
                {t('common:actions.cancel')}
              </Button>
              <Button
                type="button"
                onClick={() => void saveLinks()}
                disabled={links.saving || links.loading}
              >
                {t('personas:detail.playbooks.save')}
              </Button>
            </div>
          </Stack>
        ) : (
          <DataView
            loading={links.loading}
            error={links.error}
            empty={links.linked.length === 0}
            emptyTitle={t('personas:detail.playbooks.empty')}
          >
            <div className="flex flex-col gap-2">{links.linked.map(renderLinked)}</div>
          </DataView>
        )}
      </CardContent>
    </Card>
  )
}
