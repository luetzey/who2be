import type { ReactNode } from 'react'

import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { cn } from '@/lib/utils'

interface DataListProps<T> {
  items: T[]
  renderItem: (item: T) => ReactNode
  getKey: (item: T) => string
  loading?: boolean
  error?: string | null
  empty?: ReactNode
  className?: string
}

export function DataList<T>({
  items,
  renderItem,
  getKey,
  loading,
  error,
  empty,
  className,
}: DataListProps<T>) {
  if (loading) {
    return <LoadingState />
  }
  if (error) {
    return <ErrorAlert message={error} />
  }
  if (items.length === 0) {
    return empty ? <>{empty}</> : <EmptyState title="Keine Einträge." />
  }
  return (
    <ul
      className={cn(
        'divide-y rounded-lg border border-border/40 bg-card shadow-card',
        className,
      )}
    >
      {items.map((item) => (
        <li key={getKey(item)} className="px-4 py-3 text-sm">
          {renderItem(item)}
        </li>
      ))}
    </ul>
  )
}
