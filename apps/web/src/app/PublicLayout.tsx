import { Outlet } from 'react-router-dom'

import { LanguageSwitcher } from '@/components/ui/language-switcher'

/**
 * Shell fuer alle oeffentlichen Routen (`/login`, `/signup`,
 * `/reset-password`, `/auth/callback`, `/invitations/:token/accept`,
 * `/oauth/consent`, `/legal/*`) — Seiten, die auch ausgeloggt erreichbar
 * sind (WP1 von Issue #408). Analog zu `AppLayout`, aber ohne `AppShell`
 * (kein Nav/Sidebar) und ohne `ThemeProvider` (Theme betrifft eine andere
 * Achse als Sprache — s. Kommentar unten).
 *
 * Diese Seiten zentrieren ihre Karte selbst ueber `min-h-screen` (siehe
 * `LoginPage`/`OAuthConsentPage`); ein zusaetzlicher Flex-/Grid-Wrapper um
 * `<Outlet />` wuerde diese Zentrierung verschieben. Die Sprach-Insel sitzt
 * deshalb `fixed` (Viewport-relativ, kein umschliessendes Element noetig)
 * statt in einem Layout-Container neben dem Outlet.
 */
export function PublicLayout() {
  return (
    <>
      <div className="pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-end p-4">
        <div className="pointer-events-auto flex items-center gap-1 rounded-full border bg-popover p-1 text-popover-foreground shadow-popover">
          <LanguageSwitcher />
        </div>
      </div>
      <Outlet />
    </>
  )
}

// Bewusst OHNE ThemeToggle: `ThemeToggle` liest `useTheme()` aus
// `ThemeProvider`, das nur `AppLayout` mountet (Theme ist dort Teil der
// eingeloggten Produktoberflaeche). Ihn hier zusaetzlich zu zeigen wuerde ein
// eigenes `ThemeProvider` auf dieser Ebene erfordern — eine App-weite
// Theme-Entscheidung, die WP1 (nur Sprache oeffentlich erreichbar machen)
// nicht trifft. Ausserdem zeigt design-language.md fuer Marketing-Pages
// bisher gar keine Header-Toolbar (nur Brand-Eyebrow + Card) — die Insel hier
// ist bereits die erste Abweichung davon, und bleibt darum auf das Minimum
// beschraenkt, das das WP verlangt.
