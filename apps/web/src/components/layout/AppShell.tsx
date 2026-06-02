import {
  BookOpen,
  Bot,
  FileText,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings,
  Users,
} from 'lucide-react'
import type { ComponentType, ReactNode, SVGProps } from 'react'
import { NavLink } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { cn } from '@/lib/utils'

import { WorkspaceSwitcher } from './WorkspaceSwitcher'

interface AppShellProps {
  children: ReactNode
  onSignOut: () => void
}

interface NavItem {
  to: string
  label: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

// „Einstellungen" bündelt die drei Spaces (Konto / Organisation / Workspace)
// plus Mitglieder + API-Tokens; die Aufteilung übernimmt die `SettingsNav` in
// der Settings-Sektion. Einstiegspunkt ist der User-Space (Konto).
const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/system-prompts', label: 'System-Prompts', icon: ScrollText },
  { to: '/personas', label: 'Personae', icon: Users },
  { to: '/playbooks', label: 'Playbooks', icon: BookOpen },
  { to: '/resources', label: 'Resources', icon: FileText },
  { to: '/settings/account', label: 'Einstellungen', icon: Settings },
]

export function AppShell({ children, onSignOut }: AppShellProps) {
  const wsPath = useWorkspacePath()
  const navItems = NAV_ITEMS
  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-muted/40 px-3 py-4 sm:flex">
        <div className="px-2 pb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Who2Be
        </div>
        <div className="pb-3">
          <WorkspaceSwitcher />
        </div>
        <nav aria-label="Hauptnavigation" className="flex flex-1 flex-col gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={wsPath(item.to)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
                  isActive && 'bg-accent text-accent-foreground',
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b px-4 sm:px-6">
          <nav aria-label="Hauptnavigation (mobil)" className="flex items-center gap-3 sm:hidden">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={wsPath(item.to)}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-1 text-sm font-medium text-muted-foreground ring-offset-background hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
                    isActive && 'text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={onSignOut}>
              <LogOut className="h-4 w-4" />
              Abmelden
            </Button>
          </div>
        </header>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  )
}
