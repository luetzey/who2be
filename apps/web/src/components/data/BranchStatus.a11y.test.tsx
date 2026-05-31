import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { axe } from 'vitest-axe'

import { BranchStatus } from './BranchStatus'

describe('BranchStatus (a11y)', () => {
  it('hat keine axe-Violations', async () => {
    const { container } = render(
      <BranchStatus
        activeVersion={3}
        draftVersion={4}
        currentVersion={4}
        saveState={{ status: 'saved', lastSavedAt: new Date(), errorMessage: null }}
        actions={[
          {
            key: 'submit',
            label: 'Draft abschliessen',
            variant: 'brand',
            onClick: () => {},
          },
        ]}
      />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
