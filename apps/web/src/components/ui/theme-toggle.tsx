import { Monitor, Moon, Sun } from 'lucide-react'
import type { ComponentType, SVGProps } from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useTheme, type ThemePreference } from '@/app/theme-context'

interface ThemeOption {
  value: ThemePreference
  label: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

const OPTIONS: readonly ThemeOption[] = [
  { value: 'light', label: 'Hell', icon: Sun },
  { value: 'dark', label: 'Dunkel', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export function ThemeToggle() {
  const { preference, resolved, setPreference } = useTheme()
  const ActiveIcon = resolved === 'dark' ? Moon : Sun

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Theme umstellen"
          aria-haspopup="menu"
        >
          <ActiveIcon className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">Theme umstellen</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.value}
            onSelect={() => setPreference(option.value)}
            aria-checked={preference === option.value}
            role="menuitemradio"
          >
            <option.icon className="h-4 w-4" aria-hidden="true" />
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
