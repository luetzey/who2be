import { expect, test } from '@playwright/test'

/**
 * Oeffentliche Routen — die robuste Basis der E2E-Spitze (ADR-0041, Phase 4).
 *
 * Bewusst strukturelle (locale-unabhaengige) Assertions: dass die App im echten
 * Browser bootet, die Auth-Seiten ihre Felder rendern und ungeschuetzte Routen
 * auf /login umleiten. Diese Checks brauchen keinen Auth-Seed und sind damit
 * flake-arm — die Logik selbst ist unten in Unit/Integration getestet.
 */

test('App bootet im Browser (Root mountet, Titel gesetzt)', async ({ page }) => {
  const response = await page.goto('/')
  expect(response?.ok()).toBeTruthy()
  await expect(page).toHaveTitle(/.+/)
  // React-Root ist gemountet und nicht leer.
  await expect(page.locator('#root')).not.toBeEmpty()
})

test('Login-Seite rendert Email- und Passwort-Feld', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('input[type="email"]')).toBeVisible()
  await expect(page.locator('input[type="password"]')).toBeVisible()
})

test('Impressum (Legal) ist oeffentlich erreichbar', async ({ page }) => {
  const response = await page.goto('/legal/impressum')
  expect(response?.ok()).toBeTruthy()
  await expect(page.locator('main')).toBeVisible()
})

test('Geschuetzte Route leitet unauthentifiziert auf /login um', async ({ page }) => {
  await page.goto('/w/00000000-0000-0000-0000-000000000000/dashboard')
  // SessionProvider erkennt fehlende Session und routet zur Login-Seite.
  await page.waitForURL(/\/login/, { timeout: 15_000 })
  await expect(page.locator('input[type="email"]')).toBeVisible()
})
