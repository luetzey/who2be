// PlaybookComposesPicker — geordneter Multi-Select fuer Composite-Playbooks.
// Listet Workspace-Playbooks ausser dem aktuellen, schreibt via PUT /{id}/composes.
// Muster: ResourceBlockLinkPicker + usePlaybookComposes.

import { ChevronDown, ChevronUp } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import type { Playbook } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

interface PlaybookComposesPickerProps {
  /** ID des aktuellen Playbooks — wird aus der Auswahl ausgeschlossen. */
  currentPlaybookId: string
  /** Aktuelle Kinder-Liste (geordnet). */
  existing: Playbook[]
  saving: boolean
  onSave: (childIds: string[]) => void | Promise<void>
}

export function PlaybookComposesPicker({
  currentPlaybookId,
  existing,
  saving,
  onSave,
}: PlaybookComposesPickerProps) {
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [allPlaybooks, setAllPlaybooks] = useState<Playbook[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  // Beim Oeffnen: aktuelle Auswahl aus den bestehenden Kindern uebernehmen.
  useEffect(() => {
    if (!open) {
      return
    }
    setSelected(existing.map((pb) => pb.id))
    setLoadError(null)
    api
      .listPlaybooks()
      .then((playbooks) =>
        setAllPlaybooks(playbooks.filter((pb) => pb.id !== currentPlaybookId)),
      )
      .catch((cause: unknown) =>
        setLoadError(cause instanceof Error ? cause.message : 'Laden fehlgeschlagen.'),
      )
  }, [open, existing, api, currentPlaybookId])

  const toggle = useCallback((id: string) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((entry) => entry !== id) : [...current, id],
    )
  }, [])

  // Reihenfolge-Änderungen: Eintrag hoch- oder runterschieben.
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
    await onSave(selected)
    setOpen(false)
  }, [selected, onSave])

  // Sichtbare Liste: erst ausgewaehlte (in ihrer Reihenfolge), dann restliche.
  const selectedSet = new Set(selected)
  const unselected = allPlaybooks.filter((pb) => !selectedSet.has(pb.id))

  // Playbook-Name-Lookup fuer geordnete Anzeige.
  const nameOf = (id: string): string =>
    allPlaybooks.find((pb) => pb.id === id)?.name ?? id

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline">
          Sub-Playbooks bearbeiten
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Sub-Playbooks (Composition)</DialogTitle>
          <DialogDescription>
            Wähle Playbooks als Sub-Playbooks aus und ordne sie per Pfeil-Buttons. Die
            Reihenfolge bestimmt die Ausführungssequenz beim Rendern.
          </DialogDescription>
        </DialogHeader>

        {loadError !== null ? (
          <p className="text-sm text-destructive">{loadError}</p>
        ) : null}

        {/* Ausgewaehlte Kinder in Reihenfolge */}
        {selected.length > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Ausgewählt ({selected.length})
            </p>
            <ul className="flex flex-col gap-1" aria-label="Ausgewaehlte Sub-Playbooks">
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

        {/* Verbleibende auswaehlbare Playbooks */}
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            {selected.length > 0 ? 'Weitere hinzufügen' : 'Playbooks'}
          </p>
          <ul
            className="flex max-h-60 flex-col gap-1 overflow-auto"
            aria-label="Verfuegbare Playbooks"
          >
            {unselected.map((pb) => {
              const checkId = `compose-pick-${pb.id}`
              return (
                <li
                  key={pb.id}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-md border p-3 hover:bg-muted/40',
                  )}
                >
                  <Checkbox
                    id={checkId}
                    checked={false}
                    onChange={() => toggle(pb.id)}
                    aria-label={`${pb.name} als Sub-Playbook hinzufügen`}
                  />
                  <Label
                    htmlFor={checkId}
                    className="flex cursor-pointer flex-col gap-0.5 font-normal"
                  >
                    <span className="text-sm font-medium">{pb.name}</span>
                    {pb.content.description ? (
                      <span className="text-xs text-muted-foreground">
                        {pb.content.description}
                      </span>
                    ) : null}
                  </Label>
                </li>
              )
            })}
            {unselected.length === 0 && allPlaybooks.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                Keine weiteren Playbooks im Workspace.
              </li>
            ) : unselected.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                Alle verfügbaren Playbooks sind bereits ausgewählt.
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
