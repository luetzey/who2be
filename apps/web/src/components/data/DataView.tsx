import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

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
  emptyTitle,
  emptyDescription,
  emptyAction,
  loadingRows,
  children,
}: DataViewProps) {
  const { t } = useTranslation('data')
  if (loading) {
    return <LoadingState rows={loadingRows} />
  }
  if (error) {
    return <ErrorAlert message={error} />
  }
  if (empty) {
    return (
      <EmptyState
        title={emptyTitle ?? t('empty')}
        description={emptyDescription}
        action={emptyAction}
      />
    )
  }
  return <>{children}</>
}
