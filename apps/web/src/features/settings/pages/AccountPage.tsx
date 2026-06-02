import { Link } from 'react-router-dom'

import { useSession } from '@/auth/session-context'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ThemeToggle } from '@/components/ui/theme-toggle'

// User-Space (Track C): Konto-Einstellungen des eingeloggten Users — Profil,
// Sicherheit und Präferenzen. Bewusst lesend für die Identität (Quelle ist die
// Supabase-Session); Mutationen laufen über GoTrue-eigene Flows.
export function AccountPage() {
  const { session, me } = useSession()
  const email = session?.user?.email ?? '—'
  const userId = me?.user_id ?? session?.user?.id ?? '—'
  const hasPassword = me?.has_password ?? false

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Konto"
          description="Dein persönliches Profil, Sicherheit und Anzeige-Präferenzen."
        />

        <Card>
          <CardHeader>
            <CardTitle>Profil</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 text-sm sm:grid-cols-[8rem_1fr]">
              <dt className="text-muted-foreground">E-Mail</dt>
              <dd className="font-medium">{email}</dd>
              <dt className="text-muted-foreground">User-ID</dt>
              <dd className="font-mono text-xs break-all text-muted-foreground">{userId}</dd>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sicherheit</CardTitle>
          </CardHeader>
          <CardContent>
            <Stack gap="sm">
              <p className="text-sm text-muted-foreground">
                {hasPassword
                  ? 'Für dein Konto ist ein Passwort gesetzt.'
                  : 'Du bist per Magic-Link angemeldet. Setze ein Passwort, um dich auch ohne E-Mail-Link anmelden zu können.'}
              </p>
              <div>
                <Button asChild variant="outline" size="sm">
                  <Link to="/onboarding/set-password">
                    {hasPassword ? 'Passwort ändern' : 'Passwort setzen'}
                  </Link>
                </Button>
              </div>
            </Stack>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Präferenzen</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-4">
              <div className="text-sm">
                <div className="font-medium">Darstellung</div>
                <p className="text-muted-foreground">
                  Hell, Dunkel oder Systemvorgabe.
                </p>
              </div>
              <ThemeToggle />
            </div>
          </CardContent>
        </Card>
      </Stack>
    </Container>
  )
}
