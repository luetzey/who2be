import {
  BookOpen,
  Bot,
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
import { useState, type ComponentType, type ReactNode, type SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

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

// „Einstellungen" bündelt die drei Spaces (Konto / Organisation / Workspace)
// plus Mitglieder + API-Tokens; die Aufteilung übernimmt die `SettingsNav` in
// der Settings-Sektion. Einstiegspunkt ist der User-Space (Konto).
const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/agents', labelKey: 'nav.agents', icon: Bot },
  { to: '/system-prompts', labelKey: 'nav.systemPrompts', icon: ScrollText },
  { to: '/personas', labelKey: 'nav.personas', icon: Users },
  { to: '/playbooks', labelKey: 'nav.playbooks', icon: BookOpen },
  { to: '/resources', labelKey: 'nav.resources', icon: FileText },
  { to: '/tools', labelKey: 'nav.tools', icon: Plug },
  // ADR-0047: der Arbeitsbereich steht bewusst NEBEN den Resources, nicht
  // darin — hier liegt unversioniertes Agenten-Rohmaterial, dort kuratierte
  // und veroeffentlichte Inhalte.
  { to: '/workarea', labelKey: 'nav.workarea', icon: FolderOpen },
  { to: '/feedback', labelKey: 'nav.feedback', icon: MessageSquare },
  { to: '/settings/account', labelKey: 'nav.settings', icon: Settings },
]

export function AppShell({ children, onSignOut }: AppShellProps) {
  const { t } = useTranslation('layout')
  const wsPath = useWorkspacePath()
  const navItems = NAV_ITEMS
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

  const renderNavLinks = (onNavigate?: () => void) =>
    navItems.map((item) => (
      <NavLink
        key={item.to}
        to={wsPath(item.to)}
        onClick={onNavigate}
        className={({ isActive }) =>
          cn(
            'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
            isActive && 'bg-accent text-accent-foreground',
          )
        }
      >
        <item.icon className="h-4 w-4" />
        {t(item.labelKey)}
      </NavLink>
    ))

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-muted/40 px-3 py-4 md:flex">
        <div className="px-2 pb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t('brand')}
        </div>
        <div className="pb-3">
          <WorkspaceSwitcher />
        </div>
        <nav aria-label={t('nav.primary')} className="flex flex-1 flex-col gap-1">
          {renderNavLinks()}
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
                aria-label={t('nav.openMenu')}
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="overflow-y-auto">
              <SheetHeader>
                <SheetTitle>{t('brand')}</SheetTitle>
                <SheetDescription className="sr-only">
                  {t('nav.menuDescription')}
                </SheetDescription>
              </SheetHeader>
              <div className="pb-3">
                <WorkspaceSwitcher />
              </div>
              <nav aria-label={t('nav.primary')} className="flex flex-1 flex-col gap-1">
                {renderNavLinks(() => setNavSheetOpen(false))}
              </nav>
            </SheetContent>
          </Sheet>
          <div className="ml-auto flex items-center gap-2">
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
