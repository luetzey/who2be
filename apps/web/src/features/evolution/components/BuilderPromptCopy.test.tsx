import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BuilderPromptCopy } from './BuilderPromptCopy'

const { notifySuccess, notifyError } = vi.hoisted(() => ({
  notifySuccess: vi.fn(),
  notifyError: vi.fn(),
}))
vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: notifyError, info: vi.fn() },
}))

const { copySpy } = vi.hoisted(() => ({ copySpy: vi.fn() }))
vi.mock('@/lib/clipboard', () => ({ copyToClipboard: copySpy }))

beforeEach(() => {
  vi.clearAllMocks()
  copySpy.mockResolvedValue(undefined)
})

describe('BuilderPromptCopy', () => {
  it('bleibt ohne Angabe beim outline-Knopf (Korrektur im Review-Ergebnis)', () => {
    render(<BuilderPromptCopy prompt="Satz" />)
    const button = screen.getByRole('button', { name: 'Kopieren' })
    expect(button.className).not.toContain('bg-brand')
    expect(button.className).toContain('border')
  })

  it('nimmt variant brand an (E5f)', () => {
    render(<BuilderPromptCopy prompt="Satz" variant="brand" />)
    expect(screen.getByRole('button', { name: 'Kopieren' }).className).toContain('bg-brand')
  })

  it('ruft onCopied erst nach erfolgreichem Kopieren', async () => {
    const onCopied = vi.fn()
    render(<BuilderPromptCopy prompt="Satz" onCopied={onCopied} />)
    fireEvent.click(screen.getByRole('button', { name: 'Kopieren' }))
    await waitFor(() => expect(onCopied).toHaveBeenCalledTimes(1))
    expect(copySpy).toHaveBeenCalledWith('Satz')
    expect(notifySuccess).toHaveBeenCalledWith('Kopiert.')
  })

  it('ruft onCopied nicht, wenn das Kopieren scheitert', async () => {
    copySpy.mockRejectedValue(new Error('denied'))
    const onCopied = vi.fn()
    render(<BuilderPromptCopy prompt="Satz" onCopied={onCopied} />)
    fireEvent.click(screen.getByRole('button', { name: 'Kopieren' }))
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith('denied'))
    expect(onCopied).not.toHaveBeenCalled()
  })
})
