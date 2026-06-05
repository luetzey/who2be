import { zodResolver } from '@hookform/resolvers/zod'
import { Copy } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import type { Invitation, WorkspaceRole } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { FormSection } from '@/components/layout/FormSection'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { notify } from '@/lib/feedback'
import { isDowngrade, ROLE_ORDER, roleLabel } from '@/lib/roles'

import { useInvitations } from '../hooks/useInvitations'
import { useMembers } from '../hooks/useMembers'

const inviteSchema = z.object({
  email: z.string().email(i18n.t('common:validation.emailInvalid')),
  role: z.enum(['admin', 'editor', 'viewer']),
})

type InviteValues = z.infer<typeof inviteSchema>

function describeError(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

function acceptUrl(token: string): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  return `${origin}/invitations/${token}/accept`
}

export function MembersPage() {
  const { t } = useTranslation('settings')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const wsPath = useWorkspacePath()
  const members = useMembers()
  const invitations = useInvitations()
  // Klartext-Token der in dieser Sitzung erstellten Invitations — das Backend
  // liefert ihn nur einmal bei der Erstellung (Hash-only, ADR-0023).
  const [issuedTokens, setIssuedTokens] = useState<Record<string, string>>({})

  const isBlocked = role === 'editor' || role === 'viewer'

  useEffect(() => {
    if (isBlocked) {
      notify.error(t('members.adminOnly'))
    }
  }, [isBlocked, t])

  const form = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: '', role: 'editor' },
  })

  if (isBlocked) {
    return <Navigate to={wsPath('/dashboard')} replace />
  }

  async function onInvite(values: InviteValues) {
    try {
      const created = await api.createInvitation(values)
      if (created.token !== undefined && created.token !== null) {
        setIssuedTokens((prev) => ({ ...prev, [created.id]: created.token as string }))
      }
      notify.success(t('members.invite.sentToast', { email: values.email }))
      form.reset({ email: '', role: 'editor' })
      invitations.reload()
    } catch (cause) {
      notify.error(describeError(cause, t('members.invite.actionFailed')))
    }
  }

  async function onChangeRole(
    userId: string,
    currentRole: WorkspaceRole,
    nextRole: WorkspaceRole,
  ) {
    if (nextRole === currentRole) {
      return
    }
    try {
      await api.updateMemberRole(userId, { role: nextRole })
      notify.success(t('members.list.roleUpdatedToast'))
      // ADR-0023: Token tragen einen Rollen-Snapshot. Ein Downgrade des
      // Mitglieds entzieht dessen bestehenden Tokens NICHT automatisch die
      // höheren Rechte — die müssen explizit widerrufen werden.
      if (isDowngrade(currentRole, nextRole)) {
        notify.info(t('members.list.tokenDowngradeInfo'))
      }
      members.reload()
    } catch (cause) {
      notify.error(describeError(cause, t('members.invite.actionFailed')))
    }
  }

  async function onRemove(userId: string) {
    try {
      await api.removeMember(userId)
      notify.success(t('members.list.removedToast'))
      members.reload()
    } catch (cause) {
      notify.error(describeError(cause, t('members.invite.actionFailed')))
    }
  }

  async function onRevoke(id: string) {
    try {
      await api.revokeInvitation(id)
      notify.success(t('members.invitations.revokedToast'))
      invitations.reload()
    } catch (cause) {
      notify.error(describeError(cause, t('members.invite.actionFailed')))
    }
  }

  function tokenFor(invitation: Invitation): string | null {
    return issuedTokens[invitation.id] ?? invitation.token ?? null
  }

  function copyLink(token: string) {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(acceptUrl(token))
      notify.success(t('members.invitations.copiedToast'))
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('members.title')}
          description={t('members.description')}
        />

        <Card>
          <CardHeader>
            <CardTitle>{t('members.list.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <DataView
              loading={members.loading}
              error={members.error}
              empty={!members.loading && members.members.length === 0}
              emptyTitle={t('members.list.emptyTitle')}
              emptyDescription={t('members.list.emptyDescription')}
            >
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('members.list.colEmail')}</TableHead>
                    <TableHead>{t('members.list.colRole')}</TableHead>
                    <TableHead>{t('members.list.colJoined')}</TableHead>
                    <TableHead className="text-right">{t('members.list.colActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.members.map((member) => (
                    <TableRow key={member.user_id}>
                      <TableCell className="font-medium">
                        {member.email ? member.email : member.user_id}
                      </TableCell>
                      <TableCell>
                        <Select
                          aria-label={t('members.list.roleAriaLabel', { email: member.email })}
                          value={member.role}
                          onChange={(event) =>
                            void onChangeRole(
                              member.user_id,
                              member.role,
                              event.target.value as WorkspaceRole,
                            )
                          }
                        >
                          {ROLE_ORDER.map((option) => (
                            <option key={option} value={option}>
                              {roleLabel(option)}
                            </option>
                          ))}
                        </Select>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(member.joined_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          type="button"
                          variant="destructive"
                          size="sm"
                          onClick={() => void onRemove(member.user_id)}
                        >
                          {t('members.list.removeButton')}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </DataView>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('members.invite.cardTitle')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onInvite)}>
                <FormSection
                  title={t('members.invite.sectionTitle')}
                  description={t('members.invite.sectionDescription')}
                  footer={t('members.invite.sectionFooter')}
                >
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('members.invite.emailLabel')}</FormLabel>
                        <FormControl>
                          <Input type="email" autoComplete="off" required {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="role"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('members.invite.roleLabel')}</FormLabel>
                        <FormControl>
                          <Select {...field}>
                            {ROLE_ORDER.map((option) => (
                              <option key={option} value={option}>
                                {roleLabel(option)}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="flex justify-end">
                    <Button
                      type="submit"
                      variant="brand"
                      disabled={form.formState.isSubmitting}
                    >
                      {t('members.invite.inviteButton')}
                    </Button>
                  </div>
                </FormSection>
              </form>
            </Form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('members.invitations.cardTitle')}</CardTitle>
          </CardHeader>
          <CardContent>
            <DataList
              items={invitations.invitations}
              loading={invitations.loading}
              error={invitations.error}
              getKey={(invitation) => invitation.id}
              renderItem={(invitation) => {
                const token = tokenFor(invitation)
                return (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Stack gap="xs">
                      <div className="font-medium">{invitation.email}</div>
                      <div className="text-xs text-muted-foreground">
                        {roleLabel(invitation.role)} · {t('members.invitations.expiresLabel')}{' '}
                        {new Date(invitation.expires_at).toLocaleDateString()}
                      </div>
                    </Stack>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={token === null}
                        title={
                          token === null
                            ? t('members.invitations.copyDisabledTitle')
                            : undefined
                        }
                        onClick={() => {
                          if (token !== null) {
                            copyLink(token)
                          }
                        }}
                      >
                        <Copy className="h-4 w-4" />
                        {t('members.invitations.copyButton')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void onRevoke(invitation.id)}
                      >
                        {t('members.invitations.revokeButton')}
                      </Button>
                    </div>
                  </div>
                )
              }}
              empty={
                <p className="text-sm text-muted-foreground">
                  {t('members.invitations.empty')}
                </p>
              }
            />
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}
