# ADR-0055 — Mandantentrennung: Trennungskonzept (gemeinsame Datenbank mit RLS, keine Datenbank je Organisation)

- Status: **Accepted** (Owner, 2026-09-30). Die Entscheidung steht im Wortlaut
  in Abschnitt 2.
- Datum: 2026-10-01
- Gemessen gegen: `origin/main` @ `42e3ac45`. Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: Recherche „Eigene PostgreSQL-Datenbank pro Organisation?“
  (Karte t_77b8f502, Stand 2026-09-30, Bericht
  `mandantentrennung-db-pro-org-2026-09-30.md` mit Belegordner `-belege/`,
  außerhalb des Repos). „Bericht §n“ verweist auf dessen Abschnitte. Dazu
  kommt ein interner Audit der Mandantentrennung vom 2026-09-30 (Karte
  t_5df7548a). Seine Einzelbefunde sind nicht öffentlich, siehe Abschnitt 5.
- Bezug: ADR-0019 (Tenant-Hierarchie User → Organization → Workspace),
  ADR-0023 (Multi-User-RBAC), ADR-0048 (Blob-Storage je Workspace), ADR-0049
  (Tabellen-Store, SQLite je WorkArea), ADR-0031 (Aufbewahrung der
  Entitlement-Historie).
- Umfang: **nur Dokumentation.** Diese ADR ändert keinen Code, kein Schema und
  keine Migration. Sie ist das dokumentierte Trennungskonzept, das BSI C5
  OPS-24 und die Orientierungshilfe Mandantenfähigkeit verlangen.
- **Keine Rechtsberatung.** Die Normstellen sind wörtlich zitiert und technisch
  eingeordnet. Die rechtliche Bewertung im Einzelfall, besonders die Rolle als
  Auftragsverarbeiter oder Verantwortlicher (Abschnitt 8), gehört zu einer
  fachkundigen Beratung.

## Inhalt

1. Kontext und Normlage
2. Entscheidung (Owner-Wortlaut)
3. Verworfene Option: eigene Datenbank je Organisation
4. Das Trennmodell
5. Restrisiken (gesondert ausgewiesen)
6. Offene Weiche: strikte Policies für die Auflösungspfade
7. Nachweisweg
8. Offene Punkte
9. Ausblick
10. Konsequenzen

---

## 1. Kontext und Normlage

Der Owner hat gefragt, ob jede Organisation eine eigene PostgreSQL-Datenbank
bekommen soll, damit Nutzer nie an fremde Elemente kommen und die Daten einer
Organisation leicht herauslösbar sind. Die Recherche prüft dafür, was Norm und
Aufsicht verlangen und was vergleichbare Anbieter tun. Außerdem prüft sie, was
die Option für Who2Be kosten würde und welche belegten Vorfälle sie verhindert
hätte.

Die tragenden Normstellen, wörtlich (Bericht §1, Belege `normen/`):

- **DSGVO Art. 32 Abs. 1** verlangt Maßnahmen „unter Berücksichtigung des
  Stands der Technik, der Implementierungskosten […] um ein dem Risiko
  angemessenes Schutzniveau zu gewährleisten“. Von Trennung, Mandanten oder
  Datenbanken steht dort nichts (Bericht §1.1).
- **DSGVO Art. 28 Abs. 3 lit. g**: Der Vertrag sieht vor, dass der
  Auftragsverarbeiter „nach Abschluss der Erbringung der
  Verarbeitungsleistungen alle personenbezogenen Daten nach Wahl des
  Verantwortlichen entweder löscht oder zurückgibt und die vorhandenen Kopien
  löscht“. Das ist eine Pflicht zu Löschung und Rückgabe je Kunde, aber
  keine Vorgabe zur Speicherform.
- **OH Mandantenfähigkeit** (DSK-AK Technik, V1.0 vom 11.10.2012): „In
  begründeten Fällen kann daher auch eine gemeinsame Speicherung mit
  mandantenbezogener Kennzeichnung der Daten zulässig sein. […] Die
  Datenverarbeitung muss dabei zwingend durch technische Maßnahmen getrennt
  voneinander erfolgen.“ Als Umsetzung nennt sie ausdrücklich: „Alle Mandanten
  nutzen dieselben Tabellen in einer einzigen, gemeinsamen Datenbank […] Jeder
  Datensatz wird um ein Attribut für den jeweils zutreffenden Mandanten
  ergänzt.“ Physische Trennung ist nur bei „sehr hohem Schutzbedarf“
  „zwingend geboten“.
