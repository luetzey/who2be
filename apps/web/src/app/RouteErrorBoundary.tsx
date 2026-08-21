import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'

import { isStaleChunkError, reloadOnStaleChunk } from '@/app/stale-chunk'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'
import i18n from '@/i18n'

interface BoundaryProps {
  children: ReactNode
}

interface BoundaryState {
  error: Error | null
}

class ErrorBoundaryImpl extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('RouteErrorBoundary fing einen Fehler:', error, info)
    // Stale-Chunk-Fehler (alter React.lazy-Chunk nach Deploy 404): statt der
    // Fehlerseite genau einmal neu laden. Ist der Guard bereits verbraucht
    // (oder sessionStorage nicht verfuegbar), faellt render() unten wie
    // gehabt auf ErrorAlert zurueck.
    if (isStaleChunkError(error)) {
      reloadOnStaleChunk()
    }
  }

  render(): ReactNode {
    if (this.state.error !== null) {
      return (
        <Container>
          <ErrorAlert title={i18n.t('common:unexpectedError')} message={this.state.error.message} />
        </Container>
      )
    }
    return this.props.children
  }
}

/**
 * React-Error-Boundary fuer Route-Inhalte. Wird in `AppLayout` zwischen
 * `AppShell` und `<Outlet/>` montiert — der Shell bleibt sichtbar wenn
 * eine Page im Render scheitert. Reset bei Route-Wechsel via `key`.
 */
export function RouteErrorBoundary({ children }: BoundaryProps) {
  const location = useLocation()
  return <ErrorBoundaryImpl key={location.pathname}>{children}</ErrorBoundaryImpl>
}
