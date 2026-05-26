import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'

import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'

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
  }

  render(): ReactNode {
    if (this.state.error !== null) {
      return (
        <Container>
          <ErrorAlert title="Unerwarteter Fehler" message={this.state.error.message} />
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
