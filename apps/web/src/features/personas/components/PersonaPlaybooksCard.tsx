import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { usePersonaPlaybooks } from '@/hooks/usePersonaPlaybooks'
import { splitTriggers } from '@/lib/triggers'

import { PlaybookLinkItem } from './PlaybookLinkItem'

interface PersonaPlaybooksCardProps {
  personaId: string
  /** Editor-/Admin-Rechte und nicht managed — sonst reiner Anzeige-Modus. */
  canEdit: boolean
}

/**
 * Playbooks-Sektion der Persona-Detailseite (WP-E). Default ist ein
 * navigierbarer Anzeige-Modus (Links + Status/Composite-Badges + Meta);
 * der Checkbox-Picker liegt hinter „Verknüpfungen bearbeiten“ und bekommt
 * ein Namens-Suchfeld. Abbrechen verwirft lokale Auswahl-Änderungen.
 */
export function PersonaPlaybooksCard({ personaId, canEdit }: PersonaPlaybooksCardProps) {
  const { t } = useTranslation(['personas', 'common'])
  const wsPath = useWorkspacePath()
  const links = usePersonaPlaybooks(personaId)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (needle === '') {
      return links.playbooks
    }
    return links.playbooks.filter((playbook) => playbook.name.toLowerCase().includes(needle))
  }, [links.playbooks, query])

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
    return (
      <li key={playbook.id} className="flex flex-wrap items-center gap-2 text-sm">
        <Link
          to={wsPath(`/playbooks/${playbook.id}`)}
          className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          {playbook.name}
        </Link>
        <StatusBadge
          status={playbook.current_status}
          pendingDraft={playbook.has_pending_draft}
        />
        {playbook.is_composite === true ? <Badge variant="secondary">Composite</Badge> : null}
        <span className="text-xs text-muted-foreground">
          {playbook.type}
          {triggerCount > 0
            ? ` · ${t('personas:detail.playbooks.triggerCount', { count: triggerCount })}`
            : ''}
        </span>
      </li>
    )
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle>{t('personas:detail.playbooks.title')}</CardTitle>
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
          <Stack gap="sm">
            <div>
              <Label htmlFor="persona-playbooks-search" className="sr-only">
                {t('personas:detail.playbooks.searchLabel')}
              </Label>
              <Input
                id="persona-playbooks-search"
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('personas:detail.playbooks.searchPlaceholder')}
              />
            </div>
            <DataView
              loading={links.loading}
              error={links.error}
              empty={links.playbooks.length === 0}
              emptyTitle={t('personas:detail.playbooks.noneAvailable')}
            >
              {filtered.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t('personas:detail.playbooks.searchEmpty')}
                </p>
              ) : (
                <ul className="flex max-h-72 flex-col gap-2 overflow-auto">
                  {filtered.map((playbook) => (
                    <PlaybookLinkItem
                      key={playbook.id}
                      id={playbook.id}
                      name={playbook.name}
                      checked={links.linkedIds.includes(playbook.id)}
                      onToggle={() => links.toggle(playbook.id)}
                    />
                  ))}
                </ul>
              )}
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
            <ul
              className="flex flex-col gap-2"
              aria-label={t('personas:detail.playbooks.title')}
            >
              {links.linked.map(renderLinked)}
            </ul>
          </DataView>
        )}
      </CardContent>
    </Card>
  )
}
