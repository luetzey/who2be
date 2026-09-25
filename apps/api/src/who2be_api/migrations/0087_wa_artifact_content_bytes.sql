-- Migration 0087 — Artifact-Text zaehlt in die Speicher-Quota (Karte W8/P5)
--
-- Owner-Entscheidung vom 2026-09-24: „In die Speicher-Quota einrechnen —
-- Artifact-Text zaehlt wie Dateien, ein Limit fuer alles." Ein zweites,
-- eigenes Artifact-Kontingent stand zur Wahl und wurde ausdruecklich NICHT
-- genommen.
--
-- Bis hierher zaehlte `storage_quota_service` ausschliesslich
-- `wa_blob.size_bytes`. Artifact-Text liegt aber in `wa_artifact.content`
-- (jsonb-Blockliste, 0074) und fiel damit unter KEIN Kontingent: bis
-- `ARTIFACT_CONTENT_MAX_LENGTH` = 500.000 Zeichen je Aufruf, gebremst nur
-- durch `write_limit` (Default 30/min) — rechnerisch 15 MB/min dauerhaft,
-- auch im Free-Tarif.
--
-- WARUM EINE SPALTE UND KEINE SUMME UEBER DEN TEXT.
-- Die naheliegende Loesung waere `sum(octet_length(content::text))` direkt im
-- Gate — ohne Migration. Sie ist die falsche: die Summenabfrage laeuft bei
-- JEDEM Schreibzugriff und muesste dafuer jede `content`-Zeile des Workspace
-- detoasten. 500-KB-jsonb liegt out-of-line in TOAST; die Serialisierung nach
-- `text` erzwingt vollstaendiges Lesen samt Dekompression. Ein Free-Workspace
-- am 100-MiB-Limit heisst dann ~100 MB TOAST-Lesen PRO Schreibanfrage — bei
-- 30 Writes/min waere das Gate selbst der Lastfaktor, den es verhindern soll.
-- `pg_column_size` ist als Abkuerzung untauglich: es liefert je nach Lage
-- komprimierte oder Pointer-Groesse und ist als Grundlage einer VERKAUFTEN
-- Grenze nicht belastbar.
--
-- Stattdessen wird die Groesse materialisiert und bei jedem Content-Write in
-- DERSELBEN Anweisung mitgeschrieben (eine Zeile detoasten, die sowieso
-- geschrieben wird). Die Verbrauchssumme bleibt damit EINE Abfrage ueber zwei
-- billige Aggregate (`STORAGE_USED_SQL`), gelesen werden nur schmale Integer;
-- der Index `wa_artifact_area_idx (workspace_id, area_id)` deckt den Filter.
--
-- WAS GEZAEHLT WIRD: `octet_length(content::text)` — die UTF-8-Bytes der
-- GESPEICHERTEN jsonb-Serialisierung, nicht die Zeichen des rohen Markdown.
-- Bytes, weil das Kontingent `storage_quota_bytes` heisst und gegen
-- `wa_blob.size_bytes` summiert wird; zwei Einheiten in einer Summe waeren
-- nicht ungenau, sondern falsch. Und ein Zeichen ist nicht ein Byte: UTF-8
-- belegt 1-4 Bytes, deutscher Text ~1,05, CJK 3 — wer Zeichen zaehlte, gaebe
-- je Tarif ein- bis viermal so viel Platz, abhaengig von der Sprache des
-- Kunden. Die jsonb-Serialisierung ist zudem das, was tatsaechlich Platz
-- belegt (Block-Overhead `{"block_id":…,"kind":…,"md":…}`, ~40-60 Bytes je
-- Block); fuer eine SPEICHER-Quota ist der belegte Platz das richtige Mass.
--
-- `integer` reicht mit Absicht: ein Artifact ist durch
-- ARTIFACT_CONTENT_MAX_LENGTH auf 500.000 ZEICHEN gedeckelt, also hoechstens
-- ~2 MB plus Block-Overhead — Groessenordnungen unter int4. Anders als bei
-- `storage_quota_bytes` (0084, dort bigint) gibt es hier keinen Ueberlauf.
-- Die Spalte ist NOT NULL DEFAULT 0: 'blob'- und 'table'-Artifacts tragen
-- `content = NULL` (Inhalt liegt hinter `content_ref`) und bleiben bei 0,
-- statt die Summe mit NULL zu vergiften.
--
-- BACKFILL: hier bewusst JA — anders als beim Workspace-Deckel (0086, kein
-- Backfill). Dort waere ein nachtraeglicher Wert eine stille Verschaerfung
-- bestehender Vertraege gewesen; hier ist die Zaehlung des Bestands der
-- eigentliche Auftrag („Vorhandene Artifacts zaehlen ab sofort mit"). Der
-- Backfill ist der einzige Ort, an dem `content::text` ueber den gesamten
-- Bestand laeuft — einmalig zur Migrationszeit statt bei jedem Upload.
--
-- VERHALTENSAENDERUNG, die benannt sein muss: Bestandsnutzer haben ab dieser
-- Migration effektiv WENIGER Platz als vorher. Wer dadurch ueber seiner
-- Grenze liegt, verliert nichts und wird nicht ausgesperrt — das Gate ist ein
-- Vorab-Check an Schreibrouten, Read/Export/Download und DELETE bleiben offen
-- (der „kein Datenverlust"-Vertrag aus 0084). Nur NEUE Writes oberhalb der
-- Grenze werden mit 402 abgewiesen. Die Zahl der betroffenen Orgs ist VOR dem
-- Deploy zu messen (Abfrage unten) — kippt eine Bestands-Org sofort, ist das
-- eine Owner-Entscheidung, keine Implementierung.
--
--   SELECT w.org_id, w.id AS workspace_id,
--          coalesce(b.bytes, 0) AS blob_bytes,
--          coalesce(a.bytes, 0) AS artifact_bytes
--   FROM workspace w
--   LEFT JOIN (SELECT workspace_id, sum(size_bytes) bytes
--              FROM wa_blob GROUP BY 1) b ON b.workspace_id = w.id
--   LEFT JOIN (SELECT workspace_id, sum(content_bytes) bytes
--              FROM wa_artifact GROUP BY 1) a ON a.workspace_id = w.id
--   ORDER BY 3 + 4 DESC;
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS; der Backfill laeuft nur auf Zeilen,
-- die noch auf dem Default stehen und Inhalt tragen (bei Wiederholung leere
-- Treffermenge). Schema-aware (unqualifiziert), Muster 0039/0086.

ALTER TABLE wa_artifact
    ADD COLUMN IF NOT EXISTS content_bytes integer NOT NULL DEFAULT 0;

-- Bestand nachtragen. `content IS NOT NULL` schliesst blob/table aus (die
-- bleiben korrekt bei 0); `content_bytes = 0` macht die Wiederholung guenstig
-- und verhindert, dass ein spaeterer Lauf bereits gezaehlte Zeilen erneut
-- detoastet.
UPDATE wa_artifact
   SET content_bytes = octet_length(content::text)
 WHERE content IS NOT NULL
   AND content_bytes = 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'wa_artifact_content_bytes_check'
          AND conrelid = 'wa_artifact'::regclass
    ) THEN
        ALTER TABLE wa_artifact
            ADD CONSTRAINT wa_artifact_content_bytes_check
            CHECK (content_bytes >= 0);
    END IF;
END
$$;
