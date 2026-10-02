import { zodResolver } from '@hookform/resolvers/zod'
import { Copy } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import type { Invitation, Member, WorkspaceRole } from '@/api/types'
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
import { useIsMobile } from '@/hooks/useMediaQuery'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'
import { isDowngrade, ROLE_ORDER, roleLabel } from '@/lib/roles'

import { useInvitations } from '../hooks/useInvitations'
import { useMembers } from '../hooks/useMembers'

const inviteSchema = z.object({
  email: z.string().email({ error: () => i18n.t('common:validation.emailInvalid') }),
  role: z.enum(['admin', 'editor', 'viewer']),
})

type InviteValues = z.infer<typeof inviteSchema>

function describeError(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

// Der Token steht im URL-Fragment, nie im Pfad oder in einer Query: das
// Fragment verlässt den Browser nicht, landet also in keinem Server- oder
// Proxy-Log. Die Accept-Seite liest es per URLSearchParams und schickt den
// Token im Body an POST /v1/invitations/accept.
function acceptUrl(token: string): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  return `${origin}/invitations/accept#${new URLSearchParams({ token }).toString()}`
}

interface MemberListItemProps {
  member: Member
  onChangeRole: (userId: string, currentRole: WorkspaceRole, nextRole: WorkspaceRole) => Promise<void>
  onRemove: (userId: string) => Promise<void>
}

/**
 * Mitglied als Listenzeile (W5=a, nur unter md). Prioritaetsfelder stehen
 * immer da: der Name — die E-Mail, ein eigenes Namensfeld hat `Member` nicht —
 * und die Rolle samt Auswahl, weil Rolle aendern die haeufigste Aktion ist.
 * Beitrittsdatum und das destruktive Entfernen liegen hinter dem Aufklapper;
 * so steht „Entfernen“ nicht direkt neben der Rollenauswahl im Daumenbereich.
 *
 * Der Aufklapper nutzt die gemeinsamen Texte `common:actions.showMore/Less`;
 * welches Mitglied gemeint ist, sagt `aria-describedby` auf den Namen. Ein
 * eigenes `aria-label` wuerde den sichtbaren Text verdecken (WCAG 2.5.3).
 */
function MemberListItem({ member, onChangeRole, onRemove }: MemberListItemProps) {
  const { t } = useTranslation('settings')
  const [open, setOpen] = useState(false)
  const nameId = useId()
  const detailsId = useId()
  const name = member.email ? member.email : member.user_id

  return (
    <li className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span id={nameId} className="min-w-0 flex-1 basis-40 font-medium wrap-anywhere">
          {name}
        </span>
        <Select
          aria-label={t('members.list.roleAriaLabel', { email: member.email })}
          className="w-auto min-w-32"
          value={member.role}
          onChange={(event) =>
            void onChangeRole(member.user_id, member.role, event.target.value as WorkspaceRole)
          }
        >
          {ROLE_ORDER.map((option) => (
            <option key={option} value={option}>
              {roleLabel(option)}
            </option>
          ))}
        </Select>
      </div>
      <Button
        type="button"
        variant="link"
        className="min-h-11 self-start px-0"
        aria-expanded={open}
        aria-controls={detailsId}
        aria-describedby={nameId}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? t('common:actions.showLess') : t('common:actions.showMore')}
      </Button>
      <div
        id={detailsId}
        hidden={!open}
        className="flex flex-wrap items-center justify-between gap-3"
      >
        <dl className="flex gap-2 text-sm">
          <dt className="text-muted-foreground">{t('members.list.colJoined')}</dt>
          <dd>{new Date(member.joined_at).toLocaleDateString()}</dd>
        </dl>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          className="h-10"
          onClick={() => void onRemove(member.user_id)}
        >
          {t('members.list.removeButton')}
        </Button>
      </div>
    </li>
  )
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
  const isMobile = useIsMobile()
  const listTitleId = useId()

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
    void copyToClipboard(acceptUrl(token))
      .then(() => notify.success(t('members.invitations.copiedToast')))
      .catch((cause: unknown) => {
        const message = cause instanceof Error ? cause.message : t('common:error.generic')
        notify.error(message)
      })
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
            <CardTitle id={listTitleId}>{t('members.list.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <DataView
              loading={members.loading}
              error={members.error}
              empty={!members.loading && members.members.length === 0}
              emptyTitle={t('members.list.emptyTitle')}
              emptyDescription={t('members.list.emptyDescription')}
            >
              {isMobile ? (
                // W5=a (Mobil-Spec M11): unter md keine Tabelle, sondern eine
                // Liste mit Prioritaetsfeldern — Name (E-Mail) und Rolle
                // sichtbar, Beitritt und Entfernen hinter „Mehr anzeigen“.
                // Gemessen war die Tabelle bei 320 px nur 238 von 619 px
                // sichtbar (innerer Querscroller).
                <ul
                  className="flex flex-col divide-y divide-border"
                  aria-labelledby={listTitleId}
                  data-testid="members-list"
                >
                  {members.members.map((member) => (
                    <MemberListItem
                      key={member.user_id}
                      member={member}
                      onChangeRole={onChangeRole}
                      onRemove={onRemove}
                    />
                  ))}
                </ul>
              ) : (
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
                          className="min-w-32"
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
              )}
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
                    <Stack gap="xs" className="min-w-0">
                      <div className="font-medium break-all">{invitation.email}</div>
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