- **SDM-Baustein 50 „Trennen“** (V1.0, gültig seit 06.10.2020) führt als Stufe c
  „typisch: Mandantentrennung durch Regeln innerhalb einer Datenbankinstanz“.
  Selbst Stufe d, „mehrere Datenbank-Instanzen“, zählt dort noch als
  „logische Trennung“. Die konkreteste MUSS-Stelle für Who2Be steht in
  Prüfschritt 5: „Bei Beendigung der Auftragsverarbeitung für einen Mandanten
  muss den Anforderungen nach Herausgabe und Löschung der verbliebenen Daten
  entsprochen werden können, ohne dass dies Auswirkungen auf die Verarbeitung
  anderer Mandanten hat.“
- **BSI C5:2020 OPS-24** (Basiskriterium): Kundendaten sind „gemäß eines
  dokumentierten Konzepts auf Basis einer Risikoanalyse gemäß OIS-07 sicher und
  strikt separiert“. Als Mittel nennt C5 ausdrücklich „Zugriffslisten, Tagging
  (Auszeichnung des Datenbestandes)“. C5 ist ein freiwilliger Prüfkatalog und
  kein Gesetz.

Was die OH für das Konzept selbst verlangt, gibt dieser ADR ihre Gliederung
vor:

> „Risiken, die nicht oder nur zum Teil durch die Datensicherheits- und
> Datenschutzmaßnahmen ausreichend reduziert wurden, müssen explizit
> ausgewiesen werden. Risiken, die aufgrund einer unzureichenden Trennung der
> Mandanten bestehen, sind gesondert aufzuführen.“
> — OH Mandantenfähigkeit, Restrisikobetrachtung

## 2. Entscheidung (Owner-Wortlaut)

Owner-Entscheidung vom 2026-09-30, Wortlaut: **„1. A, 2.A, 3. B“**

| Nr. | Frage | Gewählt |
|---|---|---|
| 1 | E-Mail-Anzeige in der Cloud-Edition (`auth.users`) | **a:** eine `SECURITY DEFINER`-Funktion bzw. View, die nur `id`, `email` und `raw_user_meta_data` für übergebene IDs liefert. **Kein** pauschales `GRANT` auf `auth.users`, denn `auth.users` hat kein RLS, und jeder Mandant sähe alle E-Mails. |
| 2 | Einladungs-Token | **a:** Der Token wandert aus dem URL-Pfad ins URL-Fragment (`/invitations/accept#token=…`). Die Web-App liest ihn clientseitig und schickt ihn im Body an `POST /v1/invitations/accept`. Alte Links werden übergangsweise weiter unterstützt. |
| 3 | Mandantentrennung | **b:** **Keine** eigene Datenbank pro Organisation. Die gemeinsame Datenbank mit RLS (ADR-0019) bleibt und wird gehärtet: Trennungskonzept dokumentieren (diese ADR), Control-Plane-Tabellen absichern, API-Isolationstests, Export/Import je Org. |

Diese ADR hält Punkt 3 fest. Die Punkte 1 und 2 stehen hier, weil sie
dieselbe Grenze betreffen: Punkt 1 legt fest, dass auch der Zugriff auf die
Auth-Daten mandantengebunden bleibt. Umgesetzt werden beide in eigenen
Paketen.

## 3. Verworfene Option: eigene Datenbank je Organisation

Die Recherche hat drei Optionen verglichen (Bericht §5):

- **a) DB pro Org für alle, bei Registrierung angelegt.** Verworfen.
- **b) Status quo (Pool + RLS, ADR-0019) mit gezielter Härtung.** Gewählt.
- **c) Hybrid: b als Standard, „eigene Instanz“ als Bezahlstufe.** Nicht
  gewählt, siehe Abschnitt 9.

Die Begründung für das Verwerfen von a steht im Bericht §5, wörtlich (nur die
Beleg-Kennzeichnungen [B]/[E] sind weggelassen):

