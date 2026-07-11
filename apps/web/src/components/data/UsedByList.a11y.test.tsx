import { render } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { UsedByList } from './UsedByList'

describe('UsedByList (a11y)', () => {
  it('hat keine axe-Violations', async () => {
    const { container } = render(
      <MemoryRouter>
        <UsedByList
          aria-label="Verlinkt in"
          items={[
            { id: 'pb1', name: 'Coach', href: '/playbooks/pb1', meta: '2 Bloecke' },
            {
              id: 'pb2',
              name: 'Onboarding-Flow',
              href: '/playbooks/pb2',
              icon: FileText,
              iconTone: 'resource',
            },
          ]}
        />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
