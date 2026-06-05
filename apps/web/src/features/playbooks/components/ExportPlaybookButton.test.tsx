import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'

import { ExportPlaybookButton } from './ExportPlaybookButton'

const exportPlaybook = vi.fn()
const notifySuccess = vi.fn()
const notifyError = vi.fn()

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ exportPlaybook }),
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

function makePlaybook(overrides: Partial<Playbook> = {}): Playbook {
  return {
    id: 'pb-1',
    workspace_id: 'ws-1',
    owner_id: 'u-1',
    name: 'Onboarding',
    current_version: 1,
    type: 'guide',
    tags: [],
    triggers: null,
    content: { body: '' },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Playbook
}

let anchorClick: ReturnType<typeof vi.fn>
let createdAnchors: HTMLAnchorElement[]

beforeAll(() => {
  for (const fn of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

beforeEach(() => {
  exportPlaybook.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  createdAnchors = []
  anchorClick = vi.fn()
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreate(tag)
    if (tag === 'a') {
      el.click = anchorClick
      createdAnchors.push(el as HTMLAnchorElement)
    }
    return el
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ExportPlaybookButton', () => {
  it('exportiert als Markdown und löst einen Download-Anchor aus', async () => {
    exportPlaybook.mockResolvedValue('# Onboarding')
    render(<ExportPlaybookButton playbook={makePlaybook()} />)

    fireEvent.keyDown(screen.getByTestId('export-playbook-trigger'), { key: 'Enter' })
    fireEvent.click(await screen.findByTestId('export-playbook-markdown'))

    await waitFor(() => {
      expect(exportPlaybook).toHaveBeenCalledWith('pb-1', 'markdown')
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(createdAnchors.at(-1)?.download).toBe('who2be-playbook-onboarding.md')
  })
})
