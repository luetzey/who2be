import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

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
  name: z.string().min(1, 'Name erforderlich.').max(200),
})

type RenameValues = z.infer<typeof renameSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Aktion fehlgeschlagen.'
}

// Workspace-Space (Track C): Settings (Umbenennen), Verweis auf Mitglieder und
// die Danger-Zone (Löschen). Mutationen sind admin-only; das Backend enforced
// zusätzlich und schützt den letzten Workspace einer Organisation.
export function WorkspaceSettingsPage() {
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
          <PageHeader title="Workspace" description="Wird geladen…" />
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
      notify.success('Workspace umbenannt.')
      await refreshMe()
    } catch (cause) {
      notify.error(describeError(cause))
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
      notify.success('Workspace gelöscht.')
      const fallback = pickFallbackWorkspace()
      await refreshMe()
      navigate(fallback !== null ? `/w/${fallback}/dashboard` : '/', { replace: true })
    } catch (cause) {
      notify.error(describeError(cause))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Workspace"
          description="Einstellungen, Mitglieder und Danger-Zone dieses Workspaces."
        />

        <Card>
          <CardHeader>
            <CardTitle>Allgemein</CardTitle>
          </CardHeader>
          <CardContent>
            {isAdmin ? (
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onRename)}>
                  <FormSection
                    title="Workspace umbenennen"
                    description="Der angezeigte Name. Der Slug bleibt unverändert."
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
                    <div className="flex justify-end">
                      <Button
                        type="submit"
                        variant="brand"
                        disabled={form.formState.isSubmitting}
                      >
                        Speichern
                      </Button>
                    </div>
                  </FormSection>
                </form>
              </Form>
            ) : (
              <p className="text-sm text-muted-foreground">
                Nur Admins können diesen Workspace umbenennen.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Mitglieder</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Rollen, Einladungen und Entfernen findest du unter{' '}
              <Link to={wsPath('/settings/members')} className="underline underline-offset-4">
                Mitglieder
              </Link>
              .
            </p>
          </CardContent>
        </Card>

        {isAdmin ? (
          <Card className="border-destructive/40">
            <CardHeader>
              <CardTitle className="text-destructive">Danger-Zone</CardTitle>
            </CardHeader>
            <CardContent>
              <Stack gap="sm">
                <p className="text-sm text-muted-foreground">
                  Das Löschen entfernt den Workspace samt aller Personae, Playbooks,
                  Resources, Templates, Agenten und Tokens. Diese Aktion ist
                  unwiderruflich.
                </p>
                {isLastWorkspace ? (
                  <p className="text-sm text-muted-foreground">
                    Dies ist der letzte Workspace der Organisation und kann nicht
                    gelöscht werden.
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
                      Workspace löschen
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Workspace löschen</DialogTitle>
                      <DialogDescription>
                        Gib zur Bestätigung den Workspace-Namen „{workspace.name}“ ein.
                        Alle Inhalte gehen verloren.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="confirm-workspace-name">Workspace-Name</Label>
                      <Input
                        id="confirm-workspace-name"
                        value={confirmName}
                        autoComplete="off"
                        onChange={(event) => setConfirmName(event.target.value)}
                      />
                    </div>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline">Abbrechen</Button>
                      </DialogClose>
                      <Button
                        variant="destructive"
                        disabled={!confirmMatches || deleting}
                        onClick={() => void onDelete()}
                      >
                        Endgültig löschen
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
