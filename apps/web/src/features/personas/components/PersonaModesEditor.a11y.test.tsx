import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useForm } from 'react-hook-form'

import { axe } from '@/test/a11y'
import { Form } from '@/components/ui/form'

import { PersonaModesEditor } from './PersonaModesEditor'
import type { PersonaEditorValues } from '../hooks/usePersonaForm'

function Harness({
  initialModes = [],
}: {
  initialModes?: PersonaEditorValues['modes']
}) {
  const form = useForm<PersonaEditorValues>({
    defaultValues: {
      name: 'Test',
      description: 'Desc',
      profileBlocks: [],
      tags: [],
      modes: initialModes,
    },
  })
  return (
    <Form {...form}>
      <form>
        <PersonaModesEditor control={form.control} />
      </form>
    </Form>
  )
}

describe('PersonaModesEditor (a11y)', () => {
  it('hat keine axe-Violations im Leer-Zustand', async () => {
    const { container } = render(<Harness />)
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit einem Default-Modus', async () => {
    const { container } = render(
      <Harness
        initialModes={[
          {
            name: 'Standard',
            trigger: '',
            is_default: true,
            identity_add: 'Sei sachlich',
            output_style_override: '',
          },
        ]}
      />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit mehreren Modi', async () => {
    const { container } = render(
      <Harness
        initialModes={[
          {
            name: 'Coaching',
            trigger: 'coaching',
            is_default: true,
            identity_add: '',
            output_style_override: '',
          },
          {
            name: 'Analyse',
            trigger: 'analyse',
            is_default: false,
            identity_add: '',
            output_style_override: '',
          },
        ]}
      />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
