-- Migration 0030 — Nur-BlockNote (Track B)
-- Entfernt den `body_format='plain'`-Pfad vollstaendig: `body` ist ab jetzt
-- IMMER ein stringifiziertes BlockNote-JSON-Dokument.
--
-- 1. Altbestaende (plain-Bodies) werden markdown-aware nach BlockNote-Bloecken
--    konvertiert: Headings (#..###), Listen (-,*,1.), Code-Fences (```), Rest
--    Paragraph. Erkennung "ist schon BlockNote" ueber „parst als JSON-Array" →
--    idempotent, unabhaengig vom (gleich entfallenden) body_format.
-- 2. Der `body_format`-Key wird aus allen playbook_version.content entfernt
--    (Model ist `extra="forbid"`).
-- 3. Die `body_format`-Spalte + CHECK an system_prompt_template wird gedroppt.
--
-- Die Konvertierung laeuft ueber temporaere plpgsql-Helfer, die am Ende wieder
-- entfernt werden (kein Schema-Ballast).

CREATE OR REPLACE FUNCTION _w2b_is_json_array(t text) RETURNS boolean AS $$
DECLARE
    v jsonb;
BEGIN
    IF t IS NULL OR length(btrim(t)) = 0 THEN
        RETURN false;
    END IF;
    BEGIN
        v := t::jsonb;
    EXCEPTION WHEN others THEN
        RETURN false;
    END;
    RETURN jsonb_typeof(v) = 'array';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION _w2b_make_block(btype text, btext text, blevel int)
RETURNS jsonb AS $$
DECLARE
    props jsonb;
    content jsonb;
BEGIN
    IF btype = 'heading' THEN
        props := jsonb_build_object(
            'level', GREATEST(1, LEAST(3, COALESCE(blevel, 2))),
            'textColor', 'default', 'backgroundColor', 'default', 'textAlignment', 'left'
        );
    ELSIF btype = 'codeBlock' THEN
        props := jsonb_build_object('language', '');
    ELSE
        props := jsonb_build_object(
            'textColor', 'default', 'backgroundColor', 'default', 'textAlignment', 'left'
        );
    END IF;
    IF btext IS NULL OR btext = '' THEN
        content := '[]'::jsonb;
    ELSE
        content := jsonb_build_array(
            jsonb_build_object('type', 'text', 'text', btext, 'styles', '{}'::jsonb)
        );
    END IF;
    RETURN jsonb_build_object(
        'id', gen_random_uuid()::text,
        'type', btype,
        'props', props,
        'content', content,
        'children', '[]'::jsonb
    );
END;
$$ LANGUAGE plpgsql VOLATILE;

CREATE OR REPLACE FUNCTION _w2b_blocknote_from_markdown(plain text) RETURNS text AS $$
DECLARE
    lines text[];
    ln text;
    blocks jsonb := '[]'::jsonb;
    in_code boolean := false;
    code_buf text := '';
    m text[];
BEGIN
    IF plain IS NULL OR length(plain) = 0 THEN
        RETURN '[]';
    END IF;
    lines := string_to_array(replace(plain, E'\r\n', E'\n'), E'\n');
    FOREACH ln IN ARRAY lines LOOP
        -- Code-Fence-Umschalter.
        IF ln ~ '^\s*```' THEN
            IF in_code THEN
                blocks := blocks || jsonb_build_array(_w2b_make_block('codeBlock', code_buf, NULL));
                in_code := false;
                code_buf := '';
            ELSE
                in_code := true;
                code_buf := '';
            END IF;
            CONTINUE;
        END IF;
        IF in_code THEN
            IF code_buf = '' THEN
                code_buf := ln;
            ELSE
                code_buf := code_buf || E'\n' || ln;
            END IF;
            CONTINUE;
        END IF;
        -- Heading (#..######, geclamped auf 1..3 im make_block).
        m := regexp_match(ln, '^(#{1,6})\s+(.*)$');
        IF m IS NOT NULL THEN
            blocks := blocks || jsonb_build_array(_w2b_make_block('heading', m[2], length(m[1])));
            CONTINUE;
        END IF;
        -- Bullet-Liste.
        m := regexp_match(ln, '^\s*[-*]\s+(.*)$');
        IF m IS NOT NULL THEN
            blocks := blocks || jsonb_build_array(_w2b_make_block('bulletListItem', m[1], NULL));
            CONTINUE;
        END IF;
        -- Numerierte Liste.
        m := regexp_match(ln, '^\s*\d+\.\s+(.*)$');
        IF m IS NOT NULL THEN
            blocks := blocks || jsonb_build_array(_w2b_make_block('numberedListItem', m[1], NULL));
            CONTINUE;
        END IF;
        -- Leerzeile → Absatztrenner (kein eigener Block).
        IF length(btrim(ln)) = 0 THEN
            CONTINUE;
        END IF;
        -- Rest → Paragraph.
        blocks := blocks || jsonb_build_array(_w2b_make_block('paragraph', ln, NULL));
    END LOOP;
    -- Unbeendeter Code-Fence defensiv schliessen.
    IF in_code AND length(code_buf) > 0 THEN
        blocks := blocks || jsonb_build_array(_w2b_make_block('codeBlock', code_buf, NULL));
    END IF;
    -- Leeres Ergebnis → ein leerer Paragraph (BlockNote braucht >= 0 Bloecke;
    -- ein leerer Paragraph ist die natuerliche „leeres Dokument"-Form).
    IF jsonb_array_length(blocks) = 0 THEN
        blocks := jsonb_build_array(_w2b_make_block('paragraph', '', NULL));
    END IF;
    RETURN blocks::text;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- 1a. Playbook-Bodies konvertieren (nur die, die noch kein JSON-Array sind).
UPDATE playbook_version
   SET content = jsonb_set(
       content, '{body}', to_jsonb(_w2b_blocknote_from_markdown(content->>'body'))
   )
 WHERE NOT _w2b_is_json_array(content->>'body');

-- 1b. body_format-Key aus allen Playbook-Versionen entfernen (extra=forbid).
UPDATE playbook_version
   SET content = content - 'body_format'
 WHERE content ? 'body_format';

-- 2. Template-Bodies konvertieren (nur die, die noch kein JSON-Array sind).
UPDATE system_prompt_template_version
   SET content = jsonb_set(
       content, '{body}', to_jsonb(_w2b_blocknote_from_markdown(content->>'body'))
   )
 WHERE NOT _w2b_is_json_array(content->>'body');

-- 3. body_format-Spalte + CHECK von der Template-Zeile entfernen.
ALTER TABLE system_prompt_template
    DROP CONSTRAINT IF EXISTS system_prompt_template_body_format_check;
ALTER TABLE system_prompt_template
    DROP COLUMN IF EXISTS body_format;

-- Helfer wieder entfernen.
DROP FUNCTION IF EXISTS _w2b_blocknote_from_markdown(text);
DROP FUNCTION IF EXISTS _w2b_make_block(text, text, int);
DROP FUNCTION IF EXISTS _w2b_is_json_array(text);
