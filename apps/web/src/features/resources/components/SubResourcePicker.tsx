// SubResourcePicker — inline Add/Manage/See-Panel fuer Sub-Resources (Track E
// §3.3, Detail-Redesign). Ersetzt den frueheren Dialog durch eine im Tab
// sichtbare Insel: „Eingebunden" (Block-Anker read-only, Resource-Links mit
// Lazy/Inline-Toggle + Entfernen + Reorder) und „Sub-Resource hinzufügen"
// (Suche + verfuegbare Resources). Schreibt via
// PUT /resources/{id}/sub_resources als Volldokument-Refs
// (link_scope='resource'); Block-Anker (link_scope='block') bleiben unberuehrt
// erhalten. Muster: PlaybookComposesPicker + useResourceSubResources.

import { ChevronDown, ChevronUp, FileText, Info, Lock, Pencil, Plus, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { EmbeddingMode, Resource, SubResource, SubResourceLinkInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { EntityIcon } from '@/components/data/EntityIcon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface SubResourcePickerProps {
  /** ID der aktuellen Resource — wird aus der Auswahl ausgeschlossen. */
  currentResourceId: string
  /** Aktuelle Sub-Resource-Liste (geordnet). */
  existing: SubResource[]
  saving: boolean
  onSave: (links: SubResourceLinkInput[]) => void | Promise<void>
}

export function SubResourcePicker({
  currentResourceId,
  existing,
  saving,
  onSave,
}: SubResourcePickerProps) {
  const { t } = useTranslation('resources')
  const api = useApi()
  const [allResources, setAllResources] = useState<Resource[]>([])
  // Resource-Link-Kinder (link_scope='resource') als geordnete Arbeitsliste.
  // Block-Anker werden separat aus `existing` gelesen und nie hier verwaltet.
  const [selected, setSelected] = useState<string[]>([])
  // Embed-Modus je Resource-Link (Default 'lazy'). 'inline' liefert das
  // Volldokument vom MCP mit; 'lazy' bleibt reine Referenz.
  const [modes, setModes] = useState<Record<string, EmbeddingMode>>({})
  const [loadError, setLoadError] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  // Workspace-Resources einmalig laden (ohne die aktuelle Resource selbst).
  useEffect(() => {
    setLoadError(null)
    api
      .listResources()
      .then((resources) =>
        setAllResources(resources.filter((r) => r.id !== currentResourceId)),
      )
      .catch((cause: unknown) =>
        setLoadError(cause instanceof Error ? cause.message : t('picker.loadError')),
      )
  }, [api, currentResourceId, t])

  // Arbeitsliste aus den bestehenden Kindern ableiten — bei Mount und nach jedem
  // erfolgreichen Speichern (dann liefert der Hook die frische Kinder-Liste).
  useEffect(() => {
    const resourceSubs = existing.filter((sub) => sub.link_scope === 'resource')
    setSelected(resourceSubs.map((sub) => sub.id))
    setModes(
      Object.fromEntries(
        resourceSubs.map((sub) => [sub.id, sub.embedding_mode ?? 'lazy']),
      ),
    )
  }, [existing])

  const blockAnchors = existing.filter((sub) => sub.link_scope === 'block')

  const nameOf = (id: string): string =>
    allResources.find((r) => r.id === id)?.name ??
    existing.find((sub) => sub.id === id)?.name ??
    id

  // Volldokument-Refs aus der Arbeitsliste + erhaltene Block-Anker zusammenfuehren,
  // dann durchgaengig neu positionieren (Set-Replace ist vollstaendig). Identische
  // Semantik wie der fruehere handleSave — nur ohne Dialog-Schliessen.
  const persist = (
    nextSelected: string[],
    nextModes: Record<string, EmbeddingMode>,
  ) => {
    const resourceLinks: SubResourceLinkInput[] = nextSelected.map((id) => ({
      child_id: id,
      block_id: null,
      position: 0,
      link_scope: 'resource',
      embedding_mode: nextModes[id] ?? 'lazy',
    }))
    const anchorLinks: SubResourceLinkInput[] = blockAnchors.map((sub) => ({
      child_id: sub.id,
      block_id: sub.block_id,
      position: 0,
      link_scope: 'block',
    }))
    const links = [...resourceLinks, ...anchorLinks].map((link, index) => ({
      ...link,
      position: index,
    }))
    void onSave(links)
  }

  const addResource = (id: string) => {
    const nextSelected = [...selected, id]
    const nextModes = { ...modes, [id]: modes[id] ?? 'lazy' }
    setSelected(nextSelected)
    setModes(nextModes)
    persist(nextSelected, nextModes)
  }

  const removeResource = (id: string) => {
    const nextSelected = selected.filter((entry) => entry !== id)
    setSelected(nextSelected)
    persist(nextSelected, modes)
  }

  const changeMode = (id: string, mode: EmbeddingMode) => {
    const nextModes = { ...modes, [id]: mode }
    setModes(nextModes)
    persist(selected, nextModes)
  }

  const move = (id: string, direction: 'up' | 'down') => {
    const index = selected.indexOf(id)
    if (index < 0) return
    const next = [...selected]
    const target = direction === 'up' ? index - 1 : index + 1
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    setSelected(next)
    persist(next, modes)
  }

  const linkedIds = new Set([...selected, ...blockAnchors.map((sub) => sub.id)])
  const needle = query.trim().toLowerCase()
  const available = allResources
    .filter((r) => !linkedIds.has(r.id))
    .filter((r) => needle === '' || r.name.toLowerCase().includes(needle))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h3 className="text-base font-semibold tracking-tight">
          {t('subInline.title')}
        </h3>
        <p className="text-sm text-muted-foreground">{t('subInline.description')}</p>
      </div>

      {loadError !== null ? (
        <p className="text-sm text-destructive">{loadError}</p>
      ) : null}

      {blockAnchors.length > 0 ? (
        <div className="flex items-start gap-2 rounded-md border border-pill-resource-fg/25 bg-pill-resource/40 px-3 py-2 text-sm text-muted-foreground">
          <Info
            className="mt-0.5 size-4 shrink-0 text-pill-resource-fg"
            aria-hidden="true"
          />
          <span>{t('subInline.blockManagedHint')}</span>
        </div>
      ) : null}

      {existing.length > 0 ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('subInline.included')}
          </p>
          <ul className="flex flex-col gap-1" aria-label={t('subInline.included')}>
            {blockAnchors.map((sub) => (
              <li
                key={`anchor-${sub.id}-${sub.block_id ?? 'doc'}`}
                className="flex items-center gap-3 rounded-md border bg-pill-resource/30 px-3 py-2"
              >
                <EntityIcon icon={FileText} tone="resource" size="sm" />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium">{sub.name}</span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-pill-resource px-2 py-0.5 text-xs font-semibold text-pill-resource-fg">
                      {/* size-3 bewusst (funktionaler Sonderfall §8): Icon in
                          der kompakten text-xs-Pill. */}
                      <Pencil className="size-3" aria-hidden="true" />
                      {sub.block_id
                        ? t('subInline.inTextAnchor', { blockId: sub.block_id })
                        : t('subInline.inText')}
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {t('subInline.blockManagedRow')}
                  </span>
                </span>
                <span
                  className="text-muted-foreground/60"
                  title={t('subInline.managedTitle')}
                >
                  <Lock className="size-4" aria-hidden="true" />
                </span>
              </li>
            ))}
            {selected.map((id, index) => {
              const mode = modes[id] ?? 'lazy'
              return (
                <li
                  key={id}
                  className="flex items-center gap-2 rounded-md border px-3 py-2"
                >
                  <span className="w-5 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                    {index + 1}.
                  </span>
                  <EntityIcon icon={FileText} tone="resource" size="sm" />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">
                    {nameOf(id)}
                  </span>
                  <span
                    className="inline-flex overflow-hidden rounded-md border"
                    role="group"
                    aria-label={t('subInline.embedModeFor', { name: nameOf(id) })}
                  >
                    <Button
                      type="button"
                      variant={mode === 'lazy' ? 'brand' : 'ghost'}
                      size="sm"
                      className="h-8 rounded-none px-2 text-xs"
                      onClick={() => changeMode(id, 'lazy')}
                      aria-pressed={mode === 'lazy'}
                      disabled={saving}
                    >
                      {t('subInline.modeLazy')}
                    </Button>
                    <Button
                      type="button"
                      variant={mode === 'inline' ? 'brand' : 'ghost'}
                      size="sm"
                      className="h-8 rounded-none px-2 text-xs"
                      onClick={() => changeMode(id, 'inline')}
                      aria-pressed={mode === 'inline'}
                      disabled={saving}
                    >
                      {t('subInline.modeInline')}
                    </Button>
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="size-8 p-0"
                    onClick={() => move(id, 'up')}
                    disabled={saving || index === 0}
                    aria-label={t('picker.moveUp', { name: nameOf(id) })}
                  >
                    <ChevronUp className="size-4" aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="size-8 p-0"
                    onClick={() => move(id, 'down')}
                    disabled={saving || index === selected.length - 1}
                    aria-label={t('picker.moveDown', { name: nameOf(id) })}
                  >
                    <ChevronDown className="size-4" aria-hidden="true" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="size-8 p-0 text-destructive"
                    onClick={() => removeResource(id)}
                    disabled={saving}
                    aria-label={t('subInline.removeAria', { name: nameOf(id) })}
                  >
                    <X className="size-4" aria-hidden="true" />
                  </Button>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t('subInline.add')}
        </p>
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          {/* pl-9 ist bewusst off-scale (funktionaler Icon-Inset):
              left-3 (12px) + size-4 (16px) + 8px Luft = 36px, damit der
              Eingabetext nicht unter dem Such-Icon liegt. */}
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('subInline.searchPlaceholder')}
            aria-label={t('subInline.searchPlaceholder')}
            className="pl-9"
          />
        </div>
        <ul
          className="flex max-h-72 flex-col gap-1 overflow-auto"
          aria-label={t('picker.availableAriaLabel')}
        >
          {available.map((resource) => (
            <li key={resource.id}>
              <Button
                type="button"
                variant="ghost"
                className="h-auto w-full justify-start gap-3 px-3 py-2"
                onClick={() => addResource(resource.id)}
                disabled={saving}
                aria-label={t('picker.addAriaLabel', { name: resource.name })}
              >
                <EntityIcon icon={FileText} tone="resource" size="sm" />
                <span className="min-w-0 flex-1 truncate text-left text-sm font-medium">
                  {resource.name}
                </span>
                <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                  <Plus className="size-4" aria-hidden="true" />
                  {t('subInline.addAction')}
                </span>
              </Button>
            </li>
          ))}
          {available.length === 0 ? (
            <li className="px-3 py-3 text-center text-sm text-muted-foreground">
              {t('subInline.noResults')}
            </li>
          ) : null}
        </ul>
      </div>
    </div>
  )
}