> 1. Keine Rechtsquelle verlangt a. Die einschlägigen Aufsichtspapiere lassen b
>    ausdrücklich zu.
> 2. Der Sicherheitsgewinn von a deckt eine Fehlerklasse ab, die Who2Be schon
>    testet, und lässt die Fehlerklassen offen, die in den belegten Vorfällen
>    dominieren.
> 3. Die Kosten von a treffen genau das Free-Segment und den Server mit 8 GB.
> 4. Der Teil des Owner-Wunsches, der wirklich trägt („Daten einer Org leicht
>    herauslösen“), ist mit einem Werkzeug erreichbar, das nicht von der
>    Speicherform abhängt. Blobs und SQLite sind heute schon je Workspace
>    getrennt.

### 3.1 Eine eigene Datenbank im selben Cluster ist keine physische Trennung

AWS führt „DB pro Tenant in gemeinsamer Instanz“ als Bridge-Modell und
schreibt dazu: „it refers to a logical construct of the PostgreSQL database
management system to separate data.“ Das SDM nennt selbst getrennte
Datenbank-Instanzen noch „logische Trennung“, physisch ist dort erst eigene
Hardware (Bericht §1.2, §2, §6 Nr. 3). Eine physische Trennung wäre also erst
eine eigene Instanz oder ein eigener Server. Das ist Option c, nicht a.

### 3.2 Was eine DB-Grenze verhindert hätte und was nicht

Bericht §4 ordnet die belegten Vorfälle zu (Quellen `vorfaelle/`):

| Vorfall | DB pro Org hätte … |
|---|---|
| CVE-2024-10976 (RLS-Engine wendet falsche Policy an) | verhindert. |
| Asana MCP 2025: „logic flaw in the MCP system“ | Unklar. Bei vergessenem Filter ja. Wird der Mandant falsch aufgelöst, nein, dann öffnet die App eben die falsche DB. |
| OpenAI ChatGPT 2023: Cache lieferte fremde Daten | nicht verhindert: Der Fehler lag oberhalb der DB. |
| Atlassian 2022: Skript löschte ganze Sites | Die Löschung nicht verhindert. Die Wiederherstellung je Kunde wäre leichter gewesen: „only a portion of data stores that are continuing to be used by other customers“. |

Übertragen auf Who2Be (Bericht §4): Den Mandanten löst die Anwendung auf (JWT →
Membership-Check → `app.current_tenant`). Ein Fehler in genau diesem Pfad öffnet
mit DB pro Org die falsche DB statt der falschen Zeilen, gewonnen ist also
nichts. Wirksam wäre die DB-Grenze gegen „neue Tabelle ohne Policy“ und gegen
Fehler der RLS-Engine. Die erste Fehlerklasse fängt heute ein Coverage-Test ab
(Abschnitt 7).

### 3.3 Was für die verworfene Option spricht und bestehen bleibt

Bericht §6 Nr. 5, wörtlich: „Die OH Cloud 2014 nennt die gemeinsame Instanz als
Risiko (individuelle Backupzeiträume). Die PostgreSQL-Doku empfiehlt getrennte
DBs für einander fremde Nutzer. Gegen RLS-Engine-Fehler und vergessene
Policies ist eine DB-Grenze wirksam.“

Die OH Cloud Computing 2.0 (2014) knüpft das Risiko an den Fall, dass „die
gleiche Datenbankinstanz aus Kostengründen für verschiedene Cloud-Anwender
eingesetzt wird und damit auf Datenseparierung verzichtet wird“. Who2Be
verzichtet nicht auf Datenseparierung. Der Rest-Einwand bleibt trotzdem stehen
und ist in Abschnitt 5 als R6 ausgewiesen: Kundenindividuelle Backupzeiträume
sind mit einer gemeinsamen Datenbank nicht machbar.

### 3.4 Kosten, die a für Who2Be hätte

Aus Bericht §3 (Einschätzung auf Basis belegter Repo-Fakten):

- Jede Registrierung legt eine Personal-Org an. Jede Free-Anmeldung würde also
  zu `CREATE DATABASE` mit allen Migrationen, und zwar außerhalb der
  Registrierungs-Transaktion.
- Jeder Deploy müsste Migrationen über N Datenbanken fahren, mit Teilerfolgen
  und Wiederaufnahme.
- Eine Verbindung gehört immer zu genau einer Datenbank. Nötig wären ein Pool je
  aktiver Org oder PgBouncer, und der heutige Choke-Point für die Mandanten-GUCs
  müsste umgebaut werden.
