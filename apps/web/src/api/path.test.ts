import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

import { apiPath, resolveApiPath, segmentProblem, withQuery } from './path'

describe('apiPath', () => {
  it('kodiert jeden Wert als genau ein Segment', () => {
    const p = apiPath`/v1/workspaces/${'ws 1'}/personas/${'%2e%2e%2fx'}`
    expect(resolveApiPath(p)).toBe('/v1/workspaces/ws%201/personas/%252e%252e%252fx')
  })

  it('uebernimmt einen eingebetteten ApiPath unveraendert', () => {
    const ws = apiPath`/v1/workspaces/${'w'}`
    expect(resolveApiPath(apiPath`${ws}/agents/${7}`)).toBe('/v1/workspaces/w/agents/7')
  })

  it.each(['', '.', '..', '../x', 'x/..', 'a/b', 'a\\b', 'x?y=1', 'x#y'])(
    'macht den Pfad mit %j ungueltig',
    (value) => {
      expect(segmentProblem(value)).not.toBeNull()
      expect(resolveApiPath(apiPath`/v1/items/${value}`)).toBeNull()
    },
  )

  it('vererbt die Ungueltigkeit an zusammengesetzte Pfade', () => {
    const ws = apiPath`/v1/workspaces/${'../admin'}`
    expect(resolveApiPath(withQuery(apiPath`${ws}/agents`, { a: '1' }))).toBeNull()
  })

  it('lehnt eine Query im statischen Teil ab (nur ueber withQuery)', () => {
    expect(resolveApiPath(apiPath`/v1/items?tag=${'x'}`)).toBeNull()
  })

  it('lehnt statische Punkt-Segmente ueber die URL-Normalisierung ab', () => {
    expect(resolveApiPath(apiPath`/v1/items/../admin`)).toBeNull()
    expect(resolveApiPath(apiPath`/v1/items/%2e%2e/admin`)).toBeNull()
  })
})

describe('withQuery', () => {
  it('kodiert Werte und laesst leere Parameter weg', () => {
    expect(resolveApiPath(withQuery(apiPath`/v1/t`, { a: 'x&b=1' }))).toBe('/v1/t?a=x%26b%3D1')
    expect(resolveApiPath(withQuery(apiPath`/v1/t`, {}))).toBe('/v1/t')
  })

  it('lehnt eine zweite Query ab', () => {
    const once = withQuery(apiPath`/v1/t`, { a: '1' })
    expect(resolveApiPath(withQuery(once, { b: '2' }))).toBeNull()
  })
})

// Regressionsschutz: in client.ts entsteht kein Pfad mehr an `apiPath` vorbei.
// Geprueft wird der Syntaxbaum, nicht der Text — Kommentare und Strings mit
// `${` stoeren nicht, und jede neue Konstruktionsform faellt auf.
describe('client.ts baut Pfade nur ueber apiPath/withQuery', () => {
  const file = path.join(path.dirname(fileURLToPath(import.meta.url)), 'client.ts')

  function offenders(source: string): string[] {
    const sf = ts.createSourceFile('client.ts', source, ts.ScriptTarget.Latest, true)
    const found: string[] = []
    const where = (node: ts.Node) =>
      `client.ts:${sf.getLineAndCharacterOfPosition(node.getStart()).line + 1}: ${node.getText().slice(0, 80)}`
    const looksLikePath = (text: string) => /[/?]/.test(text)

    const visit = (node: ts.Node) => {
      // Ungetaggtes Template mit Interpolation und `/` oder `?` im Text.
      if (ts.isTemplateExpression(node) && !ts.isTaggedTemplateExpression(node.parent)) {
        const texts = [node.head.text, ...node.templateSpans.map((s) => s.literal.text)]
        if (texts.some(looksLikePath)) found.push(where(node))
      }
      // String-Verkettung mit `+`, bei der ein Literal nach Pfad aussieht.
      if (
        ts.isBinaryExpression(node) &&
        node.operatorToken.kind === ts.SyntaxKind.PlusToken &&
        [node.left, node.right].some(
          (side) =>
            (ts.isStringLiteral(side) || ts.isNoSubstitutionTemplateLiteral(side)) &&
            looksLikePath(side.text),
        )
      ) {
        found.push(where(node))
      }
      // Punktuelles Kodieren ist ein Zeichen fuer einen Pfadbau daneben.
      if (ts.isIdentifier(node) && node.text === 'encodeURIComponent') found.push(where(node))
      ts.forEachChild(node, visit)
    }
    visit(sf)
    return found
  }

  it('findet in client.ts keine rohe Interpolation in Pfaden', () => {
    expect(offenders(fs.readFileSync(file, 'utf8'))).toEqual([])
  })

  it('schlaegt bei den alten Formen an (Probe des Waechters)', () => {
    const probes = [
      'const a = request(token, `${ws}/personas/${id}`)',
      "const b = `${ws}/x` + '?against=' + v",
      'const c = `/v1/workspaces/${workspaceId}`',
      'const d = `${ws}/memories/${encodeURIComponent(id)}`',
    ]
    for (const probe of probes) expect(offenders(probe)).not.toEqual([])
    expect(offenders('const ok = apiPath`${ws}/personas/${id}`')).toEqual([])
  })
})
