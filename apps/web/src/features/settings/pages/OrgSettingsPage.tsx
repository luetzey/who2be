import { zodResolver } from '@hookform/resolvers/zod'
import { Check } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'

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
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { notify } from '@/lib/feedback'
import { roleLabel } from '@/lib/roles'

import { useCurrentOrg } from '../hooks/useCurrentOrg'

const workspaceSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.').max(200),
  slug: z
    .string()
    .min(1, 'Slug erforderlich.')
    .max(64)
    .regex(/^[a-z0-9-]+$/, 'Nur Kleinbuchstaben, Ziffern und Bindestriche.'),
})

type WorkspaceValues = z.infer<typeof workspaceSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Aktion fehlgeschlagen.'
}

// Org-Space (Track C): Organisation-Einstellungen — Workspaces (inkl. Anlage,
// Fix für den toten "Workspace hinzufügen"-Button), Org-Metadaten und der
// Billing-Slot, den Track D füllt.
export function OrgSettingsPage() {
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
          <PageHeader title="Organisation" description="Wird geladen…" />
        </Stack>
      </Container>
    )
  }

  const { org } = current
  const isAdmin = current.workspace.role === 'admin'

  async function onCreateWorkspace(values: WorkspaceValues) {
    try {
      const created = await api.createWorkspace(org.id, values)
      notify.success(`Workspace „${created.name}“ angelegt.`)
      form.reset({ name: '', slug: '' })
      await refreshMe()
    } catch (cause) {
      notify.error(describeError(cause))
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Organisation"
          description="Workspaces, Stammdaten und Abrechnung dieser Organisation."
        />

        <Card>
          <CardHeader>
            <CardTitle>Stammdaten</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">Name</dt>
              <dd className="font-medium">{org.name}</dd>
              <dt className="text-muted-foreground">Slug</dt>
              <dd className="font-mono text-xs text-muted-foreground">{org.slug}</dd>
              <dt className="text-muted-foreground">Typ</dt>
              <dd>
                <Badge variant="secondary">
                  {org.kind === 'personal' ? 'Persönlich' : 'Organisation'}
                </Badge>
              </dd>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Workspaces</CardTitle>
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
                          <Check className="size-4 shrink-0 text-brand" aria-hidden="true" />
                        ) : null}
                        <span className="truncate font-medium">{ws.name}</span>
                        <Badge variant="outline">{roleLabel(ws.role)}</Badge>
                      </div>
                      <Button asChild variant="ghost" size="sm">
                        <Link to={`/w/${ws.id}/dashboard`}>Öffnen</Link>
                      </Button>
                    </li>
                  )
                })}
              </ul>

              {isAdmin ? (
                <Form {...form}>
                  <form onSubmit={form.handleSubmit(onCreateWorkspace)}>
                    <FormSection
                      title="Workspace hinzufügen"
                      description="Ein neuer Workspace gruppiert eigene Personae, Playbooks und Tokens."
                    >
                      <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Name</FormLabel>
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
                            <FormLabel>Slug</FormLabel>
                            <FormControl>
                              <Input required placeholder="z.B. marketing" {...field} />
                            </FormControl>
                            <FormDescription>
                              Eindeutig innerhalb der Organisation, in der URL verwendet.
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
                          Workspace anlegen
                        </Button>
                      </div>
                    </FormSection>
                  </form>
                </Form>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Nur Admins können in dieser Organisation Workspaces anlegen.
                </p>
              )}
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Mitglieder</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Mitglieder werden pro Workspace verwaltet — Rollen, Einladungen und
              Entfernen findest du unter{' '}
              <Link to={wsPath('/settings/members')} className="underline underline-offset-4">
                Mitglieder
              </Link>
              .
            </p>
          </CardContent>
        </Card>

        {/* Billing-Slot (Track D füllt ihn: Entitlement-/Quota-Anzeige + Upgrade-CTA;
            On-Prem blendet ihn aus). Hier bewusst nur ein leerer Platzhalter. */}
        <Card data-testid="billing-slot">
          <CardHeader>
            <CardTitle>Abrechnung</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Plan- und Nutzungsdetails erscheinen hier, sobald die Abrechnung
              aktiviert ist.
            </p>
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}
