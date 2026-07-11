import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

function Basic({ onValueChange }: { onValueChange?: (value: string) => void } = {}) {
  return (
    <Tabs defaultValue="edit" onValueChange={onValueChange}>
      <TabsList aria-label="Detail-Tabs">
        <TabsTrigger value="edit">Bearbeiten</TabsTrigger>
        <TabsTrigger value="versions">Versionen</TabsTrigger>
      </TabsList>
      <TabsContent value="edit">Editor-Panel</TabsContent>
      <TabsContent value="versions">Versions-Panel</TabsContent>
    </Tabs>
  )
}

describe('Tabs', () => {
  it('zeigt nur das Panel des aktiven Tabs', () => {
    render(<Basic />)
    expect(screen.getByText('Editor-Panel')).toBeInTheDocument()
    expect(screen.queryByText('Versions-Panel')).not.toBeInTheDocument()
  })

  it('verknuepft tab und tabpanel via aria und markiert die Auswahl', () => {
    render(<Basic />)
    const editTab = screen.getByRole('tab', { name: 'Bearbeiten' })
    expect(editTab).toHaveAttribute('aria-selected', 'true')
    expect(editTab).toHaveAttribute('tabindex', '0')
    const versionsTab = screen.getByRole('tab', { name: 'Versionen' })
    expect(versionsTab).toHaveAttribute('aria-selected', 'false')
    expect(versionsTab).toHaveAttribute('tabindex', '-1')
    const panel = screen.getByRole('tabpanel')
    expect(panel).toHaveAttribute('aria-labelledby', editTab.id)
  })

  it('wechselt den Tab per Klick und meldet die Auswahl', () => {
    const onValueChange = vi.fn()
    render(<Basic onValueChange={onValueChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Versionen' }))
    expect(onValueChange).toHaveBeenCalledWith('versions')
    expect(screen.getByText('Versions-Panel')).toBeInTheDocument()
    expect(screen.queryByText('Editor-Panel')).not.toBeInTheDocument()
  })

  it('navigiert mit Pfeiltasten (roving tabindex, Aktivierung folgt Fokus)', () => {
    render(<Basic />)
    const editTab = screen.getByRole('tab', { name: 'Bearbeiten' })
    editTab.focus()
    fireEvent.keyDown(editTab, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Versionen' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Versionen' }), { key: 'ArrowLeft' })
    expect(screen.getByRole('tab', { name: 'Bearbeiten' })).toHaveAttribute('aria-selected', 'true')
  })

  it('unterstuetzt kontrollierten Betrieb ueber value', () => {
    render(
      <Tabs value="versions">
        <TabsList aria-label="Tabs">
          <TabsTrigger value="edit">Bearbeiten</TabsTrigger>
          <TabsTrigger value="versions">Versionen</TabsTrigger>
        </TabsList>
        <TabsContent value="edit">A</TabsContent>
        <TabsContent value="versions">B</TabsContent>
      </Tabs>,
    )
    expect(screen.getByText('B')).toBeInTheDocument()
    expect(screen.queryByText('A')).not.toBeInTheDocument()
  })
})
