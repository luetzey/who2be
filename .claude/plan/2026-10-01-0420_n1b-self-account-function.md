# N1b: Eigene Kontodaten nur ueber `w2b_self_account()`

Karte t_544f2bfd · Vorgaenger N1a (PR #741, `w2b_user_profiles`, Migration 0090).
PM-Entscheidung zum Ask-Once-Gate: Option A — neue Self-only-Funktion, die
`w2b_user_profiles` bleibt schmal (Owner-Entscheidung 1 = a: „nur id, email,
raw_user_meta_data"). Basis: origin/main 32a4dde2.

## Ziel / Completion-Condition

- `git grep -nE "FROM auth\.users|JOIN auth\.users" apps/api/src -- ':!*/migrations/*' ':!*/testing/*'`
  ist leer.
- DSGVO-Export als `who2be_app` enthaelt `email`, `created_at`, `last_sign_in_at`
  des Nutzers. Rot-Probe: derselbe Test gegen den Code-Stand von origin/main → rot.
- Negativtest: `w2b_self_account()` liefert nur die Zeile von
  `app.current_user_id`; anderer Nutzer gesetzt → dessen Zeile, nie die fremde;
  ungesetzt → leer, auch mit gesetztem Workspace-Mandanten.
- `/v1/me` als `who2be_app`: `has_password` true fuer Passwortnutzer, false fuer
  OAuth-/Magic-Link-Nutzer. Rot-Probe gegen origin/main.
- EXECUTE nur Owner + `who2be_app`, `search_path` fest, SECURITY DEFINER.
- Python-DoD aus CONTRIBUTING.md gruen, ≤ 8 Dateien, Changelog-Fragment.

## Schritte

1. [x] Migration `0093_self_account_function.sql` (urspruenglich 0091; nach
   Merge von #748/0091 und #747/0092 auf main umnummeriert, kein neuer Inhalt). Muster und Haertung wie 0090.
2. [x] `gdpr_export_service._export_account`: Transaktion + `scope_to_self` +
   `w2b_self_account()`; Fehler → leerer Block (Verhalten wie bisher).
3. [x] `me_repository._has_password`: dito.
4. [x] Docstring `workspace_repository.ensure_personal_workspace`: Zugriffsweg
   `w2b_user_profiles` statt `auth.users`.
5. [x] Tests: `test_user_profiles_function.py` um Export, has_password und
   Negativtest erweitern (Fixture `app_role_client` liegt dort), EXECUTE-Test
   auf beide Funktionen; Fake-Pools in `test_gdpr_export_account.py` auf den
   Transaktionsweg umstellen.
6. [x] Changelog-Fragment, DoD, PR.

## DoD (lokal, gemessen, pgvector:pg16)

- ruff check / format --check gruen, mypy: no issues in 515 source files.
- `WHO2BE_REQUIRE_DB=1 pytest --cov --cov-fail-under=85`: 2423 passed, 0 skipped,
  Coverage 92,01 %; Skip-Budget-Gate OK; Lizenz-Gate OK; Wirkungs-Pruefung OK.
- Grep-Kriterium leer (exit 1).
- Rot-Probe (Service/Repo auf origin/main): Export `assert None == '…'`,
  `has_password` `assert False is True`, 3 Unit-Tests rot.
- Mutation (Funktion ohne Self-Filter) vom Negativtest gefangen.

## Entscheidungen

- `bootstrap_service.py` bleibt unveraendert: der Docstring sagt nur, dass die
  Tenancy-Tabellen keinen FK auf `auth.users` tragen. Das stimmt weiter und
  beschreibt keinen Lesezugriff — eine Aenderung waere kosmetisch und kostete
  eine der acht Dateien.
- Funktion ohne Parameter: die Identitaet kommt ausschliesslich aus der GUC,
  die die App transaktionslokal setzt (`scope_to_self`, core/tenancy.py). Ein
  ID-Parameter waere eine zweite, abweichende Quelle.