- Die Steuerungsdaten bleiben zentral: GoTrue, Organisation, Mitgliedschaften,
  Billing, OAuth. Es entstünde ein Zwei-Ebenen-System mit einem Routing-Layer
  Org → DB.
- Eine Punkt-in-Zeit-Wiederherstellung je Org gäbe es trotzdem nicht. Die
  PostgreSQL-Doku sagt dazu: „can only support restoration of an entire
  database cluster, not a subset“.
- Der Umbau wären mindestens neun Pakete, die meisten davon seriell, weil sie
  dieselben Kerndateien berühren.

Der Rückweg spricht ebenfalls für b (Bericht §5): Von b zu c oder a bleibt der
Weg offen, weil jede Inhaltszeile `workspace_id` trägt. Von a zurück zu b wäre
teuer. „Wer zögert, wählt b. Dieser Weg verbaut nichts.“

## 4. Das Trennmodell

Who2Be nutzt das **Pool-Modell**: eine gemeinsame PostgreSQL-Datenbank, in der
jede Zeile ihren Mandanten trägt. Die Trennung wird in zwei Linien technisch
durchgesetzt. Das entspricht der in der OH genannten Variante „dieselben
Tabellen in einer einzigen, gemeinsamen Datenbank“ und den C5-Mitteln
„Zugriffslisten“ und „Tagging“.

### 4.1 Mandantenschlüssel (Hierarchie aus ADR-0019)

`User → org_member → Organization → Workspace → Entity`. Inhaltstabellen
tragen `workspace_id` (`NOT NULL`, FK). Organisationsbezogene Tabellen wie
Entitlement und Usage tragen `org_id`. Mitgliedschaften gibt es je Ebene
(`org_member`, `workspace_member`). Ein API-Token ist auf genau einen Workspace
festgelegt.

### 4.2 Erste Linie: Anwendungsschicht

- Workspace-gebundene Endpunkte liegen unter `/v1/workspaces/{workspace_id}/…`.
  Die Dependency `apps/api/src/who2be_api/core/security.py#get_current_workspace`
  prüft die Mitgliedschaft bzw. die Token-Bindung und liefert sonst 403
  (ADR-0019, ADR-0023).
- Jedes Repository filtert ausdrücklich auf `workspace_id` (ADR-0019,
  Konsequenzen).

### 4.3 Zweite Linie: Row Level Security und Mandanten-GUCs

- Einziger Choke-Point:
  `apps/api/src/who2be_api/core/tenancy.py#tenant_scope` legt Workspace und Org
  des Requests in einen ContextVar. Der Pool-Callback
  `apps/api/src/who2be_api/core/tenancy.py#apply_tenant_settings` setzt bei
  jedem Checkout die Session-GUCs `app.current_tenant` und `app.current_org`.
  Beim Release setzt asyncpg die Verbindung per `RESET ALL` zurück, sodass kein
  Mandant in den nächsten Checkout gelangt.
- Policies (`tenant_isolation`) vergleichen die Mandantenspalte mit
  `NULLIF(current_setting(…, true), '')::uuid`. Es gibt zwei Muster:
  - **strikt** für die Inhaltstabellen: Ohne gesetzten Mandanten passt keine
    Zeile, die Policy ist also fail-closed
    (`apps/api/src/who2be_api/migrations/0037_rls_policies.sql`).
  - **permissiv, solange kein Mandant gesetzt ist** für Tabellen, die vor der
    Mandantenauflösung gelesen oder geschrieben werden müssen. Ist ein Mandant
    gesetzt, filtern auch sie strikt. Die Begründung je Tabelle steht in den
    Migrationsköpfen
    (`apps/api/src/who2be_api/migrations/0037_rls_policies.sql`,
    `apps/api/src/who2be_api/migrations/0050_rls_workspace_invitation.sql`,
    `apps/api/src/who2be_api/migrations/0068_rls_control_plane.sql`). Das
    Restrisiko dazu ist R1.
- RLS ist eingeschaltet (`ENABLE`), aber nicht erzwungen (`FORCE`). Der Owner
  der Tabellen umgeht RLS (Restrisiko R2).

### 4.4 Rollen

