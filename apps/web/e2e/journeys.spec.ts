import { test } from '@playwright/test'

/**
 * Kritische User-Journeys (ADR-0032, Phase 4 — duenne Spitze, 3–5 Pfade).
 *
 * Diese Journeys brauchen einen echten Auth-Seed (GoTrue-User + Session) und
 * einen frisch geseedeten Workspace pro Lauf. Sie sind hier als `test.fixme`
 * verankert (erscheinen als pending, brechen CI nicht), bis der Seed-Helper
 * steht — gemaess Plan „erst non-blocking stabilisieren, dann hart schalten".
 *
 * Stabilisierungs-TODO (eigener Folge-Schritt):
 *  1. Login-Helper: GoTrue-User per Admin-API/SQL anlegen, Session injizieren
 *     (Supabase-Storage-Key) → `loginAs(page, user)`.
 *  2. Pro Journey frischer Workspace (idempotenter Seed), `data-testid`-Hooks
 *     statt Text-Selektoren (locale-stabil).
 */

test.fixme('Persona-Lifecycle: anlegen (Draft) -> editieren -> Draft->Review->Active', async () => {
  // 1. loginAs(editor); goto personas/new
  // 2. Name + BlockNote-Body ausfuellen, speichern -> Draft
  // 3. StatusActionBar: Draft->Review->Active; Status spiegelt active
})

test.fixme('Playbook->Resource-Block-Ref erzeugt Backlink in Resource-Detail', async () => {
  // 1. loginAs(editor); Resource + Playbook anlegen
  // 2. Im Playbook einen Resource-Block-Ref setzen
  // 3. Resource-Detail zeigt das Playbook als Backlink
})

test.fixme('MCP-Active-Read liefert nur die aktive Version', async () => {
  // 1. loginAs; Persona auf active promoten, Draft v2 anlegen
  // 2. MCP fetch (gegen :8000) liefert v1 (active), nicht den Draft
})

test.fixme('Invitation-Accept inkl. Email-Mismatch-Guard', async () => {
  // 1. Admin laedt ein; Magic-Link mit redirect_to=/accept?via=magic
  // 2. Falsche Email -> Guard blockt; korrekte Email -> Beitritt
})
