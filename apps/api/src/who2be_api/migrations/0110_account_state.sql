-- 0110 — Konto-Zustand ohne Tutorial-Bezug: „Was ist neu“ zuletzt geoeffnet
-- (ADR-0060 §4, Onboarding P5-API, Spec §5.4, Owner O7 a).
--
-- `news_seen_at` traegt den Punkt am „?“-Menue: sichtbar, wenn es eine News
-- nach diesem Zeitpunkt gibt. Der Wert gilt fuer das ganze Konto, nicht fuer
-- ein Tutorial — deshalb eine eigene Tabelle statt einer Spalte an
-- `tutorial_state` (dort ist der Schluessel (Nutzer, Tutorial), ein
-- Pseudo-Tutorial waere eine zweite Bedeutung derselben Zeile). Eine eigene
-- Konto-Tabelle gibt es sonst nicht: `auth.users` gehoert GoTrue, und keine
-- Migration fasst sie an (vgl. 0083/0093).
--
-- Muster 0108: kontoweit, keine Mandantenspalte, keine RLS-Policy; jede Query
-- der App filtert auf `user_id` des authentifizierten Menschen. Kein FK auf den
-- GoTrue-User — die Konto-Loeschung raeumt explizit in `purge_account_data`.
-- Rein additiv: nur CREATE TABLE IF NOT EXISTS und ein Grant.

CREATE TABLE IF NOT EXISTS account_state (
    user_id      uuid PRIMARY KEY,
    news_seen_at timestamptz,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- DML fuer die App-Rolle (Cloud); DELETE fuer den Konto-Purge. pg_roles-Guard
-- fuer On-Prem/Dev ohne `who2be_app`.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON account_state TO who2be_app;
    END IF;
END
$$;