| Rolle | Wer | RLS |
|---|---|---|
| `who2be_app` | Laufzeit-Pool der Cloud-Edition (`APP_DATABASE_URL`). `LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`, nur DML auf App-Tabellen (`apps/api/src/who2be_api/migrations/0036_rls_app_role.sql`) | wird gefiltert |
| Owner (`DATABASE_URL`) | Migrationen (`who2be-migrate`), dazu serverseitige Wartungsjobs ohne Nutzereingabe, siehe R2. On-Prem und Dev verbinden ganz als Owner. | umgeht RLS |

Ein Boot-Guard verweigert in der Cloud den Start, wenn der App-Pool als
Superuser oder mit `BYPASSRLS` verbindet
(`apps/api/src/who2be_api/core/db.py#Database._assert_rls_enforced`).
Append-only-Tabellen wie der Statusverlauf und das Audit-Log entziehen
`who2be_app` zusätzlich `UPDATE` und `DELETE`
(`apps/api/src/who2be_api/migrations/0044_audit_append_only.sql`).

### 4.5 Speicher außerhalb von Postgres

- **Blobs** (ADR-0048) liegen unter dem Key
  `blobs/{workspace_id}/{sha256}`
  (`apps/api/src/who2be_api/blobstore/port.py#blob_key`). Es gibt keine
  Deduplizierung über Workspaces hinweg.
- **Tabellen-Store** (ADR-0049): eine SQLite-Datei je WorkArea unter
  `{workspace_id}/{area_id}.sqlite`
  (`apps/api/src/who2be_api/tablestore/engine.py#TableStore.db_path`).

Beide Speicher sind schon heute physisch je Workspace getrennt und damit im
Sinne des Owner-Wunsches herauslösbar (Bericht §3). Wie sie beim Löschen
abgeräumt werden, steht in Abschnitt 4.6.

### 4.6 Löschung und Rückgabe je Organisation

- **Löschung:** Der Purge-Job löscht eine Organisation in einer
  Owner-Transaktion. Die Kaskade räumt Workspaces, Entities, Versionen,
  Entitlement und Usage ab
  (`apps/api/src/who2be_api/repositories/account_repository.py#PgAccountPurgeRepository.purge_organization`).
  Die Speicher außerhalb von Postgres hängen an keinem FK. Die Blob-Objekte
  räumt danach der Blob-Sweep ab, mit 24 h Karenz
  (`apps/api/src/who2be_api/core/purge.py#cleanup_orphan_blobs`). Die
  SQLite-Dateien eines gelöschten Workspaces lässt der Sweep bewusst liegen
  (`apps/api/src/who2be_api/core/purge.py#cleanup_deleted_area_stores`), sie
  entfernt der Betreiber. Wie Löschung und Aufbewahrung je Speicher im
  Einzelnen laufen, steht in `docs/compliance/data-retention-and-erasure.md`
  §4a. Die Löschung wirkt sich nicht auf andere Mandanten aus (SDM
  Prüfschritt 5). Zwei Lücken bleiben, sie sind als R4 ausgewiesen.
- **Rückgabe:** Heute gibt es nur einen DSGVO-Export je Nutzer. Ein Export und
  Import je Organisation ist Teil der Owner-Entscheidung und als eigenes Paket
  geplant (Abschnitt 10). Er deckt die Rückgabe nach Art. 28 Abs. 3 lit. g ab,
  das Zurückspielen einer einzelnen Org und später den Umzug in eine eigene
  Instanz.

## 5. Restrisiken (gesondert ausgewiesen)

Die OH verlangt, Risiken aus unzureichender Trennung „gesondert aufzuführen“.
Die folgende Liste tut das. Das Repo ist öffentlich, und nach CONTRIBUTING
§„What must not go public“ nennt sie die Risiken deshalb als Klassen. Sie nennt
keine heute offene Fundstelle und keinen Weg, eine Grenze zu überschreiten. Die
konkrete Zuordnung mit Tabellen und Messwerten steht im internen Audit und auf
den Board-Karten. Wer das Konzept prüft (Testat, Auftraggeber), bekommt sie dort
auf Anfrage.

Eine IDOR-Stichprobe über REST und MCP mit zwei echten Mandanten fand am
2026-09-30 **kein** Leck. Keines der folgenden Risiken ist ein bekannter
Datenabfluss. Sie beschreiben, wo die zweite Linie (RLS) heute fehlt oder
schwächer ist als die erste.

