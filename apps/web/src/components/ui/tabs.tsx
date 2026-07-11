import {
  createContext,
  useContext,
  useId,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'

import { cn } from '@/lib/utils'

// Underline-Tab-Leiste fuer die Detail-Pages (Design-Handoff „Detail-Redesign").
// Kein Radix-Tabs im Stack (siehe package.json) — daher ein leichtgewichtiges,
// zugaengliches Set: ARIA-Tabs-Pattern (tablist/tab/tabpanel, aria-selected,
// roving tabindex, Pfeil-/Home-/End-Navigation), aktiver 2px-Brand-Unterstrich.
// Kontrolliert (`value`) oder unkontrolliert (`defaultValue`).

interface TabsContextValue {
  value: string
  setValue: (value: string) => void
  baseId: string
}

const TabsContext = createContext<TabsContextValue | null>(null)

function useTabsContext(): TabsContextValue {
  const context = useContext(TabsContext)
  if (context === null) {
    throw new Error('Tabs-Unterkomponenten muessen innerhalb von <Tabs> stehen.')
  }
  return context
}

interface TabsProps {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
  className?: string
  children: ReactNode
}

export function Tabs({ value, defaultValue, onValueChange, className, children }: TabsProps) {
  const baseId = useId()
  const [internalValue, setInternalValue] = useState(defaultValue ?? '')
  const isControlled = value !== undefined
  const currentValue = isControlled ? value : internalValue

  const setValue = (next: string) => {
    if (!isControlled) {
      setInternalValue(next)
    }
    onValueChange?.(next)
  }

  return (
    <TabsContext.Provider value={{ value: currentValue, setValue, baseId }}>
      <div className={cn('flex flex-col gap-6', className)}>{children}</div>
    </TabsContext.Provider>
  )
}

interface TabsListProps {
  children: ReactNode
  className?: string
  'aria-label'?: string
}

export function TabsList({ children, className, ...props }: TabsListProps) {
  return (
    <div role="tablist" className={cn('flex gap-1 border-b', className)} {...props}>
      {children}
    </div>
  )
}

// Pfeiltasten-Navigation liegt bewusst auf den Tab-Buttons (nicht dem tablist-
// Container) — der Container bleibt so nicht-fokussierbar (roving tabindex,
// Muster wie PlaybookDetailTabs). Aktivierung folgt dem Fokus.
function handleTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
  if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) {
    return
  }
  const list = event.currentTarget.closest<HTMLElement>('[role="tablist"]')
  if (list === null) {
    return
  }
  const tabs = Array.from(
    list.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])'),
  )
  if (tabs.length === 0) {
    return
  }
  event.preventDefault()
  const activeIndex = tabs.findIndex((tab) => tab === event.currentTarget)
  let nextIndex: number
  if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = tabs.length - 1
  } else {
    const delta = event.key === 'ArrowRight' ? 1 : -1
    const base = activeIndex === -1 ? 0 : activeIndex
    nextIndex = (base + delta + tabs.length) % tabs.length
  }
  const next = tabs[nextIndex]
  next.focus()
  next.click()
}

interface TabsTriggerProps {
  value: string
  children: ReactNode
  disabled?: boolean
  className?: string
}

export function TabsTrigger({ value, children, disabled, className }: TabsTriggerProps) {
  const { value: current, setValue, baseId } = useTabsContext()
  const selected = current === value
  return (
    <button
      type="button"
      role="tab"
      id={`${baseId}-tab-${value}`}
      aria-selected={selected}
      aria-controls={`${baseId}-panel-${value}`}
      tabIndex={selected ? 0 : -1}
      disabled={disabled}
      onClick={() => setValue(value)}
      onKeyDown={handleTriggerKeyDown}
      className={cn(
        'relative inline-flex h-11 items-center justify-center gap-2 rounded-none px-4 text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-[var(--duration-medium)] ease-standard focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
        selected ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
    >
      {children}
      {selected ? (
        <span
          className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand"
          aria-hidden="true"
        />
      ) : null}
    </button>
  )
}

interface TabsContentProps {
  value: string
  children: ReactNode
  className?: string
}

export function TabsContent({ value, children, className }: TabsContentProps) {
  const { value: current, baseId } = useTabsContext()
  if (current !== value) {
    return null
  }
  return (
    <div
      role="tabpanel"
      id={`${baseId}-panel-${value}`}
      aria-labelledby={`${baseId}-tab-${value}`}
      tabIndex={0}
      className={cn('focus-visible:outline-none', className)}
    >
      {children}
    </div>
  )
}
