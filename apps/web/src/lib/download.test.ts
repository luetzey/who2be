import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadExport, downloadFile } from './download'

let anchorClick: ReturnType<typeof vi.fn>
let createdAnchors: HTMLAnchorElement[]

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

beforeEach(() => {
  createdAnchors = []
  anchorClick = vi.fn()
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreate(tag)
    if (tag === 'a') {
      el.click = anchorClick as () => void
      createdAnchors.push(el as HTMLAnchorElement)
    }
    return el
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('downloadFile', () => {
  it('loest fuer einen Blob-Inhalt einen Download-Anchor mit dem gegebenen Dateinamen aus', () => {
    const blob = new Blob(['abc'], { type: 'application/vnd.ms-excel' })

    downloadFile(blob, 'who2be-tabelle-export.xlsx')

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(anchorClick).toHaveBeenCalled()
    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-tabelle-export.xlsx')
    expect(anchor?.href).toBe('blob:mock')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })

  it('verpackt einen String-Inhalt in einen Blob und loest den Download aus', () => {
    downloadFile('a,b,c\n1,2,3', 'who2be-tabelle-export.csv')

    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    expect(anchorClick).toHaveBeenCalled()
    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-tabelle-export.csv')
  })
})

describe('downloadExport', () => {
  it('bleibt unveraendert: JSON-Export mit dem bestehenden Namensschema', () => {
    downloadExport({ id: 'p-1' }, 'json', 'persona', 'Carla')

    const anchor = createdAnchors.at(-1)
    expect(anchor?.download).toBe('who2be-persona-carla.json')
  })
})
