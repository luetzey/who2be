import { Suspense } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'

import { Footer } from '@/components/layout/Footer'
import { cn } from '@/lib/utils'

/** Navigation zwischen den Rechtsseiten innerhalb der Legal-Shell. */
const LEGAL_NAV = [
  { to: '/legal/impressum', label: 'Impressum' },
  { to: '/legal/agb', label: 'AGB' },
  { to: '/legal/datenschutz', label: 'Datenschutz' },
  { to: '/legal/dpa', label: 'Auftragsverarbeitung (DPA)' },
] as const

/**
 * Oeffentliche Shell fuer alle `/legal/*`-Seiten — bewusst ohne Auth-Gate und
 * ohne `AppShell`, damit Impressum/Datenschutz auch ausgeloggt erreichbar sind.
 */
export function LegalLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-3 px-4 py-4 sm:px-6">
          <div className="flex items-center justify-between">
            <Link to="/" className="text-sm font-semibold tracking-tight">
              Who2Be
            </Link>
            <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Rechtliches
            </span>
          </div>
          <nav aria-label="Rechtliche Seiten" className="flex flex-wrap gap-x-4 gap-y-1">
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
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">Wird geladen…</div>
          }
        >
          <Outlet />
        </Suspense>
      </main>
      <Footer />
    </div>
  )
}
