import { render } from '@testing-library/react'
import { FileText, Layers } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { EntityCard } from './EntityCard'
import { MetaPill } from './MetaPill'

describe('EntityCard (a11y)', () => {
  it('hat keine axe-Violations — schlichte Karte', async () => {
    const { container } = render(
      <MemoryRouter>
        <EntityCard
          icon={FileText}
          iconTone="tools"
          title="Support-Base"
          href="/sp/1"
          badges={<MetaPill tone="tools">support-base</MetaPill>}
          description="Grund-Prompt fuer Support-Gespraeche."
          meta={<MetaPill>Verwendet von 6 Agents</MetaPill>}
        />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations — mit offenem Expander', async () => {
    const { container } = render(
      <MemoryRouter>
        <EntityCard
          icon={FileText}
          iconTone="resource"
          title="Rueckerstattungs-Policy"
          href="/res/1"
          open={true}
          expandIcon={Layers}
          expandLabel="2 Sub-Resources"
          expandable={<p>Panel</p>}
        />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
