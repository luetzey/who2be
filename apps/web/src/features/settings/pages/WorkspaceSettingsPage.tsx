import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { useWorkspaceId } from '@/auth/useWorkspaceId'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { FormSection } from '@/components/layout/FormSection'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { notify } from '@/lib/feedback'

import { useCurrentOrg } from '../hooks/useCurrentOrg'

const renameSchema = z.object({
  name: z.string().min(1, i18n.t('common:validation.nameRequired')).max(200),
})

type RenameValues = z.infer<typeof renameSchema>

function describeError(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

// Workspace-Space (Track C): Settings (Umbenennen), Verweis auf Mitglieder und
// die Danger-Zone (Löschen). Mutationen sind admin-only; das Backend enforced
// zusätzlich und schützt den letzten Workspace einer Organisation.
export function WorkspaceSettingsPage() {
  const { t } = useTranslation('settings')
  const api = useApi()
  const { me, refreshMe } = useSession()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const workspaceId = useWorkspaceId()
  const current = useCurrentOrg()

  const [confirmName, setConfirmName] = useState('')
  const [deleting, setDeleting] = useState(false)

  const form = useForm<RenameValues>({
    resolver: zodResolver(renameSchema),
    values: { name: current?.workspace.name ?? '' },
  })

  if (current === null || me === null) {
    return (
      <Container>
        <Stack gap="lg">
          <PageHeader title={t('workspace.title')} description={t('workspace.loading')} />
        </Stack>
      </Container>
    )
  }

  const { org, workspace } = current
  const isAdmin = workspace.role === 'admin'
  const isLastWorkspace = org.workspaces.length <= 1
  const confirmMatches = confirmName === workspace.name

  async function onRename(values: RenameValues) {
    try {
      await api.renameWorkspace(workspaceId, { name: values.name })
      notify.success(t('workspace.general.renamedToast'))
      await refreshMe()
    } catch (cause) {
      notify.error(describeError(cause, t('workspace.actionFailed')))
    }
  }

  function pickFallbackWorkspace(): string | null {
    for (const o of me!.organizations) {
      for (const ws of o.workspaces) {
        if (ws.id !== workspaceId) {
          return ws.id
        }
      }
    }
    return null
  }

  async function onDelete() {
    setDeleting(true)
    try {
      await api.deleteWorkspace(workspaceId)
      notify.success(t('workspace.dangerZone.deletedToast'))
      const fallback = pickFallbackWorkspace()
      await refreshMe()
      navigate(fallback !== null ? `/w/${fallback}/dashboard` : '/', { replace: true })
    } catch (cause) {
      notify.error(describeError(cause, t('workspace.dangerZone.errorFallback')))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('workspace.title')}
          description={t('workspace.description')}
        />

        <Card>
          <CardHeader>
            <CardTitle>{t('workspace.general.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            {isAdmin ? (
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onRename)}>
                  <FormSection
                    title={t('workspace.general.renameTitle')}
                    description={t('workspace.general.renameDescription')}
                  >
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>{t('workspace.general.nameLabel')}</FormLabel>
                          <FormControl>
                            <Input required {...field} />
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
                        {t('workspace.general.saveButton')}
                      </Button>
                    </div>
                  </FormSection>
                </form>
              </Form>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('workspace.general.adminOnly')}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('workspace.members.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {t('workspace.members.descriptionPrefix')}{' '}
              <Link to={wsPath('/settings/members')} className="underline underline-offset-4">
                {t('workspace.members.linkLabel')}
              </Link>
              {t('workspace.members.descriptionSuffix')}
            </p>
          </CardContent>
        </Card>

        {isAdmin ? (
          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive">{t('workspace.dangerZone.title')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Stack gap="sm">
                <p className="text-sm text-muted-foreground">
                  {t('workspace.dangerZone.description')}
                </p>
                {isLastWorkspace ? (
                  <p className="text-sm text-muted-foreground">
                    {t('workspace.dangerZone.lastWorkspace')}
                  </p>
                ) : null}
                <Dialog
                  onOpenChange={(open) => {
                    if (!open) {
                      setConfirmName('')
                    }
                  }}
                >
                  <DialogTrigger asChild>
                    <Button variant="destructive" disabled={isLastWorkspace}>
                      {t('workspace.dangerZone.triggerButton')}
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{t('workspace.dangerZone.dialogTitle')}</DialogTitle>
                      <DialogDescription>
                        {t('workspace.dangerZone.dialogDescription', { name: workspace.name })}
                      </DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="confirm-workspace-name">{t('workspace.dangerZone.workspaceNameLabel')}</Label>
                      <Input
                        id="confirm-workspace-name"
                        value={confirmName}
                        autoComplete="off"
                        onChange={(event) => setConfirmName(event.target.value)}
                      />
                    </div>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline">{t('common:actions.cancel')}</Button>
                      </DialogClose>
                      <Button
                        variant="destructive"
                        disabled={!confirmMatches || deleting}
                        onClick={() => void onDelete()}
                      >
                        {t('workspace.dangerZone.confirmButton')}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </Stack>
            </CardContent>
          </Card>
        ) : null}
      </Stack>
    </Container>
  )
}
