-- Migration 0081 — doppelt encodierte jsonb-Werte auspacken
-- (Befund 2026-08-16: `describe_table` antwortete mit 500)
--
-- Ursache: Ein Bind-Parameter mit `::jsonb`-Cast aktiviert den jsonb-Codec
-- des App-Pools (`core/db.init_connection`, `encoder=json.dumps`). Wer den
-- Wert VORHER selbst serialisiert hat, liess ihn damit ein zweites Mal
-- verpacken — in der Spalte stand danach ein JSON-*String* statt eines
-- Objekts. Gemessen (asyncpg 0.30, PG 16):
--
--     $1::jsonb        + dict        -> jsonb_typeof = 'object'
--     $1::jsonb        + json.dumps  -> jsonb_typeof = 'string'   <-- Bug
--     $1::text::jsonb  + json.dumps  -> jsonb_typeof = 'object'
--
-- Aufgefallen ist es nur an EINER Stelle: `wa_source_convention` wurde von
-- zwei Mappern gelesen, und der strengere (`wa_table_repository`, einziger
-- Aufrufer: der describe-Pfad) starb an der Zeilenform. Sobald eine Area der
-- dokumentierten Reihenfolge folgte — Konvention setzen, dann importieren —
-- war `GET /wa-tables/{id}` fuer diese Area tot. Die Schreibpfade sind mit
-- dieser Migration korrigiert (dict statt String bzw. `::text::jsonb`); hier
-- werden die BESTANDSZEILEN nachgezogen.
--
-- `audit_log.detail` ist bewusst NICHT dabei: ein Audit-Trail wird nicht
-- rueckwirkend umgeschrieben. Der Schreibpfad ist nach vorn korrigiert, die
-- Leser bleiben tolerant (`while isinstance(detail, str)` in den Tests).
--
-- Idempotent: die Schleife packt aus, bis der Wert kein String mehr ist, und
-- laesst korrekt gespeicherte Objekte unberuehrt. Ein zweiter Lauf ist ein
-- No-op. Die Obergrenze von 5 Runden ist ein Deckel gegen eine Endlosschleife
-- bei kaputten Daten (eine Runde genuegt fuer den bekannten Fall) — mehr als
-- eine Ebene ist nie entstanden, weil pro Write genau einmal zu viel
-- encodiert wurde.

DO $$
DECLARE
    unwrapped integer;
BEGIN
    FOR i IN 1..5 LOOP
        UPDATE wa_source_convention
           SET convention = (convention #>> '{}')::jsonb
         WHERE jsonb_typeof(convention) = 'string';
        GET DIAGNOSTICS unwrapped = ROW_COUNT;
        EXIT WHEN unwrapped = 0;
        RAISE NOTICE 'wa_source_convention: % Zeile(n) ausgepackt (Runde %)', unwrapped, i;
    END LOOP;

    FOR i IN 1..5 LOOP
        UPDATE workspace
           SET memory_guard = (memory_guard #>> '{}')::jsonb
         WHERE jsonb_typeof(memory_guard) = 'string';
        GET DIAGNOSTICS unwrapped = ROW_COUNT;
        EXIT WHEN unwrapped = 0;
        RAISE NOTICE 'workspace.memory_guard: % Zeile(n) ausgepackt (Runde %)', unwrapped, i;
    END LOOP;
END $$;
