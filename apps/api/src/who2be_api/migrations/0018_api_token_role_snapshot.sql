-- Migration 0018 — api_token.role (Snapshot, Phase 2.3-0)
-- Token-Role-Snapshot (Plan §2.3.B, ADR-0023): ein API-Token traegt die Rolle
-- seines Erstellers zum Erstellungszeitpunkt. Verhindert Privilege-Drift —
-- die Token-Rolle ist gepinnt, nicht dynamisch an die aktuelle Member-Rolle
-- gebunden. Bestehende Token bekommen per DEFAULT 'admin' und bleiben damit
-- funktional unveraendert (Single-User-MVP-Token = volle Rechte).
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS. Der CHECK-Constraint ist Teil der
-- Spaltendefinition und wird nur beim ersten Lauf mit angelegt.

ALTER TABLE api_token
    ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'admin'
        CHECK (role IN ('admin', 'editor', 'viewer'));
