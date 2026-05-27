import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function DialogShowcase() {
  return (
    <ShowcaseSection
      id="dialog"
      title="Dialog"
      description="Modale Bestaetigung fuer kritische Aktionen. Radix-basiert, fokussiert sich beim Oeffnen, esc/click-outside schliesst."
    >
      <ShowcaseRow label="Trigger">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="destructive">Token widerrufen</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Token wirklich widerrufen?</DialogTitle>
              <DialogDescription>
                Der Token wird sofort ungueltig. Diese Aktion ist nicht umkehrbar.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="ghost">Abbrechen</Button>
              </DialogClose>
              <Button variant="destructive">Widerrufen</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
