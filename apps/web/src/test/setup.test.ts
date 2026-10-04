import { getConfig, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

// Haelt die zentrale Wartezeit aus `setup.ts` fest: `findBy*`/`waitFor` warten
// ohne eigenes `{ timeout }` bis 3 s statt des Testing-Library-Defaults 1 s.
describe('Test-Setup: asyncUtilTimeout', () => {
  it('steht auf 3000 ms', () => {
    expect(getConfig().asyncUtilTimeout).toBe(3000)
  })

  it('waitFor ohne eigenes timeout wartet laenger als den 1-s-Default', async () => {
    let ready = false
    setTimeout(() => {
      ready = true
    }, 1200)
    await waitFor(() => expect(ready).toBe(true))
  })
})