| # | Restrisiko | Wirkung | Behandlung |
|---|---|---|---|
| R1 | **Permissive Policies in den Auflösungspfaden.** Ein Teil der Policies filtert nicht, solange kein Mandant gesetzt ist (Login, Token-Lookup, Einladung, OAuth-Code, Billing-Webhook). In diesen Pfaden trägt allein die Anwendungsschicht die Trennung. | Ein Abfragefehler in einem Steuerpfad ohne Mandanten-Kontext würde von RLS nicht aufgefangen. | Bewusst so, die Begründung steht in den Migrationen 0037, 0050 und 0068. Wie die Policies strikt werden, ist offen (Abschnitt 6). |
| R2 | **RLS nicht erzwungen, Owner-Verbindungen zur Laufzeit.** Keine Tabelle hat `FORCE ROW LEVEL SECURITY`. Der Owner umgeht RLS. Zur Laufzeit verbinden drei serverseitige Pfade als Owner: der Builder-Content-Sync beim Start (`apps/api/src/who2be_api/main.py#lifespan`), der Chunk-Backfill (`apps/api/src/who2be_api/core/chunk_backfill.py#_run`) und der Purge-Job (`apps/api/src/who2be_api/core/purge.py#_run`). | Ein Fehler in diesen Jobs wirkt mandantenübergreifend. Keiner der Pfade verarbeitet Nutzereingaben. | Akzeptiert. `FORCE` würde nur wirken, wenn der Owner kein Superuser wäre. Ein Nicht-Superuser-Owner wird zusammen mit Abschnitt 6 geprüft. |
| R3 | **Steuer-Tabellen ohne zweite Linie.** Die Stammdaten von Organisation und Workspace, der Statusverlauf und einzelne Steuer-Tabellen haben bis zur Härtung keine eigene Policy. Der Coverage-Test nimmt `workspace` ausdrücklich aus, der Statusverlauf hat keine Mandantenspalte. | Für diese Tabellen gibt es bis zur Härtung nur die Anwendungsschicht. | Wird gehärtet (Owner-Entscheidung 3, „Control-Plane-Tabellen absichern“): Policies für Organisation und Workspace, eine Mandantenspalte und eine strikte Policy für den Statusverlauf. Die globale OAuth-Client-Registry bleibt bewusst ohne Mandant. |
| R4 | **Reste nach dem Org-Purge.** (a) Der Statusverlauf hängt über `entity_id` an den Entities, hat aber keinen FK und keine Kaskade. Nach dem Löschen einer Organisation bleiben die Zeilen stehen. Akteurs-IDs werden beim Konto-Purge anonymisiert. (b) Die SQLite-Dateien des Tabellen-Stores bleiben liegen, bis der Betreiber sie entfernt (Abschnitt 4.6). | Rest-Metadaten (Entity-ID, Statuswechsel, Zeitpunkt, Notiz) und Tabelleninhalte bleiben nach der Löschung bestehen. Das betrifft Löschung und Rückgabe (Art. 28 Abs. 3 lit. g, SDM Prüfschritt 5). | (a) wird mit R3 behoben: Mit der Mandantenspalte räumt der Org-Purge den Statusverlauf ab, ein Test belegt das. (b) ist bewusst so (ein falsch konfigurierter Purge soll keine fremden Dateien löschen) und als Betreiber-Schritt dokumentiert. |
| R5 | **Fehler der RLS-Engine.** Ein Fehler in PostgreSQL selbst (Beispiel CVE-2024-10976) kann eine falsche Policy anwenden. | Eine DB-Grenze hätte das verhindert (Abschnitt 3.2). | Akzeptiert. Für Who2Be ist das Risiko gering: eine App-Rolle, keine rollenspezifischen Policies, aktuelles Image (Bericht §4). Patch-Stand über die Image-Pflege. |
| R6 | **Keine kundenindividuellen Backup- und Wiederherstellungs-Parameter.** Ein Dump gilt für alle Mandanten, und eine Punkt-in-Zeit-Wiederherstellung geht nur für den ganzen Cluster. | Der Rest-Einwand der OH Cloud 2014 bleibt bestehen (Abschnitt 3.3). Eine einzelne Org lässt sich nur mit Werkzeug zurückspielen. | Teilweise behandelt durch Export/Import je Org. Vollständig erst mit eigener Instanz (Abschnitt 9). |

