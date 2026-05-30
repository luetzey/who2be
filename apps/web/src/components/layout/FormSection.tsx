import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'

import { InfoTooltip } from '@/components/ui/info-tooltip'
import { cn } from '@/lib/utils'

export interface FormSectionProps extends HTMLAttributes<HTMLElement> {
  title: string
  /** Ein-Satz-Beschreibung unter dem Titel. Mehrzeilige Tipps gehen ueber `help`. */
  description?: string
  /** Erweiterte Hilfe — wird im Tooltip neben dem Titel gerendert. */
  help?: ReactNode
  footer?: ReactNode
}

/**
 * Gruppiert Felder in Editor-Forms (siehe design-language.md §9.5).
 * Title + optional Description in der Section-Spitze; Children sind die
 * Felder; optional ein Footer mit kleiner Microcopy ("Aenderungen ...").
 * Visuelle Abtrennung zur vorigen Section via `border-t pt-6` — die
 * erste Section in einem Container braucht `first:border-t-0 first:pt-0`.
 */
export const FormSection = forwardRef<HTMLElement, FormSectionProps>(function FormSection(
  { title, description, help, footer, className, children, ...props },
  ref,
) {
  return (
    <section
      ref={ref}
      className={cn(
        'flex flex-col gap-4 border-t pt-6 first:border-t-0 first:pt-0',
        className,
      )}
      {...props}
    >
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          {help !== undefined ? <InfoTooltip>{help}</InfoTooltip> : null}
        </div>
        {description !== undefined ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <div className="flex flex-col gap-4">{children}</div>
      {footer !== undefined ? (
        <p className="text-xs text-muted-foreground">{footer}</p>
      ) : null}
    </section>
  )
})
