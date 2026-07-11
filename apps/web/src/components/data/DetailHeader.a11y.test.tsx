import { render } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { Button } from '@/components/ui/button'
import { axe } from '@/test/a11y'

import { DetailHeader } from './DetailHeader'

describe('DetailHeader (a11y)', () => {
  it('hat keine axe-Violations', async () => {
    const { container } = render(
      <MemoryRouter>
        <DetailHeader
          icon={FileText}
          iconTone="tools"
          title="Support-Base"
          backHref="/system-prompts"
          backLabel="System-Prompts"
          badges={<span>support-base</span>}
          description="Grund-Prompt fuer Support-Gespraeche."
          actions={<Button variant="outline">Duplizieren</Button>}
        />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
