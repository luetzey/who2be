import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

interface PlaybookLinkItemProps {
  id: string
  name: string
  checked: boolean
  onToggle: () => void
}

/**
 * Listen-Eintrag fuer die Persona-Playbook-Verknuepfung. Trennt Checkbox
 * und Label sauber via `htmlFor`/`id` (statt rohem `<label>`-Wrap), damit
 * jsx-a11y und axe-Probes gleichermassen zufrieden sind.
 */
export function PlaybookLinkItem({ id, name, checked, onToggle }: PlaybookLinkItemProps) {
  const inputId = `playbook-link-${id}`
  return (
    <li className="flex items-center gap-2 text-sm">
      <Checkbox id={inputId} checked={checked} onChange={onToggle} />
      <Label htmlFor={inputId}>{name}</Label>
    </li>
  )
}
