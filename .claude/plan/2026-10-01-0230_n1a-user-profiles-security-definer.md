# N1a: Nutzerprofile (E-Mail, Metadaten) nur ueber eine SECURITY-DEFINER-Funktion

Karte t_4d6a6c68 · Owner-Entscheidung 2026-09-30, N1 = a: „SECURITY DEFINER-Funktion
bzw. View, die nur id, email, raw_user_meta_data fuer uebergebene IDs liefert — KEIN
pauschales GRANT auf auth.users". Basis: origin/main 42e3ac45.
Folgekarte N1b (t_544f2bfd): workspace_repository, gdpr_export_service, bootstrap_service.

## Ziel / Completion-Condition

- Integrationstest als `who2be_app`: `GET /dashboard` 200 mit Anzeigenamen aus dem
  Profil, `GET /members` mit E-Mails, `GET /v1/me` (Lazy-Seed) benennt die
  Personal-Org nach dem E-Mail-Local-Part. Rot-Probe: derselbe Test gegen den
  Code-Stand von origin/main → Dashboard 500.
- Negativtest: Funktion liefert fuer die ID eines Nutzers aus einem fremden
  Mandanten nichts, ohne gesetzten Mandanten nichts.
- `who2be_app` hat weder USAGE auf `auth` noch SELECT auf `auth.users`; EXECUTE
  auf die Funktion haben nur Owner und `who2be_app` (auch bei Default-Privileges).
- Python-DoD aus CONTRIBUTING.md gruen, ≤ 8 Dateien, Changelog-Fragment.

## Schritte

1. [x] Migration `0090_user_profiles_function.sql` (Nummer auf origin/main + allen
   Remote-Branches geprueft: hoechste ist 0089).
2. [x] `core/tenancy.py`: GUC-Name `app.current_user_id` als Konstante
   `USER_SETTING` (SSoT der GUC-Namen) plus `scope_to_self`.
3. [x] `dashboard_repository.py`: Activity-Query ohne `auth.users`-Join, Profile in
   EINER zweiten Query fuer die IDs der Seite; Fehler → ohne Profil (kein 500).
4. [x] `workspace_member_repository.py`: Join auf die Funktion statt auf `auth.users`.
5. [x] `me_repository.py`: Lazy-Seed-Profil ueber die Funktion (Self-Lookup).
6. [x] Test `test_user_profiles_function.py` (who2be_app, Rot-Probe), Changelog.
7. [x] DoD, PR.

## DoD (lokal, gemessen)

- ruff check / format --check gruen, mypy: no issues in 515 source files.
- `WHO2BE_REQUIRE_DB=1 pytest --cov --cov-fail-under=85`: 2555 passed, 0 skipped,
  Coverage 91,64 %; Skip-Budget-Gate OK; Lizenz-Gate OK; Wirkungs-Pruefung OK.

## Belege (gemessen, lokale CI-DB pgvector/pgvector:pg16)

- Rot-Probe (Produktivcode + Migration auf origin/main-Stand, nur neuer Test):
  Dashboard `assert 500 == 200`; Funktion fehlt (`UndefinedFunctionError`).
  Die Vorbedingungs-Probe (who2be_app ohne USAGE auf `auth`) ist auf beiden
  Staenden gruen — sie belegt, dass der Test wirklich als App-Rolle laeuft.
- Mutationsprobe: Mandantenfilter in der Funktion ausgehebelt (`OR true`) →
  Negativtest rot (fremder Nutzer `n1a-b@example.com` sichtbar); Entzug
  fremder Grants abgeschaltet → Grant-Test rot (Probe-Rolle mit EXECUTE).

## Entscheidungen (aus dem Repo belegt)

- **Sichtbarkeit = Mitglieder des aktuellen Workspaces plus Mitglieder seiner Org,
  plus der Aufrufer selbst.** Der Mandant kommt aus `app.current_tenant` (gesetzt im
  RLS-Choke-Point `get_current_workspace`, core/tenancy.py) — dasselbe
  Vertrauensmodell wie die RLS-Policies aus 0037. Die Org wird aus dem Workspace
  abgeleitet, nicht aus `app.current_org`, damit die Funktion an genau einer GUC haengt.
- **Self-Lookup ueber neue GUC `app.current_user_id`, transaktionslokal gesetzt.**
  `/v1/me` laeuft ohne Mandanten (Lazy-Seed: der Nutzer hat noch keinen Workspace).
  Gesetzt wird sie nur in `me_repository` mit `is_local = true` (Muster
  `_scope_to_new_workspace`, workspace_repository.py) — kein Leak in den Pool.
- **plpgsql statt SQL-Funktion.** Ein SQL-Body wird beim Anlegen gegen die
  Tabellen geprueft; in CI/Test-DBs existiert `auth.users` erst durch den
  Test-Stub. plpgsql loest die Tabelle erst zur Laufzeit auf.
- **`search_path = pg_catalog, pg_temp`, alle Tabellen schema-qualifiziert**
  (Schema per `current_schema()` zur Migrationszeit, wie 0036). PostgreSQL 16,
  CREATE FUNCTION, „Writing SECURITY DEFINER Functions Safely": „For security,
  search_path should be set to exclude any schemas writable by untrusted users."
  und „A secure arrangement can be obtained by forcing the temporary schema to be
  searched last. To do this, write pg_temp as the last entry in search_path."
- **EXECUTE: PUBLIC entziehen und zusaetzlich jede weitere Rolle aus der ACL.**
  Dieselbe Doku-Stelle: „by default, execute privilege is granted to PUBLIC for
  newly created functions". Images mit Default-Privileges auf Funktionen (z. B.
  Supabase-Rollen) wuerden EXECUTE sonst explizit vergeben; REVOKE FROM PUBLIC
  traefe das nicht. Die Migration laeuft in einer Transaktion (Runner), es gibt
  kein Zeitfenster mit offener Funktion.
- **Dashboard faellt bei Profil-Fehler auf die User-ID zurueck statt 500** — wie
  `/members` und `/v1/me` es schon tun. So traegt der Fix auch dann, wenn der
  Funktions-Owner in einem Image `auth.users` nicht lesen koennte (nicht gemessen).
- **`_has_password` bleibt unveraendert.** Die Owner-Entscheidung nennt nur
  `id, email, raw_user_meta_data`; ein Passwort-Merkmal gehoert nicht in diese
  Funktion. In der Cloud (nur externe Provider) liefert der bestehende Fallback
  `False`. Offener Punkt fuer N1b/PM.

## Auf Zuruf angenommen

- nichts
