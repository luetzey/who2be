import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DataView } from './DataView'

describe('DataView', () => {
  it('zeigt Skeleton im Loading-Zustand', () => {
    render(
      <DataView loading>
        <div>kinder</div>
      </DataView>,
    )

    expect(screen.getByText('Lädt…')).toBeInTheDocument()
    expect(screen.queryByText('kinder')).not.toBeInTheDocument()
  })

  it('zeigt ErrorAlert mit Nachricht', () => {
    render(
      <DataView error="Netzwerk weg.">
        <div>kinder</div>
      </DataView>,
    )

    expect(screen.getByText('Netzwerk weg.')).toBeInTheDocument()
    expect(screen.queryByText('kinder')).not.toBeInTheDocument()
  })

  it('zeigt EmptyState mit Titel + Beschreibung', () => {
    render(
      <DataView empty emptyTitle="Nichts da." emptyDescription="Lege etwas an.">
        <div>kinder</div>
      </DataView>,
    )

    expect(screen.getByText('Nichts da.')).toBeInTheDocument()
    expect(screen.getByText('Lege etwas an.')).toBeInTheDocument()
    expect(screen.queryByText('kinder')).not.toBeInTheDocument()
  })

  it('rendert children wenn kein State aktiv ist', () => {
    render(
      <DataView>
        <div>kinder</div>
      </DataView>,
    )

    expect(screen.getByText('kinder')).toBeInTheDocument()
  })

  it('priorisiert Loading vor Error vor Empty vor Content', () => {
    render(
      <DataView loading error="ignored" empty emptyTitle="auch ignoriert">
        <div>kinder</div>
      </DataView>,
    )

    expect(screen.getByText('Lädt…')).toBeInTheDocument()
    expect(screen.queryByText('ignored')).not.toBeInTheDocument()
    expect(screen.queryByText('auch ignoriert')).not.toBeInTheDocument()
  })
})