Nicht als Restrisiko geführt, weil die Anwendung sie absichtlich überschreitet:
geteilte Einladungen und die Liste der eigenen Organisationen eines Nutzers
(`/v1/me`). Für sie gelten die Prüfungen der Anwendungsschicht.

## 6. Offene Weiche: strikte Policies für die Auflösungspfade

Damit die Policies aus R1 strikt werden können, brauchen die Auflösungspfade
einen anderen Weg an ihre Zeilen. Der Audit nennt das ausdrücklich eine
Architekturfrage für eine ADR und kein einzelnes Paket. **Diese ADR entscheidet
die Weiche nicht.** Die Optionen:

| Option | Kern | Pro | Contra |
|---|---|---|---|
| **A — eigene, eng gefasste GUC** | Statt „kein Mandant ⇒ alles“ setzt der Steuerpfad `app.control_plane = <zweck>`. Die Policy lässt ohne Mandant nur Zeilen für genau diesen Zweck durch. | Bleibt im bestehenden GUC-Muster und im Choke-Point (`tenancy.py`). Kein neues DB-Objekt je Lookup. | Die GUC ist weiter eine Session-Einstellung, die die App selbst setzt. Ein Fehler beim Setzen öffnet den Zweck. Die Policies werden komplexer. |
| **B — `SECURITY DEFINER`-Funktionen für die Lookups** | Für genau die Lookups vor der Auflösung (Token-Hash, Einladungs-Hash, Code-Hash, Webhook-Upsert) gibt es je eine Funktion, die nur die benötigte Zeile liefert. Die Policies werden danach ohne Ausnahme strikt. | Engste Fläche, und die Policies bleiben einfach. Dasselbe Muster wie in Owner-Entscheidung 1 (E-Mail-Funktion). | Je Lookup ein DB-Objekt mit eigener Rechtepflege. `SECURITY DEFINER` braucht sorgfältiges `search_path`-Härten. Der Owner der Funktionen muss sie pflegen. |
| **C — beibehalten und absichern** | Die Policies bleiben, wie sie sind. Die Absicherung übernehmen API-Isolationstests und Review. | Kein Umbau. | R1 bleibt dauerhaft bestehen und muss ausgewiesen bleiben. |

Wer die Weiche angeht, prüft dabei auch einen Owner, der kein Superuser ist
(R2). Die Entscheidung fällt der Owner. Sie kommt als Nachtrag in diese ADR
oder in eine eigene.

## 7. Nachweisweg

Die OH verlangt einen „Nachweis einer ausreichenden Trennung“, C5 die Prüfung
des Konzepts. Diese Tests belegen die Trennung (alle laufen in CI, die
Integrationstests mit echter Datenbank):

| Was | Test | Belegt |
|---|---|---|
| Jede Tabelle mit `workspace_id`/`org_id` hat RLS und eine Policy | `apps/api/tests/test_rls_isolation.py#test_every_scoped_table_has_rls_policy` | Eine neue Tabelle ohne Policy macht den Test rot. Ausnahmen müssen ausdrücklich eingetragen werden. Das ist die Fehlerklasse, gegen die eine DB-Grenze wirken würde (Abschnitt 3.2). |
| Als `who2be_app` sind fremde Zeilen unsichtbar und Inserts in fremde Mandanten werden abgewiesen | `apps/api/tests/test_rls_isolation.py#test_rls_blocks_cross_workspace_reads_for_app_role` | Strikte und permissive Policies verhalten sich wie dokumentiert (Abschnitt 4.3). |
| Seeds laufen unter erzwungenem RLS | `apps/api/tests/test_rls_isolation.py#test_ensure_personal_workspace_seeds_under_enforced_rls`, `apps/api/tests/test_rls_isolation.py#test_workspace_create_seeds_under_enforced_rls` | Auch Bootstrap-Pfade halten die Grenze ein. |
| Der Laufzeit-Pool darf RLS nicht umgehen | `apps/api/tests/test_db_rls_guard.py#test_rls_guard_rejects_bypass_role_in_cloud` | Boot-Guard aus Abschnitt 4.4. |
| Der Statusverlauf und das Audit-Log sind für die App-Rolle append-only | `apps/api/tests/test_audit_append_only.py#test_append_only_for_app_role_and_owner_full_access` | Protokolldaten kann die App-Rolle nicht nachträglich ändern. |
| Der Konto-Purge anonymisiert die Audit-Referenzen | `apps/api/tests/test_purge_erasure.py#test_purge_anonymises_audit_and_keeps_entitlement_history` | Löschpfad je Nutzer. |

