// SubResourcePicker — geordneter Multi-Select fuer Sub-Resources (Track E §3.3).
// Listet Workspace-Resources ausser der aktuellen, schreibt via
// PUT /resources/{id}/sub_resources als Volldokument-Refs (link_scope='resource').
// Muster: PlaybookComposesPicker + useResourceSubResources.

import { ChevronDown, ChevronUp } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import type { Resource, SubResource, SubResourceLinkInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

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
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [allResources, setAllResources] = useState<Resource[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Beim Oeffnen: aktuelle Auswahl aus den bestehenden Kindern uebernehmen.
  // Nur Volldokument-Refs (link_scope='resource') werden im Picker verwaltet;
  // etwaige Block-Anker bleiben unberuehrt erhalten (siehe handleSave).
  useEffect(() => {
    if (!open) {
      return
    }
    setSelected(
      existing.filter((sub) => sub.link_scope === 'resource').map((sub) => sub.id),
    )
    setLoadError(null)
    api
      .listResources()
      .then((resources) =>
        setAllResources(resources.filter((r) => r.id !== currentResourceId)),
      )
      .catch((cause: unknown) =>
        setLoadError(cause instanceof Error ? cause.message : 'Laden fehlgeschlagen.'),
      )
  }, [open, existing, api, currentResourceId])

  const toggle = useCallback((id: string) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id],
    )
  }, [])

  const move = useCallback((id: string, direction: 'up' | 'down') => {
    setSelected((current) => {
      const index = current.indexOf(id)
      if (index < 0) return current
      const next = [...current]
      const target = direction === 'up' ? index - 1 : index + 1
      if (target < 0 || target >= next.length) return current
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }, [])

  const handleSave = useCallback(async () => {
    // Volldokument-Refs aus der Auswahl + erhaltene Block-Anker zusammenfuehren,
    // dann durchgaengig neu positionieren (Set-Replace ist vollstaendig).
    const blockAnchors = existing.filter((sub) => sub.link_scope === 'block')
    const resourceLinks: SubResourceLinkInput[] = selected.map((id) => ({
      child_id: id,
      block_id: null,
      position: 0,
      link_scope: 'resource',
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
    await onSave(links)
    setOpen(false)
  }, [selected, existing, onSave])

  const selectedSet = new Set(selected)
  const unselected = allResources.filter((r) => !selectedSet.has(r.id))

  const nameOf = (id: string): string =>
    allResources.find((r) => r.id === id)?.name ?? id

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          Sub-Resources bearbeiten
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Sub-Resources (Composition)</DialogTitle>
          <DialogDescription>
            Wähle Resources als Sub-Resources aus und ordne sie per Pfeil-Buttons. Agenten
            laden sie über <code>fetch_resource</code> nach — die Inhalte werden nicht
            expandiert.
          </DialogDescription>
        </DialogHeader>

        {loadError !== null ? (
          <p className="text-sm text-destructive">{loadError}</p>
        ) : null}

        {selected.length > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Ausgewählt ({selected.length})
            </p>
            <ul className="flex flex-col gap-1" aria-label="Ausgewaehlte Sub-Resources">
              {selected.map((id, index) => (
                <li
                  key={id}
                  className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <span className="flex items-center gap-2">
                    <span className="w-5 text-right text-xs text-muted-foreground">
                      {index + 1}.
                    </span>
                    <span className="font-medium">{nameOf(id)}</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => move(id, 'up')}
                      disabled={index === 0}
                      aria-label={`${nameOf(id)} nach oben verschieben`}
                    >
                      <ChevronUp className="size-3" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => move(id, 'down')}
                      disabled={index === selected.length - 1}
                      aria-label={`${nameOf(id)} nach unten verschieben`}
                    >
                      <ChevronDown className="size-3" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs text-muted-foreground"
                      onClick={() => toggle(id)}
                    >
                      Entfernen
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {selected.length > 0 ? 'Weitere hinzufügen' : 'Resources'}
          </p>
          <ul
            className="flex max-h-60 flex-col gap-1 overflow-auto"
            aria-label="Verfuegbare Resources"
          >
            {unselected.map((resource) => {
              const checkId = `sub-resource-pick-${resource.id}`
              return (
                <li
                  key={resource.id}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-md border p-3 hover:bg-muted/40',
                  )}
                >
                  <Checkbox
                    id={checkId}
                    checked={false}
                    onChange={() => toggle(resource.id)}
                    aria-label={`${resource.name} als Sub-Resource hinzufügen`}
                  />
                  <Label
                    htmlFor={checkId}
                    className="flex cursor-pointer flex-col gap-1 font-normal"
                  >
                    <span className="text-sm font-medium">{resource.name}</span>
                    {resource.content.description ? (
                      <span className="text-xs text-muted-foreground">
                        {resource.content.description}
                      </span>
                    ) : null}
                  </Label>
                </li>
              )
            })}
            {unselected.length === 0 && allResources.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                Keine weiteren Resources im Workspace.
              </li>
            ) : unselected.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                Alle verfügbaren Resources sind bereits ausgewählt.
              </li>
            ) : null}
          </ul>
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Abbrechen
          </Button>
          <Button
            type="button"
            variant="brand"
            onClick={() => void handleSave()}
            disabled={saving}
          >
            Speichern ({selected.length})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
