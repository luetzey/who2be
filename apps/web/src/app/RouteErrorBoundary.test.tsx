import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import i18n from '@/i18n'

import { RouteErrorBoundary } from './RouteErrorBoundary'

const GUARD_KEY = 'who2be:stale-chunk-reload'

function ThrowStaleChunk(): null {
  throw new Error('Importing a module script failed')
}

function ThrowGeneric(): null {
  throw new Error('Boom')
}

function renderBoundary(children: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <RouteErrorBoundary>{children}</RouteErrorBoundary>
    </MemoryRouter>,
  )
}

describe('RouteErrorBoundary', () => {
  let reloadSpy: ReturnType<typeof vi.fn>
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    window.sessionStorage.clear()
    reloadSpy = vi.fn()
    vi.stubGlobal('location', { ...window.location, reload: reloadSpy })
    // React loggt gefangene Render-Fehler zusaetzlich per console.error —
    // fuer diese Tests bewusst stummgeschaltet, geprueft wird das Verhalten.
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    consoleErrorSpy.mockRestore()
  })

  it('loest bei einem Stale-Chunk-Fehler einen Reload aus (Guard frisch)', () => {
    renderBoundary(<ThrowStaleChunk />)

    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })

  it('zeigt ErrorAlert mit "Unerwarteter Fehler", wenn der Guard bereits verbraucht ist', () => {
    window.sessionStorage.setItem(GUARD_KEY, String(Date.now()))

    renderBoundary(<ThrowStaleChunk />)

    expect(reloadSpy).not.toHaveBeenCalled()
    expect(screen.getByTestId('error-alert')).toBeInTheDocument()
    expect(screen.getByText(i18n.t('common:unexpectedError'))).toBeInTheDocument()
  })

  it('zeigt bei einem gewoehnlichen Fehler wie bisher ErrorAlert, ohne Reload', () => {
    renderBoundary(<ThrowGeneric />)

    expect(reloadSpy).not.toHaveBeenCalled()
    expect(screen.getByTestId('error-alert')).toBeInTheDocument()
    expect(screen.getByText(i18n.t('common:unexpectedError'))).toBeInTheDocument()
    expect(screen.getByText('Boom')).toBeInTheDocument()
  })
})
