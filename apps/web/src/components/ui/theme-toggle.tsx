import { Monitor, Moon, Sun } from 'lucide-react'
import type { ComponentType, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'

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
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

// Beschriftung je Option unter `layout:theme.<value>` (Audit A9: vorher fest
// deutsch, auch in der englischen Oberflaeche).
const OPTIONS: readonly ThemeOption[] = [
  { value: 'light', icon: Sun },
  { value: 'dark', icon: Moon },
  { value: 'system', icon: Monitor },
]

export function ThemeToggle() {
  const { t } = useTranslation('layout')
  const { preference, resolved, setPreference } = useTheme()
  const ActiveIcon = resolved === 'dark' ? Moon : Sun

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label={t('theme.switch')}
          aria-haspopup="menu"
        >
          <ActiveIcon className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">{t('theme.switch')}</span>
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
            {t(`theme.${option.value}`)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
