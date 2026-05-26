import type { ReactNode } from 'react'

import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'

interface DataViewProps {
  loading?: boolean
  error?: string | null
  empty?: boolean
  emptyTitle?: string
  emptyDescription?: string
  emptyAction?: ReactNode
  loadingRows?: number
  children: ReactNode
}

export function DataView({
  loading,
  error,
  empty,
  emptyTitle = 'Keine Eintraege.',
  emptyDescription,
  emptyAction,
  loadingRows,
  children,
}: DataViewProps) {
  if (loading) {
    return <LoadingState rows={loadingRows} />
  }
  if (error) {
    return <ErrorAlert message={error} />
  }
  if (empty) {
    return (
      <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
    )
  }
  return <>{children}</>
}
