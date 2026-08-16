import { FolderOpen, Network, Search } from 'lucide-react'
import type { ComponentType, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { cn } from '@/lib/utils'

interface WorkAreaNavItem {
  to: string
  labelKey: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
  /** Nur die Bereichs-Liste ist die Index-Route und braucht `end`. */
  end?: boolean
}

// Sub-Navigation des Arbeitsbereichs (Muster `SettingsNav`). Die Suche steht
// bewusst gleichrangig neben der Bereichs-Liste: fuer Menschen wie fuer Agenten
// ist sie der eigentliche Einstieg — die Liste ist Bestandsuebersicht.
const ITEMS: WorkAreaNavItem[] = [
  { to: '/workarea', labelKey: 'nav.areas', icon: FolderOpen, end: true },
  { to: '/workarea/search', labelKey: 'nav.search', icon: Search },
  { to: '/workarea/kb', labelKey: 'nav.kb', icon: Network },
]

export function WorkAreaNav() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  return (
    <nav aria-label={t('nav.label')} className="flex flex-wrap gap-1 border-b pb-px">
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={wsPath(item.to)}
          end={item.end}
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
