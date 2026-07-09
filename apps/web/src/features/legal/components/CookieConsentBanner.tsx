import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

import { useCookieConsent } from '../hooks/useCookieConsent'
import { Placeholder } from './Placeholder'

/**
 * Cookie-Consent-Banner (Opt-in). Erscheint global, solange keine Entscheidung
 * getroffen wurde. „Nur notwendige" lehnt optionales Tracking ab, „Alle
 * akzeptieren" willigt ein — bis dahin laeuft **kein** Tracking. Der Banner
 * blockiert die App nicht (kein Modal), bleibt aber sichtbar bis zur Wahl.
 */
export function CookieConsentBanner() {
  const { isDecided, accept, reject } = useCookieConsent()
  const { t } = useTranslation('legal')

  if (isDecided) {
    return null
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4">
      <Card
        role="region"
        aria-label={t('cookie.regionLabel')}
        className="pointer-events-auto flex w-full max-w-2xl flex-col gap-4 p-4 shadow-modal sm:flex-row sm:items-center"
      >
        <div className="flex-1 space-y-1">
          <p className="text-sm font-medium">{t('cookie.title')}</p>
          <p className="text-sm text-muted-foreground">
            {t('cookie.body')}{' '}
            <Placeholder>{t('cookie.bodyServices')}</Placeholder>
            {') '}
            {t('cookie.bodyEnd')}{' '}
            <Link
              to="/legal/datenschutz"
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              {t('cookie.privacyLink')}
            </Link>
            .
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={reject}>
            {t('cookie.rejectButton')}
          </Button>
          <Button variant="brand" size="sm" onClick={accept}>
            {t('cookie.acceptButton')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
