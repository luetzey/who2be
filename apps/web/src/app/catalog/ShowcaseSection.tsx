import type { ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface ShowcaseSectionProps {
  id: string
  title: string
  description?: string
  children: ReactNode
}

export function ShowcaseSection({ id, title, description, children }: ShowcaseSectionProps) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20">
      <Card>
        <CardHeader>
          <CardTitle id={`${id}-title`}>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </CardHeader>
        <CardContent className="flex flex-col gap-6">{children}</CardContent>
      </Card>
    </section>
  )
}

interface ShowcaseRowProps {
  label?: string
  children: ReactNode
}

export function ShowcaseRow({ label, children }: ShowcaseRowProps) {
  return (
    <div className="flex flex-col gap-2">
      {label ? (
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {label}
        </span>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  )
}
