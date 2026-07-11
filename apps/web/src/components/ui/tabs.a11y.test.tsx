import { render } from '@testing-library/react'
import { GitBranch, Pencil } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

describe('Tabs (a11y)', () => {
  it('hat keine axe-Violations', async () => {
    const { container } = render(
      <Tabs defaultValue="edit">
        <TabsList aria-label="Detail-Tabs">
          <TabsTrigger value="edit">
            <Pencil aria-hidden="true" />
            Bearbeiten
          </TabsTrigger>
          <TabsTrigger value="versions">
            <GitBranch aria-hidden="true" />
            Versionen
          </TabsTrigger>
        </TabsList>
        <TabsContent value="edit">Editor</TabsContent>
        <TabsContent value="versions">Versionen</TabsContent>
      </Tabs>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
