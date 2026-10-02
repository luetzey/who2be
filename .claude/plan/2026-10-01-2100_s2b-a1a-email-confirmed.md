# S2b A1a: `w2b_self_account()` liefert `email_confirmed`

Karte t_b7c3bb45 (S2b, Einladungsmail ohne Token). Basis: origin/main 188e16e7.

## Owner-Entscheidungen (bindend)

- 2026-10-01 „1.a, 2.a, 3.b, 4. b": Frage 1 = A. Der Mail-Link traegt keinen
  Einladungs-Token mehr. Nach dem Login zeigt die Seite die offenen Einladungen
  fuer genau die E-Mail des Kontos (Pending-Endpunkte, an E-Mail-Besitz
  gebunden). Der Token bleibt nur fuer den manuell geteilten Link.
- 2026-10-01 „A" (Weiche E-Mail-Besitz): Die Pending-Endpunkte pruefen
  serverseitig `auth.users.email_confirmed_at IS NOT NULL`, und zwar ueber die
  SECURITY-DEFINER-Funktion `w2b_self_account()` (0093). Sie bekommt dafuer eine
  Spalte `email_confirmed`, per neuer Migration, ohne 0093 zu aendern.

## Zuschnitt S2b (je PR <= 8 Dateien, Reihenfolge fest)

1. **A1a (dieser PR):** Migration 0094 `w2b_self_account()` + `email_confirmed`;
   Auth-Stub und `seed_auth_user` der Testhilfen um `email_confirmed_at` ergaenzt;
   Tests. Kein Endpunkt, kein Verhalten nach aussen.
2. A1b: `GET /v1/invitations/pending` (403 `invitation_email_unconfirmed` ohne
   Bestaetigung, 403 `invitation_email_required` ohne Claim).
3. A2: `POST /v1/invitations/pending/{invitation_id}/accept`.
4. W: Web (Pending-Seite, Fragment -> Body, i18n), wird selbst geteilt.
5. M: Mailer ohne Token, Compose `GOTRUE_MAILER_URLPATHS_INVITE`, Betriebsdoku
   (SMTP + `GOTRUE_MAILER_AUTOCONFIRM=false` als Voraussetzung, Warnung), Log-Probe.

## Completion-Condition A1a

- `SELECT email_confirmed FROM w2b_self_account()` als `who2be_app` mit gesetzter
  `app.current_user_id`: true bei `email_confirmed_at` gesetzt, false bei NULL.
  Ohne GUC weiterhin keine Zeile, fremde Zeilen nie.
- Rot-Probe: neuer Test gegen origin/main (ohne 0094) rot.
- Haertung unveraendert: SECURITY DEFINER, `search_path = pg_catalog, pg_temp`,
  EXECUTE nur Owner + `who2be_app` (parametrisierter ACL-Test laeuft weiter).
- Python-DoD aus CONTRIBUTING.md gruen, Changelog-Fragment.

## Schritte

1. [x] Migration `0094_self_account_email_confirmed.sql`: DROP + CREATE (der
   Rueckgabetyp aendert sich, `CREATE OR REPLACE` geht dafuer nicht), Haertung
   wie 0093. Der Runner faehrt jede Datei in einer Transaktion.
2. [x] `testing/workspace_setup.py`: Stub-Spalte `email_confirmed_at`,
   `seed_auth_user(..., email_confirmed_at=None)`.
3. [x] `test_user_profiles_function.py`: Spaltenmenge + bestaetigt/unbestaetigt.
4. [x] Changelog-Fragment, DoD, Rot-Probe, PR.

## DoD (lokal gemessen, pgvector:pg16, DB who2be_s2b)

- ruff check und format --check gruen, mypy: no issues in 524 source files.
- `WHO2BE_REQUIRE_DB=1 pytest --cov --cov-fail-under=85`: 2607 passed, 0 skipped, 92,91 %.
- Skip-Budget OK, Lizenz-Gate exit 0, check_effectful_tests ohne Befund,
  changelog_fragments check exit 0.
- Rot-Probe auf eigener DB who2be_s2b_red ohne 0094: 2 failed (Spaltenmenge;
  `email_confirmed` existiert nicht). Danach 0094 auf dieselbe DB gefahren
  (Upgrade-Pfad ueber 0093): gruen. ACL, SECURITY DEFINER und search_path sind
  unveraendert.
