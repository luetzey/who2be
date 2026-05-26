import { zodResolver } from '@hookform/resolvers/zod'
import { Copy, KeyRound } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

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
import { Textarea } from '@/components/ui/textarea'
import type { TokenCreated } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useAuthTokenContext } from '@/auth/auth-token-context'
import { useTokens } from '@/hooks/useTokens'
import { notify } from '@/lib/feedback'

const tokenSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
})

type TokenValues = z.infer<typeof tokenSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

function maskTail(token: string): string {
  return token.length <= 6 ? token : `…${token.slice(-6)}`
}

export function SettingsTokensPage() {
  const api = useApi()
  const { tokens, loading, error, reload } = useTokens()
  const { overrideToken, setOverrideToken } = useAuthTokenContext()

  const [createError, setCreateError] = useState<string | null>(null)
  const [created, setCreated] = useState<TokenCreated | null>(null)

  const [overrideInput, setOverrideInput] = useState('')

  const form = useForm<TokenValues>({
    resolver: zodResolver(tokenSchema),
    defaultValues: { name: '' },
  })

  async function onCreate(values: TokenValues) {
    setCreateError(null)
    try {
      const result = await api.createToken({ name: values.name })
      setCreated(result)
      form.reset({ name: '' })
      reload()
      notify.success(`Token „${values.name}" angelegt. Klartext jetzt einmalig kopieren.`)
    } catch (cause) {
      setCreateError(describeError(cause))
    }
  }

  async function handleRevoke(id: string) {
    try {
      await api.revokeToken(id)
      reload()
    } catch (cause) {
      notify.error(describeError(cause))
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
            title="API-Tokens"
            description="Persistente Tokens fuer Headless-Clients und Agents."
          />

          <Card>
            <CardHeader>
              <CardTitle>Vorhandene Tokens</CardTitle>
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
                          erstellt {token.created_at}
                          {token.last_used_at !== null
                            ? ` · zuletzt benutzt ${token.last_used_at}`
                            : ''}
                          {isRevoked ? ` · widerrufen ${token.revoked_at ?? ''}` : ''}
                        </div>
                      </Stack>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void handleRevoke(token.id)}
                        disabled={isRevoked}
                      >
                        Widerrufen
                      </Button>
                    </div>
                  )
                }}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Neuen Token anlegen</CardTitle>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onCreate)} className="flex flex-col gap-4">
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
                  {createError !== null ? <ErrorAlert message={createError} /> : null}
                  <div className="flex justify-end">
                    <Button type="submit" disabled={form.formState.isSubmitting}>
                      Anlegen
                    </Button>
                  </div>
                </form>
              </Form>
            </CardContent>
          </Card>

          {created !== null ? (
            <Alert role="status">
              <KeyRound />
              <AlertTitle>Neuer Token — jetzt kopieren</AlertTitle>
              <AlertDescription>
                <Stack gap="sm">
                  <p>
                    Der Klartext wird genau einmal angezeigt. Nach dem Schliessen ist er
                    nicht mehr abrufbar.
                  </p>
                  <Textarea
                    readOnly
                    aria-label="Klartext-Token"
                    value={created.token}
                    rows={2}
                    onFocus={(event) => event.currentTarget.select()}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => {
                        if (typeof navigator !== 'undefined' && navigator.clipboard) {
                          void navigator.clipboard.writeText(created.token)
                        }
                      }}
                    >
                      <Copy className="h-4 w-4" />
                      In Zwischenablage kopieren
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setCreated(null)}
                    >
                      Schliessen
                    </Button>
                  </div>
                </Stack>
              </AlertDescription>
            </Alert>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Headless-Token aktivieren</CardTitle>
            </CardHeader>
            <CardContent>
              <Stack gap="md">
                <p className="text-sm text-muted-foreground">
                  Override fuer kuenftige Headless-Use-Cases: Der eingegebene Token wird ab
                  sofort statt des Supabase-JWT an die API gesendet. Lebt nur in dieser
                  Tab-Sitzung — Reload entfernt ihn.
                </p>
                <p className="text-sm">
                  Status:{' '}
                  {overrideToken === null
                    ? 'kein Override (Supabase-JWT aktiv)'
                    : `Override aktiv (${maskTail(overrideToken)})`}
                </p>
                <form onSubmit={handleOverrideActivate} className="flex flex-col gap-3">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="override-token">w2b_-Token</Label>
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
                      Aktivieren
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setOverrideToken(null)}
                      disabled={overrideToken === null}
                    >
                      Override entfernen
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
