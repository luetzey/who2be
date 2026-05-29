import { render } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { TagInput } from './tag-input'

function Harness() {
  const [value, setValue] = useState<string[]>(['coaching'])
  return (
    <div>
      <span id="tag-label">Tags</span>
      <TagInput
        value={value}
        onChange={setValue}
        ariaLabelledby="tag-label"
        placeholder="Tag eingeben"
      />
    </div>
  )
}

describe('TagInput (a11y)', () => {
  it('hat keine axe-Violations', async () => {
    const { container } = render(<Harness />)
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
