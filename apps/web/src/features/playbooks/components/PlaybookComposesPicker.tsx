// PlaybookComposesPicker — geordneter Multi-Select fuer Composite-Playbooks.
// Listet Workspace-Playbooks ausser dem aktuellen, schreibt via PUT /{id}/composes.
// Muster: ResourceBlockLinkPicker + usePlaybookComposes.

import { ChevronDown, ChevronUp } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

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
  const { t } = useTranslation('playbooks')
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
        setLoadError(cause instanceof Error ? cause.message : t('composesPicker.loadFailed')),
      )
  }, [open, existing, api, currentPlaybookId, t])

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
          {t('composesPicker.triggerButton')}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('composesPicker.dialogTitle')}</DialogTitle>
          <DialogDescription>
            {t('composesPicker.dialogDescription')}
          </DialogDescription>
        </DialogHeader>

        {loadError !== null ? (
          <p className="text-sm text-destructive">{loadError}</p>
        ) : null}

        {/* Ausgewaehlte Kinder in Reihenfolge */}
        {selected.length > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t('composesPicker.selectedHeading', { count: selected.length })}
            </p>
            <ul className="flex flex-col gap-1" aria-label={t('composesPicker.selectedList')}>
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
                      aria-label={t('composesPicker.moveUp', { name: nameOf(id) })}
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
                      aria-label={t('composesPicker.moveDown', { name: nameOf(id) })}
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
                      {t('common:actions.remove')}
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Verbleibende auswaehlbare Playbooks */}
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {selected.length > 0 ? t('composesPicker.addMore') : t('composesPicker.availableHeading')}
          </p>
          <ul
            className="flex max-h-60 flex-col gap-1 overflow-auto"
            aria-label={t('composesPicker.availableList')}
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
                    aria-label={t('composesPicker.addAriaLabel', { name: pb.name })}
                  />
                  <Label
                    htmlFor={checkId}
                    className="flex cursor-pointer flex-col gap-1 font-normal"
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
                {t('composesPicker.noPlaybooks')}
              </li>
            ) : unselected.length === 0 ? (
              <li className="px-3 py-2 text-sm text-muted-foreground">
                {t('composesPicker.noMore')}
              </li>
            ) : null}
          </ul>
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            {t('common:actions.cancel')}
          </Button>
          <Button
            type="button"
            variant="brand"
            onClick={() => void handleSave()}
            disabled={saving}
          >
            {t('composesPicker.saveButton', { count: selected.length })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
