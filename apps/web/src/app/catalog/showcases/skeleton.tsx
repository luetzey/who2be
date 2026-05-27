import { Skeleton } from '@/components/ui/skeleton'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

export function SkeletonShowcase() {
  return (
    <ShowcaseSection
      id="skeleton"
      title="Skeleton"
      description="Platzhalter waehrend Lade-States. Hauptkonsument: LoadingState."
    >
      <ShowcaseRow label="Bloecke">
        <div className="flex w-full max-w-md flex-col gap-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </ShowcaseRow>
      <ShowcaseRow label="Avatar + Text">
        <div className="flex w-full max-w-md items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
