import { forwardRef, useCallback, useRef, type TextareaHTMLAttributes } from 'react'

import { useAutoGrow } from '@/hooks/useAutoGrow'
import { cn } from '@/lib/utils'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  /**
   * Waechst mit dem Inhalt bis 60 % der kleinen Viewporthoehe (Mobil-Spec M5).
   * Erst darueber scrollt das Feld innen. `false` nur fuer Anzeigen mit fester
   * Hoehe (Token, Konfigurationsschnipsel).
   */
  autoGrow?: boolean
}

// `py-2` (2 x 0,5rem) plus `border` (2 x 1px): Die Mindesthoehe aus `rows`
// muss beides mitzaehlen, weil `box-sizing: border-box` gilt.
const FRAME = '1rem + 2px'

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, autoGrow = true, rows, style, ...props },
  ref,
) {
  const innerRef = useRef<HTMLTextAreaElement | null>(null)
  const setRef = useCallback(
    (node: HTMLTextAreaElement | null) => {
      innerRef.current = node
      if (typeof ref === 'function') ref(node)
      else if (ref !== null) ref.current = node
    },
    [ref],
  )
  useAutoGrow(innerRef, autoGrow, props.value)

  // `field-sizing: content` ignoriert `rows`. Damit `rows` Mindesthoehe
  // bleibt, steht sie als `min-height` in Zeilenhoehen (`lh`) am Feld; die
  // `min-h-20` der Klasse bleibt Untergrenze.
  const minHeight =
    autoGrow && rows !== undefined ? `max(5rem, calc(${rows}lh + ${FRAME}))` : undefined

  return (
    <textarea
      className={cn(
        'flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        autoGrow && 'field-sizing-content max-h-[60svh]',
        className,
      )}
      ref={setRef}
      rows={rows}
      style={minHeight === undefined ? style : { minHeight, ...style }}
      {...props}
    />
  )
})
