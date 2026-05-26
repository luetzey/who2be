import { LoadingState } from '@/components/data/LoadingState'
import { Container } from '@/components/layout/Container'

/**
 * Suspense-Fallback fuer Lazy-Routes. Behaelt den Shell-Layout-Rhythmus
 * (Container) und zeigt ein neutrales LoadingState im Inhaltsbereich.
 */
export function RouteFallback() {
  return (
    <Container>
      <LoadingState rows={4} />
    </Container>
  )
}
