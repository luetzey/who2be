import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useForm } from 'react-hook-form'

import type { ResourceBlock } from '@/api/types'
import { axe } from '@/test/a11y'
import { Form } from '@/components/ui/form'

import { PersonaModesEditor } from './PersonaModesEditor'
import type { PersonaEditorValues } from '../hooks/usePersonaForm'

// BlockNote-Insel mocken (jsdom kann ProseMirror nicht starten).
vi.mock('@/components/editor/BlockNoteEditor', () => ({
  BlockNoteEditor: ({ initialBlocks }: { initialBlocks: ResourceBlock[] }) => (
    <div
      data-testid="blocknote-view"
      data-initial-blocks={JSON.stringify(initialBlocks)}
    />
  ),
}))

vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    listPlaybooks: vi.fn().mockResolvedValue([{ id: 'pb-1', name: 'Playbook A' }]),
  }),
}))

const emptyMode = (overrides: Partial<PersonaEditorValues['modes'][number]> = {}) => ({
  name: '',
  trigger: '',
  is_default: false,
  identity_add: [],
  output_style_override: [],
  anti_patterns: [],
  playbook_id: null,
  playbook_name: undefined,
  ...overrides,
})

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
      skills: [],
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
      <Harness initialModes={[emptyMode({ name: 'Standard', is_default: true })]} />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit mehreren Modi', async () => {
    const { container } = render(
      <Harness
        initialModes={[
          emptyMode({ name: 'Coaching', trigger: 'coaching', is_default: true }),
          emptyMode({ name: 'Analyse', trigger: 'analyse', is_default: false }),
        ]}
      />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
