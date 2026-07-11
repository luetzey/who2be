import { Link } from 'react-router-dom'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'

import { AlertShowcase } from './showcases/alert'
import { BadgeShowcase } from './showcases/badge'
import { ButtonShowcase } from './showcases/button'
import { CardShowcase } from './showcases/card'
import { CardsShowcase } from './showcases/cards'
import { CheckboxShowcase } from './showcases/checkbox'
import { DataShowcase } from './showcases/data'
import { DialogShowcase } from './showcases/dialog'
import { DropdownShowcase } from './showcases/dropdown'
import { FormShowcase } from './showcases/form'
import { FormSectionShowcase } from './showcases/form-section'
import { InfoTooltipShowcase } from './showcases/info-tooltip'
import { InputShowcase } from './showcases/input'
import { LabelShowcase } from './showcases/label'
import { LayoutShowcase } from './showcases/layout'
import { SelectShowcase } from './showcases/select'
import { SkeletonShowcase } from './showcases/skeleton'
import { TableShowcase } from './showcases/table'
import { TabsShowcase } from './showcases/tabs'
import { TextareaShowcase } from './showcases/textarea'

interface NavEntry {
  id: string
  label: string
}

const NAV_ENTRIES: readonly NavEntry[] = [
  { id: 'button', label: 'Button' },
  { id: 'input', label: 'Input' },
  { id: 'textarea', label: 'Textarea' },
  { id: 'label', label: 'Label' },
  { id: 'select', label: 'Select' },
  { id: 'checkbox', label: 'Checkbox' },
  { id: 'card', label: 'Card' },
  { id: 'badge', label: 'Badge' },
  { id: 'alert', label: 'Alert' },
  { id: 'dialog', label: 'Dialog' },
  { id: 'dropdown', label: 'Dropdown' },
  { id: 'form', label: 'Form' },
  { id: 'form-section', label: 'FormSection' },
  { id: 'info-tooltip', label: 'InfoTooltip' },
  { id: 'tabs', label: 'Tabs' },
  { id: 'skeleton', label: 'Skeleton' },
  { id: 'table', label: 'Table' },
  { id: 'layout', label: 'Layout' },
  { id: 'data', label: 'Data' },
  { id: 'cards', label: 'Cards' },
]

export function CatalogPage() {
  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Component-Catalog"
          description="DEV-only Showcase aller UI-, Layout- und Data-Komponenten. Single Source of Truth fuer den Frontend-Standards-Stack."
        />
        <nav aria-label="Catalog-Navigation" className="rounded-md border bg-muted/30 p-4">
          <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            {NAV_ENTRIES.map((entry) => (
              <li key={entry.id}>
                <Link
                  to={`#${entry.id}`}
                  className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {entry.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <ButtonShowcase />
        <InputShowcase />
        <TextareaShowcase />
        <LabelShowcase />
        <SelectShowcase />
        <CheckboxShowcase />
        <CardShowcase />
        <BadgeShowcase />
        <AlertShowcase />
        <DialogShowcase />
        <DropdownShowcase />
        <FormShowcase />
        <FormSectionShowcase />
        <InfoTooltipShowcase />
        <TabsShowcase />
        <SkeletonShowcase />
        <TableShowcase />
        <LayoutShowcase />
        <DataShowcase />
        <CardsShowcase />
      </Stack>
    </Container>
  )
}
