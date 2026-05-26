import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { useSession } from '@/auth/session-context'

const loginSchema = z.object({
  email: z.string().email('Bitte gueltige E-Mail eingeben.'),
  password: z.string().min(1, 'Passwort erforderlich.'),
})

type LoginValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const { session, signIn } = useSession()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  if (session !== null) {
    return <Navigate to="/" replace />
  }

  async function onSubmit(values: LoginValues) {
    setError(null)
    try {
      await signIn(values.email, values.password)
      navigate('/')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Login fehlgeschlagen.')
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            <h1 className="text-2xl font-semibold tracking-tight">Who2Be — Anmeldung</h1>
          </CardTitle>
          <CardDescription>Melde dich mit deinem Supabase-Account an.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>E-Mail</FormLabel>
                    <FormControl>
                      <Input type="email" autoComplete="email" required {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Passwort</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="current-password"
                        required
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
                Anmelden
              </Button>
              {error !== null ? <ErrorAlert message={error} /> : null}
            </form>
          </Form>
        </CardContent>
      </Card>
    </main>
  )
}
