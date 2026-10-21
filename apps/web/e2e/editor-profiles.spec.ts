import { expect, test, type Locator, type Page } from '@playwright/test'

import { apiRequest, createUser, loginAs, seedWorkspace } from './helpers/auth'
import { decideCookieConsent } from './helpers/consent'

/**
 * Editor-Paket P2: was jeder Einsatzort anbietet (editorProfiles.ts).
 *
 * Browser statt jsdom, weil Slash-Menue, Formatierungsleiste und Einfuegen
 * ProseMirror im echten DOM brauchen (ADR-0022). Geprueft wird:
 * - Playbook: Slash-Menue mit nummerierter Liste, Zitat und Code, ohne
 *   Tabelle; eingefuegte Tabelle wird zu Text.
 * - Resource: der einzige Ort mit Tabelle; eingefuegte Tabelle bleibt.
 * - Formatierungsleiste: Fett, Kursiv, Code, Link — ohne Unterstreichen,
 *   Farben, Ausrichten, Einruecken.
 * - Bestand: ein Playbook, das schon eine Tabelle enthaelt, oeffnet und
 *   zeigt sie weiter (kein Lese-Fallback in BlockNote, Schema bleibt voll).
 */

const TABLE_HTML =
  '<table><tr><th>Stufe</th><th>Frist</th></tr><tr><td>Eins</td><td>3 Tage</td></tr></table>'

// Die Menuetitel werden auf Deutsch geprueft (UI-Sprache folgt dem Browser).
test.use({ locale: 'de-DE' })

const paragraph = (id: string, text: string) => ({
  id,
  type: 'paragraph',
  props: {},
  content: [{ type: 'text', text, styles: {} }],
  children: [],
})

const tableBlock = {
  id: 'e2e-bestand-tabelle',
  type: 'table',
  props: {},
  content: {
    type: 'tableContent',
    columnWidths: [null, null],
    rows: [
      { cells: [[{ type: 'text', text: 'Bestand A', styles: {} }], [{ type: 'text', text: 'Bestand B', styles: {} }]] },
    ],
  },
  children: [],
}

async function setup(page: Page, request: Parameters<typeof createUser>[0]) {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  const token = user.session.access_token
  const post = <T>(path: string, data: unknown) =>
    apiRequest<T>(request, token, `/v1/workspaces/${workspaceId}${path}`, { method: 'POST', data })
  return { ws: `/w/${workspaceId}`, post }
}

/** Setzt den Cursor ans Ende des letzten Absatzes im Editor. */
async function focusEnd(editor: Locator) {
  const last = editor.locator('[data-content-type="paragraph"]').last()
  await last.click()
  await editor.page().keyboard.press('End')
}

async function pasteHtml(editor: Locator, html: string) {
  await editor.locator('.ProseMirror').evaluate((el, value) => {
    const data = new DataTransfer()
    data.setData('text/html', value)
    data.setData('text/plain', 'Stufe\tFrist\nEins\t3 Tage')
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }))
  }, html)
}

async function slashTitles(page: Page, editor: Locator): Promise<string[]> {
  await focusEnd(editor)
  await page.keyboard.press('Enter')
  await page.keyboard.type('/')
  const menu = page.locator('.bn-suggestion-menu')
  await expect(menu).toBeVisible()
  const titles = await menu.locator('.bn-mt-suggestion-menu-item-title').allInnerTexts()
  await page.keyboard.press('Escape')
  return titles.map((title) => title.trim())
}

test('Playbook: Slash-Menue ohne Tabelle, eingefuegte Tabelle wird Text', async ({ page, request }) => {
  test.setTimeout(90_000)
  const { ws, post } = await setup(page, request)
  const playbook = await post<{ id: string }>('/playbooks', {
    name: 'E2E P2 Playbook',
    content: { description: 'Kurz.', body: JSON.stringify([paragraph('e2e-p1', 'Schritt eins')]) },
  })

  await page.goto(`${ws}/playbooks/${playbook.id}`)
  const editor = page.getByTestId('playbook-body-editor')
  await expect(editor.getByText('Schritt eins')).toBeVisible()

  const titles = await slashTitles(page, editor)
  for (const wanted of ['Nummerierte Liste', 'Zitat', 'Code']) expect(titles).toContain(wanted)
  for (const missing of ['Tabelle', 'Bild', 'Checkliste', 'Titel']) expect(titles).not.toContain(missing)

  await focusEnd(editor)
  await pasteHtml(editor, TABLE_HTML)
  await expect(editor.getByText('Eins | 3 Tage')).toBeVisible()
  await expect(editor.locator('[data-content-type="table"]')).toHaveCount(0)
})

test('Resource: Tabelle im Slash-Menue, eingefuegte Tabelle bleibt Tabelle', async ({ page, request }) => {
  test.setTimeout(90_000)
  const { ws, post } = await setup(page, request)
  const resource = await post<{ id: string }>('/resources', {
    name: 'E2E P2 Resource',
    content: { description: 'Kurz.', blocks: [paragraph('e2e-r1', 'Inhalt der Resource')] },
  })

  await page.goto(`${ws}/resources/${resource.id}`)
  const editor = page.getByTestId('blocknote-editor')
  await expect(editor).toHaveAttribute('data-editor-profile', 'resource')
  await expect(editor.getByText('Inhalt der Resource')).toBeVisible()

  const titles = await slashTitles(page, editor)
  expect(titles).toContain('Tabelle')
  expect(titles).not.toContain('Bild')

  await focusEnd(editor)
  await pasteHtml(editor, TABLE_HTML)
  await expect(editor.locator('[data-content-type="table"]')).toHaveCount(1)
})

