import { Skeleton } from '@/components/ui/skeleton'

interface LoadingStateProps {
  rows?: number
}

export function LoadingState({ rows = 3 }: LoadingStateProps) {
  return (
    <div className="space-y-2" aria-live="polite" aria-busy="true">
      <span className="sr-only">Lädt…</span>
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  )
}
