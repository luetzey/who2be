import { Trash2 } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { WorkAreaGrant, WorkAreaGrantLevel } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { DataView } from '@/components/data/DataView'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAgents } from '@/hooks/useAgents'
import { useListData } from '@/hooks/useListData'
import { notify } from '@/lib/feedback'

const LEVELS: readonly WorkAreaGrantLevel[] = ['read', 'write']

interface AreaGrantsProps {
  areaId: string
}

/**
 * Freigaben eines geteilten Arbeitsbereichs (ADR-0047).
 *
 * Grant-Vergabe ist serverseitig MENSCHEN vorbehalten — ein agent-gebundener
 * Token bekommt 403. Ein Agent, der sich selbst Zugriff verschaffen koennte,
 * haette das Grant-Modell ausgehebelt. In der Web-UI ist deshalb nur die Rolle
 * zu pruefen (der Browser spricht immer mit einem Menschen-JWT): Viewer sehen
 * den Stand, aendern koennen ihn editor+.
 *
 * Der Aufrufer stellt sicher, dass die Area `scope='shared'` ist — private
 * Areas sind nicht grantbar und antworten mit 403 `area_forbidden`.
 */
export function AreaGrants({ areaId }: AreaGrantsProps) {
  const { t } = useTranslation('workarea')
  const api = useApi()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const { agents } = useAgents()
  const loader = useCallback(() => api.listWorkAreaGrants(areaId), [api, areaId])
  const { data: grants, loading, error, reload } = useListData<WorkAreaGrant>(loader)
  const [busy, setBusy] = useState(false)
  const [pendingAgent, setPendingAgent] = useState('')

  const agentName = (id: string): string =>
    agents.find((agent) => agent.id === id)?.name ?? id

  // Nur Agenten anbieten, die noch keinen Grant haben — ein zweiter Eintrag
  // fuer denselben Agenten waere ein Update, kein Hinzufuegen.
  const grantedIds = new Set(grants.map((grant) => grant.agent_id))
  const selectable = agents.filter((agent) => !grantedIds.has(agent.id))

  const setGrant = async (agentId: string, level: WorkAreaGrantLevel) => {
    setBusy(true)
    try {
      await api.setWorkAreaGrant(areaId, agentId, { level })
      notify.success(t('grants.savedToast'))
      reload()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('grants.actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  const removeGrant = async (agentId: string) => {
    setBusy(true)
    try {
      await api.deleteWorkAreaGrant(areaId, agentId)
      notify.success(t('grants.removedToast'))
      reload()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('grants.actionFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('grants.description')}</p>
      <DataView
        loading={loading}
        error={error}
        empty={grants.length === 0}
        emptyTitle={t('grants.emptyTitle')}
        emptyDescription={t('grants.emptyDescription')}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('grants.agentColumn')}</TableHead>
              <TableHead>{t('grants.levelColumn')}</TableHead>
              {/* Aktionsspalte: visuell leer, aber nicht fuer Screenreader —
                  ein leerer `th` laesst die Spalte unbenannt. */}
              <TableHead>
                <span className="sr-only">{t('grants.remove')}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {grants.map((grant) => (
              <TableRow key={grant.agent_id}>
                <TableCell>{agentName(grant.agent_id)}</TableCell>
                <TableCell>
                  <Label className="sr-only" htmlFor={`grant-level-${grant.agent_id}`}>
                    {t('grants.levelColumn')}
                  </Label>
                  <Select
                    id={`grant-level-${grant.agent_id}`}
                    value={grant.level}
                    disabled={isViewer || busy}
                    title={isViewer ? t('grants.viewerReadOnly') : undefined}
                    onChange={(e) =>
                      void setGrant(grant.agent_id, e.target.value as WorkAreaGrantLevel)
                    }
                  >
                    {LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level === 'write' ? t('grants.levelWrite') : t('grants.levelRead')}
                      </option>
                    ))}
                  </Select>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={isViewer || busy}
                    title={isViewer ? t('grants.viewerReadOnly') : undefined}
                    onClick={() => void removeGrant(grant.agent_id)}
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('grants.remove')}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </DataView>
      {selectable.length > 0 ? (
        <div className="flex flex-wrap items-end gap-2">
          <Label className="flex flex-col items-start gap-1 text-sm font-normal">
            <span className="font-medium">{t('grants.addAgent')}</span>
            <Select
              value={pendingAgent}
              disabled={isViewer || busy}
              title={isViewer ? t('grants.viewerReadOnly') : undefined}
              onChange={(e) => setPendingAgent(e.target.value)}
            >
              <option value="">{t('grants.selectAgent')}</option>
              {selectable.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </Select>
          </Label>
          <Button
            type="button"
            variant="outline"
            disabled={isViewer || busy || pendingAgent === ''}
            title={isViewer ? t('grants.viewerReadOnly') : undefined}
            onClick={() => {
              const agentId = pendingAgent
              setPendingAgent('')
              // Neue Freigaben starten bewusst mit `read` — Schreibrecht ist
              // eine zweite, bewusste Entscheidung, kein Nebeneffekt.
              void setGrant(agentId, 'read')
            }}
          >
            {t('grants.addAgent')}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
