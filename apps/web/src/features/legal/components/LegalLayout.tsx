import { Suspense } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Footer } from '@/components/layout/Footer'
import { cn } from '@/lib/utils'


/**
 * Oeffentliche Shell fuer alle `/legal/*`-Seiten — bewusst ohne Auth-Gate und
 * ohne `AppShell`, damit Impressum/Datenschutz auch ausgeloggt erreichbar sind.
 */
export function LegalLayout() {
  const { t } = useTranslation('legal')

  const LEGAL_NAV = [
    { to: '/legal/impressum', label: t('layout.nav.impressum') },
    { to: '/legal/agb', label: t('layout.nav.agb') },
    { to: '/legal/datenschutz', label: t('layout.nav.datenschutz') },
    { to: '/legal/dpa', label: t('layout.nav.dpa') },
  ] as const

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-3 px-4 py-4 sm:px-6">
          <div className="flex items-center justify-between">
            <Link to="/" className="text-sm font-semibold tracking-tight">
              {t('layout.brand')}
            </Link>
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {t('layout.legalLabel')}
            </span>
          </div>
          <nav aria-label={t('layout.nav.ariaLabel')} className="flex flex-wrap gap-x-4 gap-y-1">
            {LEGAL_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline',
                    isActive && 'font-medium text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Suspense
          fallback={
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">
              {t('layout.loading')}
            </div>
          }
        >
          <Outlet />
        </Suspense>
      </main>
      <Footer />
    </div>
  )
}
