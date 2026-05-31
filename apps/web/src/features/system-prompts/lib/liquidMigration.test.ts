import { describe, expect, it } from 'vitest'

import { liquidBodyToInline } from './liquidMigration'

describe('liquidBodyToInline', () => {
  it('wandelt persona.name in einen persona-field-Placeholder mit target_id=name', () => {
    const out = liquidBodyToInline('Hallo {{ persona.name }}!')
    expect(out).toEqual([
      { type: 'text', text: 'Hallo ', styles: {} },
      {
        type: 'placeholder',
        props: { kind: 'persona-field', target_id: 'name', label: 'Persona: Name' },
      },
      { type: 'text', text: '!', styles: {} },
    ])
  })

  it('wandelt persona.description analog mit target_id=description', () => {
    const out = liquidBodyToInline('{{ persona.description }}')
    expect(out).toEqual([
      {
        type: 'placeholder',
        props: {
          kind: 'persona-field',
          target_id: 'description',
          label: 'Persona: Beschreibung',
        },
      },
    ])
  })

  it('belaesst unbekannte Tokens als Klartext (Server-Renderer kann sie spaeter expandieren)', () => {
    const out = liquidBodyToInline('Siehe {{ playbooks }} und {{ triggers }}.')
    expect(out).toEqual([
      { type: 'text', text: 'Siehe ', styles: {} },
      { type: 'text', text: '{{ playbooks }}', styles: {} },
      { type: 'text', text: ' und ', styles: {} },
      { type: 'text', text: '{{ triggers }}', styles: {} },
      { type: 'text', text: '.', styles: {} },
    ])
  })

  it('liefert einen leeren Text-Run statt leerer Inline-Liste fuer leeren Input', () => {
    expect(liquidBodyToInline('')).toEqual([{ type: 'text', text: '', styles: {} }])
  })

  it('liefert eine reine Text-Liste fuer Input ohne Tokens', () => {
    expect(liquidBodyToInline('Plain text.')).toEqual([
      { type: 'text', text: 'Plain text.', styles: {} },
    ])
  })

  it('toleriert variable Whitespace innerhalb des Tokens', () => {
    const out = liquidBodyToInline('{{persona.name}} und {{   persona.description   }}')
    expect(out.filter((c) => c.type === 'placeholder')).toHaveLength(2)
  })
})
