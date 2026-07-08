import { zodResolver } from '@hookform/resolvers/zod'
import { Check } from 'lucide-react'
import { Suspense, lazy, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import i18n from '@/i18n'

import type { MeOrganization } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { useWorkspaceId } from '@/auth/useWorkspaceId'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { FormSection } from '@/components/layout/FormSection'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { notify } from '@/lib/feedback'
import { roleLabel } from '@/lib/roles'

import { useCurrentOrg } from '../hooks/useCurrentOrg'

// Build-Zeit-Isolation (ADR-0029): Im On-Prem-Build ist `__CLOUD_BUILD__` das
// Literal `false`, sodass der dynamische Import im toten Ternary-Zweig vom
// Bundler eliminiert wird — `features/billing` (inkl. Mollie-/Tarif-Interna)
// landet dann nicht im ausgelieferten JS. Nur der Cloud-Build laedt das Panel.
const BillingPanel = __CLOUD_BUILD__
  ? lazy(() => import('@/features/billing').then((m) => ({ default: m.BillingPanel })))
  : null

const workspaceSchema = z.object({
  name: z.string().min(1, i18n.t('common:validation.nameRequired')).max(200),
  slug: z
    .string()
    .min(1, i18n.t('common:validation.slugRequired'))
    .max(64)
    .regex(/^[a-z0-9-]+$/, i18n.t('common:validation.slugInvalid')),
})

type WorkspaceValues = z.infer<typeof workspaceSchema>

function describeError(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

// Org-Space (Track C): Organisation-Einstellungen — Workspaces (inkl. Anlage,
// Fix für den toten "Workspace hinzufügen"-Button), Org-Metadaten und der
// Billing-Slot, den Track D füllt.
export function OrgSettingsPage() {
  const { t } = useTranslation('settings')
  const api = useApi()
  const { refreshMe } = useSession()
  const current = useCurrentOrg()
  const wsPath = useWorkspacePath()
  const activeWorkspaceId = useWorkspaceId()

  const form = useForm<WorkspaceValues>({
    resolver: zodResolver(workspaceSchema),
    defaultValues: { name: '', slug: '' },
  })

  if (current === null) {
    return (
      <Container>
        <Stack gap="lg">
          <PageHeader title={t('org.title')} description={t('org.loading')} />
        </Stack>
      </Container>
    )
  }

  const { org } = current
  const isAdmin = current.workspace.role === 'admin'

  async function onCreateWorkspace(values: WorkspaceValues) {
    try {
      const created = await api.createWorkspace(org.id, values)
      notify.success(t('org.workspaces.createdToast', { name: created.name }))
      form.reset({ name: '', slug: '' })
      await refreshMe()
    } catch (cause) {
      notify.error(describeError(cause, t('org.actionFailed')))
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('org.title')}
          description={t('org.description')}
        />

        <Card>
          <CardHeader>
            <CardTitle>{t('org.masterData.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">{t('org.masterData.name')}</dt>
              <dd className="font-medium">{org.name}</dd>
              <dt className="text-muted-foreground">{t('org.masterData.slug')}</dt>
              <dd className="font-mono text-xs text-muted-foreground">{org.slug}</dd>
              <dt className="text-muted-foreground">{t('org.masterData.type')}</dt>
              <dd>
                <Badge variant="secondary">
                  {org.kind === 'personal' ? t('org.masterData.personal') : t('org.masterData.company')}
                </Badge>
              </dd>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('org.workspaces.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Stack gap="md">
              <ul className="divide-y rounded-md border">
                {org.workspaces.map((ws) => {
                  const active = ws.id === activeWorkspaceId
                  return (
                    <li
                      key={ws.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        {active ? (
                          <Check className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                        ) : null}
                        <span className="truncate font-medium">{ws.name}</span>
                        <Badge variant="outline">{roleLabel(ws.role)}</Badge>
                      </div>
                      <Button asChild variant="ghost" size="sm">
                        <Link to={`/w/${ws.id}/dashboard`}>{t('org.workspaces.openButton')}</Link>
                      </Button>
                    </li>
                  )
                })}
              </ul>

              {isAdmin ? (
                <Form {...form}>
                  <form onSubmit={form.handleSubmit(onCreateWorkspace)}>
                    <FormSection
                      title={t('org.workspaces.addTitle')}
                      description={t('org.workspaces.addDescription')}
                    >
                      <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t('org.workspaces.nameLabel')}</FormLabel>
                            <FormControl>
                              <Input required {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="slug"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>{t('org.workspaces.slugLabel')}</FormLabel>
                            <FormControl>
                              <Input required placeholder={t('org.workspaces.slugPlaceholder')} {...field} />
                            </FormControl>
                            <FormDescription>
                              {t('org.workspaces.slugDescription')}
                            </FormDescription>
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
                          {t('org.workspaces.createButton')}
                        </Button>
                      </div>
                    </FormSection>
                  </form>
                </Form>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {t('org.workspaces.adminOnly')}
                </p>
              )}
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('org.members.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {t('org.members.descriptionPrefix')}{' '}
              <Link to={wsPath('/settings/members')} className="underline underline-offset-4">
                {t('org.members.linkLabel')}
              </Link>
              {t('org.members.descriptionSuffix')}
            </p>
          </CardContent>
        </Card>

        {/* Billing-Slot: nur im Cloud-Build vorhanden (Build-Zeit-Isolation,
            ADR-0029). Im On-Prem-Bundle ist BillingPanel `null` und der Code
            wird wegge-tree-shaked. Wrapper haelt die testid stabil. */}
        <div data-testid="billing-slot">
          {BillingPanel ? (
            <Suspense fallback={null}>
              <BillingPanel />
            </Suspense>
          ) : null}
        </div>

        {org.kind === 'company' && isAdmin ? <DeleteOrgSection org={org} /> : null}
      </Stack>
    </Container>
  )
}

// Danger-Zone (Track O): Org-Löschung mit 30-Tage-Grace. Nur der Org-Owner darf
// das wirklich — das Backend enforced es (403 → Toast); hier zeigen wir den
// Eintrag für Company-Org-Admins, Personal-Orgs laufen über die Konto-Löschung.
function DeleteOrgSection({ org }: { org: MeOrganization }) {
  const { t } = useTranslation('settings')
  const api = useApi()
  const { refreshMe } = useSession()
  const navigate = useNavigate()
  const [confirm, setConfirm] = useState('')
  const [pending, setPending] = useState(false)
  const confirmMatches = confirm === org.name

  async function onDelete() {
    setPending(true)
    try {
      await api.deleteOrganization(org.id)
      notify.success(t('org.dangerZone.deletedToast', { name: org.name }))
      await refreshMe()
      navigate('/', { replace: true })
    } catch (cause) {
      setPending(false)
      notify.error(cause instanceof Error ? cause.message : t('org.dangerZone.errorFallback'))
    }
  }

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle className="text-destructive">{t('org.dangerZone.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Stack gap="sm">
          <p className="text-sm text-muted-foreground">
            {t('org.dangerZone.description')}
          </p>
          <Dialog
            onOpenChange={(open) => {
              if (!open) {
                setConfirm('')
              }
            }}
          >
            <DialogTrigger asChild>
              <Button variant="destructive">{t('org.dangerZone.triggerButton')}</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('org.dangerZone.dialogTitle')}</DialogTitle>
                <DialogDescription>
                  {t('org.dangerZone.dialogDescription', { name: org.name })}
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-2">
                <Label htmlFor="confirm-org-name">{t('org.dangerZone.orgNameLabel')}</Label>
                <Input
                  id="confirm-org-name"
                  value={confirm}
                  autoComplete="off"
                  onChange={(event) => setConfirm(event.target.value)}
                />
              </div>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">{t('common:actions.cancel')}</Button>
                </DialogClose>
                <Button
                  variant="destructive"
                  disabled={!confirmMatches || pending}
                  onClick={() => void onDelete()}
                >
                  {t('org.dangerZone.confirmButton')}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Stack>
      </CardContent>
    </Card>
  )
}
