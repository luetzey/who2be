import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { copyToClipboard } from './clipboard'

// happy-dom/jsdom liefern `document.execCommand` nicht (deprecated); fuer den
// Fallback-Pfad mockt jeder Test seine eigene Implementierung als Property.
function setExecCommand(impl: () => boolean): ReturnType<typeof vi.fn> {
  const fn = vi.fn(impl)
  Object.defineProperty(document, 'execCommand', {
    value: fn,
    configurable: true,
    writable: true,
  })
  return fn
}

describe('copyToClipboard', () => {
  beforeEach(() => {
    Reflect.deleteProperty(navigator, 'clipboard')
    Reflect.deleteProperty(document, 'execCommand')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    Reflect.deleteProperty(navigator, 'clipboard')
    Reflect.deleteProperty(document, 'execCommand')
  })

  it('nutzt navigator.clipboard.writeText im Secure-Context', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    await copyToClipboard('Hallo Welt')

    expect(writeText).toHaveBeenCalledTimes(1)
    expect(writeText).toHaveBeenCalledWith('Hallo Welt')
  })

  it('faellt auf execCommand zurueck, wenn navigator.clipboard fehlt (HTTP-Origin)', async () => {
    const exec = setExecCommand(() => true)

    await copyToClipboard('fallback-payload')

    expect(exec).toHaveBeenCalledWith('copy')
    expect(document.querySelector('textarea')).toBeNull()
  })

  it('faellt auf execCommand zurueck, wenn clipboard.writeText wirft (Permission)', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('NotAllowedError'))
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const exec = setExecCommand(() => true)

    await copyToClipboard('blocked')

    expect(writeText).toHaveBeenCalledOnce()
    expect(exec).toHaveBeenCalledWith('copy')
  })

  it('wirft eindeutige Error-Message, wenn execCommand fehlschlaegt', async () => {
    setExecCommand(() => false)

    await expect(copyToClipboard('lost')).rejects.toThrow(/Clipboard nicht verfuegbar/)
    expect(document.querySelector('textarea')).toBeNull()
  })

  it('raeumt die Textarea auch bei execCommand-Exception auf', async () => {
    setExecCommand(() => {
      throw new Error('boom')
    })

    await expect(copyToClipboard('cleanup')).rejects.toThrow()
    expect(document.querySelector('textarea')).toBeNull()
  })
})
