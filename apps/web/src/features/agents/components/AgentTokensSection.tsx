import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import type { TokenInput, WorkspaceRole } from '@/api/types'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { DataList } from '@/components/data/DataList'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { TokenSecretReveal } from '@/components/data/TokenSecretReveal'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useAgentTokens } from '@/hooks/useTokens'
import { useTokenMutations } from '@/hooks/useTokenMutations'
import { roleLabel, rolesAtMost } from '@/lib/roles'

const tokenSchema = z.object({
  name: z.string().min(1, i18n.t('common:validation.nameRequired')),
})

type TokenValues = z.infer<typeof tokenSchema>

interface AgentTokensSectionProps {
  agentId: string
}

/**
 * Token-Verwaltung direkt am Agenten: jeder Token ist implizit an diesen
 * Agenten gebunden (secure by default). Anzeigen, Erstellen, Umbenennen,
 * Rotieren (neues Secret), Widerrufen.
 */
export function AgentTokensSection({ agentId }: AgentTokensSectionProps) {
  const { t } = useTranslation('tokens')
  const { tokens, loading, error, reload } = useAgentTokens(agentId)
  const { createError, revealed, dismissRevealed, createToken, renameToken, rotateToken, revokeToken } =
    useTokenMutations(reload)

  // Token erbt hoechstens die eigene Rolle (Snapshot, ADR-0023). Die Rolle ist
  // unabhaengig von der Tool-Policy des Agenten: sie gated REST-Mutationen,
  // die Policy scopt die Reads/Writes des gebundenen Agenten.
  const currentRole = useCurrentWorkspaceRole()
  const roleOptions = currentRole !== null ? rolesAtMost(currentRole) : []
  const [roleOverride, setRoleOverride] = useState<WorkspaceRole | null>(null)
  const [expiresAt, setExpiresAt] = useState('')
  const role = roleOverride ?? currentRole

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  const form = useForm<TokenValues>({
    resolver: zodResolver(tokenSchema),
    defaultValues: { name: '' },
  })

  async function onCreate(values: TokenValues) {
    const input: TokenInput =
      currentRole !== null && role !== null
        ? { name: values.name, role, agent_id: agentId }
        : { name: values.name, agent_id: agentId }
    // Datum (YYYY-MM-DD) → Ende des Tages in UTC; leer = kein Ablauf.
    if (expiresAt !== '') input.expires_at = new Date(`${expiresAt}T23:59:59Z`).toISOString()
    const result = await createToken(input)
    if (result !== null) {
      form.reset({ name: '' })
      setExpiresAt('')
    }
  }

  async function saveRename(id: string) {
    if (editName.trim() === '') {
      return
    }
    const ok = await renameToken(id, editName.trim())
    if (ok) {
      setEditingId(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('agentSection.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Stack gap="md">
          <p className="text-sm text-muted-foreground">{t('agentSection.description')}</p>

          <DataList
            items={tokens}
            loading={loading}
            error={error}
            getKey={(token) => token.id}
            renderItem={(token) => {
              const isRevoked = token.revoked_at !== null
              const isEditing = editingId === token.id
              return (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <Stack gap="xs">
                    {isEditing ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Input
                          value={editName}
                          aria-label={t('rename.ariaLabel')}
                          onChange={(event) => setEditName(event.target.value)}
                        />
                        <Button
                          type="button"
                          size="sm"
                          variant="brand"
                          onClick={() => void saveRename(token.id)}
                        >
                          {t('common:actions.save')}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => setEditingId(null)}
                        >
                          {t('common:actions.cancel')}
                        </Button>
                      </div>
                    ) : (
                      <div className="font-medium">{token.name}</div>
                    )}
                    <div className="text-xs text-muted-foreground">
                      {t('list.createdAt', { date: token.created_at })}
                      {token.last_used_at !== null
                        ? t('list.lastUsed', { date: token.last_used_at })
                        : ''}
                      {isRevoked ? t('list.revoked', { date: token.revoked_at ?? '' }) : ''}
                    </div>
                  </Stack>
                  {!isEditing ? (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isRevoked}
                        onClick={() => {
                          setEditingId(token.id)
                          setEditName(token.name)
                        }}
                      >
                        {t('rename.action')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isRevoked}
                        onClick={() => void rotateToken(token.id)}
                      >
                        {t('rotate.action')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={isRevoked}
                        onClick={() => void revokeToken(token.id)}
                      >
                        {t('list.revoke')}
                      </Button>
                    </div>
                  ) : null}
                </div>
              )
            }}
          />

          {revealed !== null ? (
            <TokenSecretReveal token={revealed.token} onDismiss={dismissRevealed} />
          ) : null}

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
                  <Label htmlFor="agent-token-role">{t('create.roleLabel')}</Label>
                  <Select
                    id="agent-token-role"
                    value={role}
                    onChange={(event) => setRoleOverride(event.target.value as WorkspaceRole)}
                  >
                    {roleOptions.map((option) => (
                      <option key={option} value={option}>
                        {roleLabel(option)}
                      </option>
                    ))}
                  </Select>
                  <p className="text-xs text-muted-foreground">{t('create.roleHint')}</p>
                </div>
              ) : null}
              <div className="flex flex-col gap-2">
                <Label htmlFor="agent-token-expires">{t('create.expiresLabel')}</Label>
                <Input
                  id="agent-token-expires"
                  type="date"
                  value={expiresAt}
                  onChange={(event) => setExpiresAt(event.target.value)}
                />
                <p className="text-xs text-muted-foreground">{t('create.expiresHint')}</p>
              </div>
              {createError !== null ? <ErrorAlert message={createError} /> : null}
              <div className="flex justify-end">
                <Button type="submit" variant="brand" disabled={form.formState.isSubmitting}>
                  {t('create.submit')}
                </Button>
              </div>
            </form>
          </Form>
        </Stack>
      </CardContent>
    </Card>
  )
}