Geplant und Teil der Owner-Entscheidung:

- **API- und MCP-Isolationstests je Endpunkt** (Karte t_40307837): Die Routen
  werden aus dem Router-Baum aufgezählt und als Mandant A mit Objekt-IDs von
  Mandant B aufgerufen, erwartet ist 403 bzw. 404. Neue Routen werden
  automatisch erfasst. Läuft null Prüfungen, gilt das als Fehlschlag. Damit wird
  die manuelle Stichprobe vom 2026-09-30 zum CI-Gate.
- **Isolations- und Purge-Test für die gehärteten Steuer-Tabellen** (Karte
  t_8ed14f76, R3/R4).

C5 OPS-24 verlangt außerdem eine Risikoanalyse „gemäß OIS-07“. Diese ADR
liefert das Konzept und die ausgewiesenen Restrisiken. Eine formale
OIS-07-Risikoanalyse ist sie nicht (Abschnitt 8).

## 8. Offene Punkte

- **Rolle je Kunde:** Ob Who2Be im Cloud-Betrieb für alle Kunden
  Auftragsverarbeiter ist (B2B) oder für Personal-Orgs auch Verantwortlicher,
  ist rechtlich zu klären (Bericht, Offene Punkte). Davon hängt ab, wer die
  Restrisiken übernimmt. Die OH verlangt: „Die Übernahme der Restrisiken muss
  schriftlich durch den Leiter der dem Mandanten zugeordneten Daten
  verarbeitenden Stelle erfolgen.“
- **Risikoanalyse:** Eine formale Risikoanalyse nach C5 OIS-07 fehlt. Sie ist
  nur nötig, wenn ein C5-Testat angestrebt wird.
- **EDPB:** Eine Leitlinie mit einer Vorgabe zur Datenbank-Trennung hat die
  Recherche nicht gefunden. Vollständig durchsucht ist die EDPB nicht.
- **Prod-Image:** Die RLS-Attribute und der Owner wurden lokal gemessen. Auf dem
  Server sollte die Messung vor dem ersten Kunden einmal lesend wiederholt
  werden.

## 9. Ausblick

Eine **eigene Instanz für Firmenkunden** (Option c: Compose-Stack je Kunde auf
eigenem Server) bleibt ein möglicher späterer Weg. Der Owner hat ihn am
2026-09-30 nicht gewählt. Diese ADR legt ihn weder fest noch bereitet sie ihn
vor. Sie hält nur fest, dass Entscheidung b ihn nicht verbaut: Jede
Inhaltszeile trägt `workspace_id`, und mit dem Export/Import je Org wäre der
Umzug einer Organisation ein Export mit anschließendem Import (Bericht §5,
Rückweg).

## 10. Konsequenzen

- Die gemeinsame Datenbank mit RLS (ADR-0019) bleibt das Trennmodell. Diese ADR
  ist dessen dokumentiertes Trennungskonzept und muss mitgezogen werden, wenn
  sich eine Policy, eine Rolle oder ein Speicherort ändert.
- Folgepakete aus der Owner-Entscheidung, jedes in einem eigenen PR:
  1. E-Mail-Zugriff über die Funktion (Entscheidung 1), in zwei Paketen.
  2. Härtung der Steuer-Tabellen und Purge des Statusverlaufs (R3, R4).
  3. API- und MCP-Isolationstests je Endpunkt (Abschnitt 7).
  4. Export und Import je Organisation (Abschnitt 4.6, R6).
- Die Weiche aus Abschnitt 6 liegt beim Owner. Bis sie entschieden ist, bleibt
  R1 ausgewiesen.
- Ist ein Restrisiko behoben, wird es in Abschnitt 5 als geschlossen markiert
  und mit dem PR verlinkt, nicht gelöscht. Eine geschlossene Lücke darf
  öffentlich mit ihrer Fundstelle stehen (CONTRIBUTING).
