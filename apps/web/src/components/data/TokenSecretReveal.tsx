import { Copy, KeyRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Stack } from '@/components/layout/Stack'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { copyToClipboard } from '@/lib/clipboard'
import { notify } from '@/lib/feedback'

interface TokenSecretRevealProps {
  /** Der Klartext-Token (aus Create oder Rotate) — wird nur einmal angezeigt. */
  token: string
  onDismiss: () => void
}

/**
 * Einmalige Klartext-Anzeige eines frisch erzeugten/rotierten Tokens mit
 * Copy-Button. Bewusst feature-agnostisch (nur `@/components/ui/*`), damit es
 * von der Agent-Token-Sektion und anderswo wiederverwendbar ist.
 */
export function TokenSecretReveal({ token, onDismiss }: TokenSecretRevealProps) {
  const { t } = useTranslation('tokens')
  return (
    <Alert role="status">
      <KeyRound />
      <AlertTitle>{t('reveal.title')}</AlertTitle>
      <AlertDescription>
        <Stack gap="sm">
          <p>{t('reveal.body')}</p>
          <Textarea
            readOnly
            aria-label={t('reveal.ariaLabel')}
            value={token}
            rows={2}
            onFocus={(event) => event.currentTarget.select()}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="brand"
              size="sm"
              onClick={() => {
                void copyToClipboard(token).catch((cause: unknown) => {
                  const message =
                    cause instanceof Error ? cause.message : t('common:error.generic')
                  notify.error(message)
                })
              }}
            >
              <Copy className="h-4 w-4" />
              {t('reveal.copyButton')}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onDismiss}>
              {t('common:actions.close')}
            </Button>
          </div>
        </Stack>
      </AlertDescription>
    </Alert>
  )
}
