import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'

// Rechtliche Pflicht-Links. Bewusst hier (Layout-Ebene) gehalten, damit der
// Footer ohne Kopplung an das `legal`-Feature ueberall (auch ausgeloggt)
// gerendert werden kann. Pfade spiegeln die Routes in `app/routes.tsx`.
const LEGAL_LINKS = [
  { to: '/legal/impressum', labelKey: 'footer.impressum' },
  { to: '/legal/agb', labelKey: 'footer.terms' },
  { to: '/legal/datenschutz', labelKey: 'footer.privacy' },
  { to: '/legal/dpa', labelKey: 'footer.dpa' },
] as const

export function Footer({ className }: { className?: string }) {
  const { t } = useTranslation('layout')
  const year = new Date().getFullYear()
  return (
    <footer className={cn('border-t bg-muted/30', className)}>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p className="text-xs text-muted-foreground">© {year} {t('brand')}</p>
        <nav aria-label={t('footer.legal')} className="flex flex-wrap gap-x-4 gap-y-2">
          {LEGAL_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              {t(link.labelKey)}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  )
}