test('Formatierungsleiste: Fett, Kursiv, Code, Link — ohne Unterstreichen, Farben, Ausrichten', async ({
  page,
  request,
}) => {
  const { ws, post } = await setup(page, request)
  const playbook = await post<{ id: string }>('/playbooks', {
    name: 'E2E P2 Leiste',
    content: { description: 'Kurz.', body: JSON.stringify([paragraph('e2e-l1', 'Markiere mich')]) },
  })

  await page.goto(`${ws}/playbooks/${playbook.id}`)
  const editor = page.getByTestId('playbook-body-editor')
  await editor.getByText('Markiere mich').dblclick()
  const toolbar = page.locator('.bn-formatting-toolbar')
  await expect(toolbar).toBeVisible()
  for (const present of ['bold', 'italic', 'code', 'createLink']) {
    await expect(toolbar.locator(`[data-test="${present}"]`)).toHaveCount(1)
  }
  for (const absent of ['underline', 'strike', 'colors', 'alignTextLeft', 'nestBlock', 'unnestBlock']) {
    await expect(toolbar.locator(`[data-test="${absent}"]`)).toHaveCount(0)
  }
})

test('Bestand: Playbook mit Tabelle oeffnet und zeigt sie weiter', async ({ page, request }) => {
  const { ws, post } = await setup(page, request)
  const playbook = await post<{ id: string }>('/playbooks', {
    name: 'E2E P2 Bestand',
    content: {
      description: 'Kurz.',
      body: JSON.stringify([paragraph('e2e-b1', 'Vor der Tabelle'), tableBlock]),
    },
  })

  await page.goto(`${ws}/playbooks/${playbook.id}`)
  const editor = page.getByTestId('playbook-body-editor')
  await expect(editor.getByText('Vor der Tabelle')).toBeVisible()
  await expect(editor.locator('[data-content-type="table"]')).toHaveCount(1)
  await expect(editor.getByText('Bestand B')).toBeVisible()
})

/**
 * Editor-Paket P3: Längen-Fußzeile. Tippen im echten Editor ändert die Zahl;
 * die Live-Region schweigt beim Öffnen und meldet erst nach einer Pause.
 * Pills zählen nicht mit (Unit-Test), hier geht es um das Browser-Verhalten.
 */
test('Fußzeile: Zähler folgt dem Tippen, Live-Region meldet erst nach der Pause', async ({
  page,
  request,
}) => {
  test.setTimeout(90_000)
  const { ws, post } = await setup(page, request)
  const playbook = await post<{ id: string }>('/playbooks', {
    name: 'E2E P3 Zähler',
    content: { description: 'Kurz.', body: JSON.stringify([paragraph('e2e-z1', 'Grüße')]) },
  })

  await page.goto(`${ws}/playbooks/${playbook.id}`)
  const editor = page.getByTestId('playbook-body-editor')
  await expect(editor.getByText('Grüße')).toBeVisible()
  const footer = page.getByTestId('editor-footer')
  const length = footer.getByTestId('editor-footer-length')
  const live = footer.getByTestId('editor-footer-live')
  await expect(length).toHaveText('≈ 5 Zeichen · ≈ 10 Token (geschätzt)')
  await expect(live).toHaveAttribute('aria-live', 'polite')
  await page.waitForTimeout(1500)
  await expect(live).toHaveText('')

  await focusEnd(editor)
  await page.keyboard.type(' an alle')
  await expect(length).toHaveText('≈ 13 Zeichen · ≈ 10 Token (geschätzt)')
  // Gedrosselt: direkt nach dem Tippen noch still, nach der Pause gemeldet.
  await expect(live).toHaveText('')
  await expect(live).toHaveText('Länge: etwa 13 Zeichen, etwa 10 Token (geschätzt)')

  await footer.getByRole('button', { name: 'Wie wird die Länge geschätzt?' }).focus()
  await expect(page.getByRole('tooltip')).toContainText('Eingebettete Verweise sind nicht eingerechnet.')
})

test('Fußzeile: auch im Resource-Editor', async ({ page, request }) => {
  const { ws, post } = await setup(page, request)
  const resource = await post<{ id: string }>('/resources', {
    name: 'E2E P3 Resource',
    content: { description: 'Kurz.', blocks: [paragraph('e2e-zr1', 'Zwölf Zeichen')] },
  })

  await page.goto(`${ws}/resources/${resource.id}`)
  const editor = page.getByTestId('resource-editor')
  await expect(editor.getByText('Zwölf Zeichen')).toBeVisible()
  const length = editor.getByTestId('editor-footer-length')
  await expect(length).toHaveText('≈ 13 Zeichen · ≈ 10 Token (geschätzt)')
  await focusEnd(editor.getByTestId('blocknote-editor'))
  await page.keyboard.type('!')
  await expect(length).toHaveText('≈ 14 Zeichen · ≈ 10 Token (geschätzt)')
})
