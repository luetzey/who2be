import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useAgents } from '@/hooks/useAgents'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

import { ApprovalQueue } from '../components/ApprovalQueue'

/**
 * Gedaechtnis-Seite (Spec §11.2). C5a liefert nur S1′ „Zur Freigabe“; die
 * Tab-Leiste kommt mit C5b. `/memory` setzt `?tab=approval`, damit Links aus
 * Banner und Benachrichtigungen schon heute stabil sind. Suche (`q`) und
 * Agent-Filter (`agent`) stehen in der URL.
 */
export function MemoryPage() {
  const { t } = useTranslation('learning')
  const role = useCurrentWorkspaceRole()
  const canManageAgents = role !== null && role !== 'viewer'
  const [params, setParams] = useSearchParams()
  const searchId = useId()

  const agentId = params.get('agent') ?? ''
  const [query, setQuery] = useState(params.get('q') ?? '')
  const debouncedQuery = useDebouncedValue(query.trim())

  useEffect(() => {
    if (params.get('tab') !== null) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('tab', 'approval')
        return next
      },
      { replace: true },
    )
  }, [params, setParams])

  useEffect(() => {
    if ((params.get('q') ?? '') === debouncedQuery) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (debouncedQuery === '') next.delete('q')
        else next.set('q', debouncedQuery)
        return next
      },
      { replace: true },
    )
  }, [debouncedQuery, params, setParams])

  const setAgent = (id: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (id === '') next.delete('agent')
      else next.set('agent', id)
      return next
    })

  const resetFilters = () => {
    setQuery('')
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('q')
      next.delete('agent')
      return next
    })
  }

  return (
    <Container>
      <PageHeader title={t('page.title')} description={t('page.description')} />
      <div className="mt-6 flex flex-col gap-6">
        <h2 className="text-lg font-semibold">{t('page.tabs.approval')}</h2>
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <Label htmlFor={searchId}>{t('approval.search')}</Label>
            <Input
              id={searchId}
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('approval.searchPlaceholder')}
            />
          </div>
          {canManageAgents ? <AgentFilter value={agentId} onChange={setAgent} /> : null}
        </div>
        <ApprovalQueue
          q={params.get('q') ?? ''}
          agentId={canManageAgents ? agentId : ''}
          onShowAgent={setAgent}
          onResetFilters={resetFilters}
        />
      </div>
    </Container>
  )
}

function AgentFilter({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useTranslation('learning')
  const { agents } = useAgents()
  const selectId = useId()
  return (
    <div className="flex flex-col gap-1 md:w-64">
      <Label htmlFor={selectId}>{t('approval.agentFilter')}</Label>
      <Select id={selectId} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t('approval.allAgents')}</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name}
          </option>
        ))}
      </Select>
    </div>
  )
}
