import { ChevronDown } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function DropdownShowcase() {
  return (
    <ShowcaseSection
      id="dropdown"
      title="Dropdown-Menu"
      description="Kontext-Menue fuer Aktionen mit niedrigerer Prioritaet. Radix-basiert, Keyboard-navigierbar."
    >
      <ShowcaseRow label="Trigger">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">
              Aktionen
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Persona</DropdownMenuLabel>
            <DropdownMenuItem>Duplizieren</DropdownMenuItem>
            <DropdownMenuItem>Versions-Diff</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">Loeschen</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
