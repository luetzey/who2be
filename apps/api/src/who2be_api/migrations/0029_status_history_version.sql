-- Migration 0029 — status_history.version (Track A: Versionierung-Core)
-- Restore/Diff/Provenance brauchen Versions-Granularitaet im Audit-Trail:
--   * Provenance liest die Status-Kette EINER Version ("warum aktiv").
--   * Reset-auf-Draft reaktiviert die zuletzt aktive Version (juengste
--     status_history-active-Episode) — dazu muss am Audit-Eintrag stehen,
--     WELCHE Version aktiv wurde.
--
-- Nullable: Alt-Eintraege (vor dieser Migration) tragen keine Version; neue
-- Transitions schreiben sie ab jetzt mit. Idempotent via IF NOT EXISTS, damit
-- ein zweiter Lauf folgenlos bleibt (Runner-Vertrag, core/migrations.py).

ALTER TABLE status_history
    ADD COLUMN IF NOT EXISTS version integer;

CREATE INDEX IF NOT EXISTS status_history_entity_version_idx
    ON status_history (entity_type, entity_id, version, changed_at);
