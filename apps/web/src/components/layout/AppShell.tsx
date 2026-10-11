import {
  Bell,
  BookOpen,
  Bot,
  Brain,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Plug,
  ScrollText,
  Settings,
  Users,
} from 'lucide-react'
import { useId, useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, useMatch } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { LanguageSwitcher } from '@/components/ui/language-switcher'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { useInboxCounts } from '@/hooks/useInboxCounts'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/utils'

import { Footer } from './Footer'
import { WorkspaceSwitcher } from './WorkspaceSwitcher'

interface AppShellProps {
  children: ReactNode
  onSignOut: () => void
}

interface NavItem {
  to: string
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

interface NavGroup {
  /** Stabiler Schluessel fuer `data-testid` und Ueberschrift-IDs. */
  id: string
  /** Ohne Ueberschrift: Einstieg oben (Dashboard, Agents) und Settings unten. */
  labelKey?: string
  items: NavItem[]
}

// Audit E2-B: die Navigation zeigt, dass ein Agent AUS Bausteinen besteht —
// Gruppen mit Eyebrow-Ueberschrift statt zehn gleichrangiger Eintraege.
// Eine Quelle fuer Sidebar UND Phone-Sheet; Routen bleiben unveraendert.
const NAV_GROUPS: NavGroup[] = [
  {
    id: 'main',
    items: [
      { to: '/dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard },
      { to: '/agents', labelKey: 'nav.agents', icon: Bot },
    ],
  },
  {
    id: 'building-blocks',
    labelKey: 'nav.groups.buildingBlocks',
    items: [
      { to: '/system-prompts', labelKey: 'nav.systemPrompts', icon: ScrollText },
      { to: '/personas', labelKey: 'nav.personas', icon: Users },
      { to: '/playbooks', labelKey: 'nav.playbooks', icon: BookOpen },
      { to: '/resources', labelKey: 'nav.resources', icon: FileText },
      { to: '/tools', labelKey: 'nav.tools', icon: Plug },
    ],
  },
  {
    id: 'operations',
    labelKey: 'nav.groups.operations',
    items: [
      // ADR-0047: der Arbeitsbereich steht bewusst NEBEN den Resources, nicht
      // darin — hier liegt unversioniertes Agenten-Rohmaterial, dort kuratierte
      // und veroeffentlichte Inhalte.
      { to: '/workarea', labelKey: 'nav.workarea', icon: FolderOpen },
      { to: '/feedback', labelKey: 'nav.feedback', icon: MessageSquare },
      { to: '/memory', labelKey: 'nav.memory', icon: Brain },
    ],
  },
  {
    // „Einstellungen" bündelt die drei Spaces (Konto / Organisation /
    // Workspace) plus Mitglieder + API-Tokens; die Aufteilung übernimmt die
    // `SettingsNav` in der Settings-Sektion. Einstiegspunkt ist der
    // User-Space (Konto).
    id: 'settings',
    items: [{ to: '/settings/account', labelKey: 'nav.settings', icon: Settings }],
  },
]

// Ab hier zeigt die Glocke „99+“ statt der Zahl (Spec §2.3).
const BELL_MAX = 99

/**
 * Glocke in der Kopfleiste (Navigation W1, Spec §2.3, Weiche N2 a): ein Link
 * auf die Seite „Zu erledigen“, kein Popover. Der Zaehler ist `total` aus
 * `useInboxCounts`; bei 0, beim Laden und bei einem Fehler steht kein Zaehler
 * da (nie eine behauptete „0“), der Link funktioniert immer. Die Zahl ist
 * `aria-hidden` — vorgelesen wird sie einmal, im `aria-label`.
 */
function InboxBell() {
  const { t } = useTranslation('layout')
  const wsPath = useWorkspacePath()
  const to = wsPath('/inbox')
  const active = useMatch({ path: to, end: true }) !== null
  const { counts } = useInboxCounts()
  const total = counts?.total ?? null
  const label =
    total === null ? t('inbox.label') : t('inbox.bell', { count: total })
  return (
    <Button
      asChild
      variant="ghost"
      size="icon"
      className={cn(
        'relative h-11 w-11 md:h-9 md:w-9',
        active && 'bg-accent text-accent-foreground',
      )}
    >
      <Link
        to={to}
        aria-label={label}
        aria-current={active ? 'page' : undefined}
        data-testid="inbox-bell"
      >
        <Bell className="h-5 w-5" aria-hidden="true" />
        {total !== null && total > 0 && (
          <span
            aria-hidden="true"
            data-testid="inbox-bell-count"
            className="absolute top-1 left-1/2 ml-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1 text-[0.6875rem] leading-none font-semibold text-brand-foreground tabular-nums md:-top-1 md:-right-1 md:left-auto md:ml-0"
          >
            {total > BELL_MAX ? `${BELL_MAX}+` : total}
          </span>
        )}
      </Link>
    </Button>
  )
}

export function AppShell({ children, onSignOut }: AppShellProps) {
  const { t } = useTranslation('layout')
  const wsPath = useWorkspacePath()
  const navGroups = NAV_GROUPS
  const idPrefix = useId()
  const isMobile = useIsMobile()
  const [navSheetOpen, setNavSheetOpen] = useState(false)

  // Sichtbarkeit von Sidebar vs. Sheet-Trigger laeuft ausschliesslich ueber
  // CSS-Klassen (`hidden md:flex` / `md:hidden`) — `useIsMobile()` steuert
  // hier bewusst nur *Verhalten*: waechst das Viewport waehrend das Sheet
  // offen ist ueber die `md`-Schwelle (Resize, DevTools-Rotation), schliesst
  // es sich automatisch, statt parallel zur nun sichtbaren Sidebar offen zu
  // bleiben (Designsprache §4.4, ADR-lose Vorgabe aus Issue #500).
  //
  // Bewusst kein `useEffect`: das waere ein Lehrbuch-Fall von
  // "Adjusting state when a prop changes" (react.dev), das
  // `react-hooks/set-state-in-effect` zu Recht anmeckert (setState
  // synchron im Effect-Body). Stattdessen der von React empfohlene
  // Render-Zeit-Vergleich gegen den zuletzt gesehenen Wert.
  const [prevIsMobile, setPrevIsMobile] = useState(isMobile)
  if (isMobile !== prevIsMobile) {
    setPrevIsMobile(isMobile)
    if (!isMobile) {
      setNavSheetOpen(false)
    }
  }

  // Screenreader-Struktur: je Gruppe eine Liste; betitelte Gruppen tragen eine
  // h2-Eyebrow (design-language §3.3/§3.4), die die Liste per
  // `aria-labelledby` benennt. Sidebar und Sheet stehen gleichzeitig im DOM
  // (Sichtbarkeit per CSS), deshalb bekommt jede Flaeche ein eigenes
  // ID-Praefix — doppelte IDs wuerden `aria-labelledby` falsch aufloesen.
  const renderNavGroups = (surface: 'sidebar' | 'sheet', onNavigate?: () => void) =>
    navGroups.map((group) => {
      const headingId = group.labelKey ? `${idPrefix}-${surface}-${group.id}` : undefined
      return (
        <div key={group.id} className="flex flex-col gap-1">
          {group.labelKey && (
            <h2
              id={headingId}
              className="px-3 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase"
            >
              {t(group.labelKey)}
            </h2>
          )}
          <ul
            aria-labelledby={headingId}
            data-testid={`nav-group-${group.id}`}
            className="flex flex-col gap-1"
          >
            {group.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={wsPath(item.to)}
                  onClick={onNavigate}
                  data-testid={`nav-link-${item.labelKey.replace('nav.', '')}`}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
                      isActive && 'bg-accent text-accent-foreground',
                    )
                  }
                >
                  <item.icon className="h-4 w-4" aria-hidden="true" />
                  {t(item.labelKey)}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      )
    })

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-muted/40 px-3 py-4 md:flex">
        <div className="px-2 pb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t('brand')}
        </div>
        <div className="pb-3">
          <WorkspaceSwitcher />
        </div>
        <nav
          aria-label={t('nav.primary')}
          data-testid="app-nav-sidebar"
          className="flex flex-1 flex-col gap-4"
        >
          {renderNavGroups('sidebar')}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b px-4 sm:px-6">
          <Sheet open={navSheetOpen} onOpenChange={setNavSheetOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden"
                data-testid="app-nav-open"
                aria-label={t('nav.openMenu')}
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            {/* `overscroll-contain`: Am Ende der Navigation laeuft der
                Wisch nicht in die Seite dahinter weiter (Scroll-Chaining,
                Mobil-Spec „Nav-Sheet“). */}
            <SheetContent side="left" className="overflow-y-auto overscroll-contain">
              <SheetHeader>
                <SheetTitle>{t('brand')}</SheetTitle>
                <SheetDescription className="sr-only">
                  {t('nav.menuDescription')}
                </SheetDescription>
              </SheetHeader>
              <div className="pb-3">
                <WorkspaceSwitcher />
              </div>
              <nav
                aria-label={t('nav.primary')}
                data-testid="app-nav-sheet"
                className="flex flex-1 flex-col gap-4"
              >
                {renderNavGroups('sheet', () => setNavSheetOpen(false))}
              </nav>
            </SheetContent>
          </Sheet>
          <div className="ml-auto flex items-center gap-2">
            <InboxBell />
            <LanguageSwitcher />
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={onSignOut}>
              <LogOut className="h-4 w-4" />
              {t('signOut')}
            </Button>
          </div>
        </header>
        <main className="min-w-0 flex-1">{children}</main>
        <Footer />
      </div>
    </div>
  )
}
