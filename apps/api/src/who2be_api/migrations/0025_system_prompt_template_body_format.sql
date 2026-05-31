-- Migration 0025 — system_prompt_template.body_format (Welle 5)
--
-- Ergaenzt die `body_format`-Spalte auf `system_prompt_template`.
-- `'plain'` (Default) bedeutet der Body ist reiner Text mit Liquid-Style-
-- Placeholders; `'blocknote'` bedeutet der Body ist Stringified-BlockNote-JSON
-- mit Custom-Inline-Blocks vom Typ `placeholder`.
--
-- Bestehende Templates erhalten `'plain'` per DEFAULT — kein Update noetig,
-- sie bleiben funktional.
--
-- Idempotenz: Die ALTER TABLE ... ADD COLUMN-Variante pruefen wir ueber
-- `information_schema`; der CHECK-Constraint wird per `pg_constraint`-Probe
-- nur hinzugefuegt, wenn er noch nicht existiert (Muster aus Migration 0020).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name   = 'system_prompt_template'
           AND column_name  = 'body_format'
    ) THEN
        ALTER TABLE system_prompt_template
            ADD COLUMN body_format text NOT NULL DEFAULT 'plain';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname    = 'system_prompt_template_body_format_check'
           AND conrelid   = 'system_prompt_template'::regclass
    ) THEN
        ALTER TABLE system_prompt_template
            ADD CONSTRAINT system_prompt_template_body_format_check
            CHECK (body_format IN ('plain', 'blocknote'));
    END IF;
END $$;
