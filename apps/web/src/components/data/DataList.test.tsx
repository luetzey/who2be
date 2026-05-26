import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DataList } from './DataList'

interface Item {
  id: string
  label: string
}

const renderList = (props: Partial<React.ComponentProps<typeof DataList<Item>>> = {}) =>
  render(
    <DataList
      items={[]}
      getKey={(item) => item.id}
      renderItem={(item) => <span>{item.label}</span>}
      {...props}
    />,
  )

describe('DataList', () => {
  it('rendert Loading-Skeleton wenn loading=true', () => {
    renderList({ loading: true })
    expect(screen.getByText('Lädt…')).toBeInTheDocument()
  })

  it('rendert ErrorAlert wenn error gesetzt ist', () => {
    renderList({ error: 'Boom' })
    expect(screen.getByText('Boom')).toBeInTheDocument()
  })

  it('rendert Default-EmptyState wenn items leer und kein anderer State aktiv', () => {
    renderList()
    expect(screen.getByText('Keine Einträge.')).toBeInTheDocument()
  })

  it('rendert die Items wenn vorhanden', () => {
    renderList({ items: [{ id: 'a', label: 'Alpha' }, { id: 'b', label: 'Bravo' }] })
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Bravo')).toBeInTheDocument()
  })

  it('rendert custom empty wenn uebergeben', () => {
    renderList({ empty: <div>Nada</div> })
    expect(screen.getByText('Nada')).toBeInTheDocument()
  })
})
