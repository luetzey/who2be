import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { config } from '@/config'

// "Wir arbeiten noch"-Hinweisseite (Issue #429, WHO2BE_LAUNCH_MODE=coming_soon).
// Ersetzt das Signup-Formular auf `/signup`, solange der Launch-Modus aktiv
// ist — siehe der Gate in `SignupPage.tsx`. Folgt dem Marketing-Page-Pattern
// aus docs/frontend/design-language.md §10.2, mit einem echten `<h1>` statt
// `CardTitle` (das rendert ein `<h2>`) — die a11y-Anforderung verlangt genau
// eine H1 auf dieser Seite.
export function ComingSoonPage() {
  const { t } = useTranslation('auth')
  const contact = config.launchContact

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md border-transparent shadow-modal">
        <CardHeader className="gap-2">
          <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            {t('brand')}
          </span>
          <h1 className="text-3xl font-semibold tracking-tight">{t('comingSoon.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('comingSoon.body')}</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {contact !== '' ? (
            <p className="text-center text-sm text-muted-foreground">
              {t('comingSoon.contact')}{' '}
              <Button asChild variant="link" className="h-auto p-0 align-baseline">
                <Link to={`mailto:${contact}`}>{contact}</Link>
              </Button>
            </p>
          ) : null}
          <Button asChild variant="brand" className="w-full">
            <Link to="/login">{t('backToLogin')}</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}
