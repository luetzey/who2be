import { Building2, Settings2, User, Users } from 'lucide-react'
import type { ComponentType, SVGProps } from 'react'
import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { cn } from '@/lib/utils'

interface SettingsNavItem {
  to: string
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  adminOnly?: boolean
}

// Sub-Navigation der drei Spaces (Konto / Organisation / Workspace) plus den
// Workspace-internen Bereich Mitglieder (admin-only, ADR-0023). API-Tokens
// werden direkt am Agenten verwaltet (kein eigener Settings-Eintrag mehr).
const ITEMS: SettingsNavItem[] = [
  { to: '/settings/account', labelKey: 'nav.account', icon: User },
  { to: '/settings/org', labelKey: 'nav.org', icon: Building2 },
  { to: '/settings/workspace', labelKey: 'nav.workspace', icon: Settings2 },
  { to: '/settings/members', labelKey: 'nav.members', icon: Users, adminOnly: true },
]

export function SettingsNav() {
  const { t } = useTranslation('settings')
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const items = ITEMS.filter((item) => !item.adminOnly || role === 'admin')
  return (
    <nav
      aria-label={t('nav.ariaLabel')}
      className="flex flex-wrap gap-1 border-b pb-px"
    >
      {items.map((item) => (
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
          {t(item.labelKey)}
        </NavLink>
      ))}
    </nav>
  )
}
