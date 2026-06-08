import { zodResolver } from '@hookform/resolvers/zod'
import { Copy, KeyRound } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import type { Agent, TokenInput, WorkspaceRole } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'
import { roleLabel, rolesAtMost } from '@/lib/roles'
import { useTokens } from '@/hooks/useTokens'

import { useTokenMutations } from '../hooks/useTokenMutations'

const tokenSchema = z.object({
  name: z.string().min(1, i18n.t('common:validation.nameRequired')),
})

type TokenValues = z.infer<typeof tokenSchema>

function maskTail(token: string): string {
  return token.length <= 6 ? token : `…${token.slice(-6)}`
}

export function SettingsTokensPage() {
  const { t } = useTranslation('tokens')
  const { tokens, loading, error, reload } = useTokens()
  const {
    createError,
    created,
    dismissCreated,
    createToken,
    revokeToken,
    overrideToken,
    setOverrideToken,
  } = useTokenMutations(reload)

  const [overrideInput, setOverrideInput] = useState('')

  // Token erbt höchstens die eigene Rolle (Snapshot, ADR-0023). Solange die
  // Rolle unbekannt ist (`null`), bleibt der Select weg und der Service
  // defaultet serverseitig — der Body trägt dann nur `{ name }`.
  const currentRole = useCurrentWorkspaceRole()
  const roleOptions = currentRole !== null ? rolesAtMost(currentRole) : []
  const [roleOverride, setRoleOverride] = useState<WorkspaceRole | null>(null)
  const role = roleOverride ?? currentRole

  // Optionale Agent-Bindung: ein gebundener Token erbt die MCP-Tool-Policy des
  // Agenten. Agenten werden direkt geladen (kein Cross-Feature-Import).
  const api = useApi()
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentId, setAgentId] = useState('')

  useEffect(() => {
    let cancelled = false
    void api
      .listAgents()
      .then((list) => {
        if (!cancelled) {
          setAgents(list)
        }
      })
      .catch(() => {
        // Agenten-Liste ist optional fuer die Token-Anlage — Fehler still ignorieren.
      })
    return () => {
      cancelled = true
    }
  }, [api])

  const form = useForm<TokenValues>({
    resolver: zodResolver(tokenSchema),
    defaultValues: { name: '' },
  })

  async function onCreate(values: TokenValues) {
    const input: TokenInput =
      currentRole !== null && role !== null
        ? { name: values.name, role }
        : { name: values.name }
    if (agentId !== '') {
      input.agent_id = agentId
    }
    const result = await createToken(input)
    if (result !== null) {
      form.reset({ name: '' })
      setAgentId('')
    }
  }

  function handleOverrideActivate(event: FormEvent) {
    event.preventDefault()
    if (overrideInput === '') {
      return
    }
    setOverrideToken(overrideInput)
    setOverrideInput('')
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('page.title')}
          description={t('page.description')}
        />

        <Card>
          <CardHeader>
            <CardTitle>{t('list.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <DataList
              items={tokens}
              loading={loading}
              error={error}
              getKey={(token) => token.id}
              renderItem={(token) => {
                const isRevoked = token.revoked_at !== null
                return (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Stack gap="xs">
                      <div className="font-medium">{token.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {t('list.createdAt', { date: token.created_at })}
                        {token.last_used_at !== null
                          ? t('list.lastUsed', { date: token.last_used_at })
                          : ''}
                        {isRevoked ? t('list.revoked', { date: token.revoked_at ?? '' }) : ''}
                      </div>
                    </Stack>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void revokeToken(token.id)}
                      disabled={isRevoked}
                    >
                      {t('list.revoke')}
                    </Button>
                  </div>
                )
              }}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('create.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onCreate)} className="flex flex-col gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('common:fields.name')}</FormLabel>
                      <FormControl>
                        <Input required {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {currentRole !== null && role !== null ? (
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="token-role">{t('create.roleLabel')}</Label>
                    <Select
                      id="token-role"
                      value={role}
                      onChange={(event) =>
                        setRoleOverride(event.target.value as WorkspaceRole)
                      }
                    >
                      {roleOptions.map((option) => (
                        <option key={option} value={option}>
                          {roleLabel(option)}
                        </option>
                      ))}
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {t('create.roleHint')}
                    </p>
                  </div>
                ) : null}
                {agents.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="token-agent">{t('create.agentLabel')}</Label>
                    <Select
                      id="token-agent"
                      value={agentId}
                      onChange={(event) => setAgentId(event.target.value)}
                    >
                      <option value="">{t('create.agentNone')}</option>
                      {agents.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </Select>
                    <p className="text-xs text-muted-foreground">{t('create.agentHint')}</p>
                  </div>
                ) : null}
                {createError !== null ? <ErrorAlert message={createError} /> : null}
                <div className="flex justify-end">
                  <Button
                    type="submit"
                    variant="brand"
                    disabled={form.formState.isSubmitting}
                  >
                    {t('create.submit')}
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>

        {created !== null ? (
          <Alert role="status">
            <KeyRound />
            <AlertTitle>{t('reveal.title')}</AlertTitle>
            <AlertDescription>
              <Stack gap="sm">
                <p>
                  {t('reveal.body')}
                </p>
                <Textarea
                  readOnly
                  aria-label={t('reveal.ariaLabel')}
                  value={created.token}
                  rows={2}
                  onFocus={(event) => event.currentTarget.select()}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="brand"
                    size="sm"
                    onClick={() => {
                      void copyToClipboard(created.token).catch((cause: unknown) => {
                        const message = cause instanceof Error ? cause.message : t('common:error.generic')
                        notify.error(message)
                      })
                    }}
                  >
                    <Copy className="h-4 w-4" />
                    {t('reveal.copyButton')}
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={dismissCreated}>
                    {t('common:actions.close')}
                  </Button>
                </div>
              </Stack>
            </AlertDescription>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>{t('override.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Stack gap="md">
              <p className="text-sm text-muted-foreground">
                {t('override.description')}
              </p>
              <p className="text-sm">
                {t('override.statusLabel')}{' '}
                {overrideToken === null
                  ? t('override.statusNone')
                  : t('override.statusActive', { tail: maskTail(overrideToken) })}
              </p>
              <form onSubmit={handleOverrideActivate} className="flex flex-col gap-3">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="override-token">{t('override.inputLabel')}</Label>
                  <Input
                    id="override-token"
                    type="password"
                    value={overrideInput}
                    onChange={(event) => setOverrideInput(event.target.value)}
                    placeholder="w2b_..."
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" disabled={overrideInput === ''}>
                    {t('common:actions.activate')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setOverrideToken(null)}
                    disabled={overrideToken === null}
                  >
                    {t('override.remove')}
                  </Button>
                </div>
              </form>
            </Stack>
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}
