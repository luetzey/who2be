import { render } from '@testing-library/react'
import { Clock } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { Button } from '@/components/ui/button'
import { axe } from '@/test/a11y'

import { AttentionBanner } from './AttentionBanner'

describe('AttentionBanner (a11y)', () => {
  it('hat keine axe-Violations', async () => {
    const { container } = render(
      <AttentionBanner
        icon={Clock}
        title="Version 3 liegt zur Review"
        description="Wartet auf Freigabe durch einen Admin."
        actions={
          <>
            <Button variant="brand">Aktivieren</Button>
            <Button variant="outline">Zurueck zu Entwurf</Button>
          </>
        }
      />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
