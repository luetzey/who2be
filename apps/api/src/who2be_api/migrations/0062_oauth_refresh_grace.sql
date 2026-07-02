-- 0062_oauth_refresh_grace.sql
--
-- Grace-Window fuer die Refresh-Rotation (RFC 9700 §4.14.2): ein soeben
-- rotierter Refresh-Token darf innerhalb eines engen Fensters GENAU EINMAL als
-- gutartiger Retry (verlorene Token-Antwort / paralleler Refresh) erneut
-- eingeloest werden, statt die ganze Kette zu killen.
--
-- `grace_consumed_at` macht diesen Grace-Einloese-Pfad atomar single-use (analog
-- `consumed_at`): der zweite Grace-Versuch fuer denselben Token faellt durch und
-- loest die Replay-Detection aus. Ohne diese Spalte koennte aus einem
-- 30-s-Race eine unbegrenzte Zahl unabhaengiger Ketten-Zweige entstehen.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS. Grants unveraendert (who2be_app hat
-- bereits UPDATE auf oauth_refresh_token, Migration 0049).

ALTER TABLE oauth_refresh_token ADD COLUMN IF NOT EXISTS grace_consumed_at timestamptz;
