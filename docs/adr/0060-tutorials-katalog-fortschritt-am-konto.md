# ADR-0060 — Tutorials und Onboarding-Zustand: Katalog-Daten, Fortschritt am Konto

- Status: **Accepted** (Umsetzung Onboarding P1, Kanban-Karte t_cdf85bb8).
- Datum: 2026-10-21
- Grundlage: Onboarding-Design 2026-10 (P1), Karten t_3fbfc8ce und t_59b71492.

## 1. Kontext

Neue Konten brauchen einen gefuehrten Einstieg: Builder bereit, Claude
verbinden, eigenen Agenten bauen, Rueckmeldungen kennenlernen. Das Web
braucht dafuer einen Fortschritt, der Geraete und Workspaces ueberdauert und
den der Nutzer neu starten kann.

Owner-Entscheidung vom 2026-10-20, woertlich:

> „O1 B, Rest wie empfohlen, Test a, Zusätzlich soll der User jederzeit das
> Tutorial erneut starten können, im Tutorial-Bereich sollen späterer mehre
> Tutorials zur Verfügung stehen und hinzugefügt werden können.“

Fuer diese ADR heisst das:

- **O1 B:** zwei Stufen, erst eine Begruessung, dann eine Startliste.
- **O2 a:** Die Begruessung erscheint automatisch einmal pro Konto.
  Eingeladene sehen nur die Startliste.
- **O7 a:** Der Zustand liegt in der Who2Be-DB am Konto.
- **Zusatz „jederzeit erneut starten“:** Neustart je Tutorial (§2.4). Die
  Begruessung laesst sich erneut abspielen.
- **Zusatz „mehrere Tutorials, hinzufuegbar“:** Tutorials sind Daten. Der
  Onboarding-Ablauf ist das erste Tutorial, `getting-started` („Erste
  Schritte“).
- **Test a:** Den Install-Link-Durchlauf (P0) macht der Owner selbst. Diese
  ADR betrifft er nicht.

## 2. Entscheidung

1. **Tutorials sind Daten, kein Code (Weiche W60-1, Variante A).** Ein
   Tutorial besteht aus **drei Dateien**:
   - eine sprachneutrale Definition
     `packages/models/src/who2be_models/tutorials/<id>.json` mit `id`,
     Zielgruppe (`audience`), Begruessung ja/nein (`welcome`) und den
     Schritten (`id` = step_id, `type` aus §3, bei `page_visited` dazu
     `page`). Validiert wird sie durch
     `who2be_models.tutorial.TutorialDefinition`.
   - je Sprache eine Markdown-Datei im Hilfe-Bereich des Web (DE und EN).
     Sie traegt nur Titel und Texte und im Frontmatter `tutorial: <id>`.

   Die API validiert Tutorial- und Schritt-IDs gegen die JSON-Datei. Das Web
   haelt keine zweite Schrittliste: es bekommt die Schritte ueber die API
   (§5). Ob die
   step_ids im Markdown zur JSON-Datei passen, prueft ein Paritaetstest im
   Hilfe-Geruest (Onboarding P4). Ein neues Tutorial heisst damit: drei
   Dateien, kein Code und keine Migration, solange es nur Schritt-Typen aus
   §3 nutzt. Der Katalog ist fuer alle Konten gleich.
2. **Fortschritt haengt am Konto, nicht an einem Mandanten.** Migration
   `0108_tutorial_progress.sql` legt zwei Tabellen an, beide ohne
   `workspace_id`:
   - `tutorial_state` mit Begruessung gesehen und Neustart-Zeitpunkt
   - `tutorial_progress` nur mit den manuellen Zustaenden `done` und
     `skipped` je (Nutzer, tutorial_id, step_id)

   Jede Query filtert auf die authentifizierte `user_id`. Schreiben fuer ein
   fremdes Konto ist nicht ausdrueckbar. tutorial_id und step_id haben die
   Slug-Form `^[a-z0-9]+(?:-[a-z0-9]+)*$` mit hoechstens 64 Zeichen. Die
   Regel steht als CHECK in der Migration und als Pattern im Modell.
3. **Automatische Schritte werden abgeleitet, nicht gespeichert** (§3). Dafuer
   gibt der Client `?workspace_id=` an. Die API prueft ihn gegen die
   Mitgliedschaft, fremd und unbekannt enden gleich mit 404
   `workspace_not_found`. Ohne Workspace bleiben automatische Schritte offen.
4. **Neustart je Tutorial.** `POST /v1/me/tutorials/{id}/restart` loescht
   nur die Zeilen dieses Tutorials und setzt `restarted_at`. Ereignisse davor
   zaehlen nicht mehr. Der Aufruf ist idempotent. `welcome_seen_at` bleibt
   erhalten, die Begruessung erscheint also automatisch nur einmal pro Konto
   und laesst sich im Web von Hand erneut abspielen.
5. **Routen nur fuer Menschen.** `GET /v1/me/tutorials`,
   `GET|PATCH /v1/me/tutorials/{id}` und `POST …/restart` haengen an
   `get_current_user`. Maschinen-Tokens enden mit 403
   `account_route_requires_human`. Unbekannte Tutorial- und Schritt-IDs
   enden mit 422, `loc` zeigt auf das Feld.

## 3. Schritt-Typ-Katalog und Zustandsregeln

Fester Katalog, im Code `who2be_models.tutorial.StepType`:

| Typ | Art | Erledigt, wenn … |
|---|---|---|
| `head_start` | automatisch | immer (Startvorsprung, z. B. „Builder ist bereit“) |
| `first_mcp_call` | automatisch, abgeleitet | eine serverseitig gezaehlte Auslieferung (`usage_event`, `source='server'`) mit `actor_id` = Nutzer im gewaehlten Workspace existiert |
| `agent_created` | automatisch, abgeleitet | ein nicht verwalteter Agent (`agent.is_managed = false`) mit `owner_id` = Nutzer im gewaehlten Workspace existiert |
| `own_agent_mcp_call` | automatisch, abgeleitet | wie `first_mcp_call`, aber ueber einen nicht verwalteten Agenten |
| `page_visited` | manuell gemeldet | das Web meldet den Besuch der Seite `page` (PATCH `done`) |
| `manual` | manuell | der Nutzer hakt den Schritt selbst ab |

Die Ableitung steckt in `PgTutorialRepository.derived`. Sie laeuft unter
`tenant_scope` des geprueften Workspace, weil `usage_event` und `agent` unter
RLS stehen. Es zaehlen nur Ereignisse ab `restarted_at`.

Zustandsregeln, an einer Stelle in `build_tutorial_read`:

- `head_start` ist immer `done`.
- Ein abgeleitetes Ereignis macht den Schritt `done` und schlaegt ein
  frueheres Ueberspringen.
- Automatische Schritte lassen sich ueberspringen oder wieder oeffnen, aber
  nicht von Hand abhaken (422).
- `page_visited` und `manual` uebernehmen den gespeicherten Zustand. `open`
  loescht die Zeile.
- Ein Tutorial ist `completed`, wenn kein Schritt mehr `open` ist.

Ein neuer Schritt-Typ mit automatischer Erkennung ist ein eigenes kleines
Code-Paket: Ableitung, Test und Nachtrag in dieser Tabelle.

## 4. Datenschutz

- **Datenumfang:** nur Zeitpunkte und Zustaende je (Nutzer, tutorial_id,
  step_id). Es gibt keine Inhalte, keine IP und kein Klickprotokoll.
  Abgeleitete Schritte werden nicht gespeichert, sondern bei jedem Abruf aus
  den vorhandenen Workspace-Daten gelesen.
- **Loeschung:** Der Konto-Purge (`PgAccountPurgeRepository.purge_account_data`)
  loescht beide Tabellen ausdruecklich, weil es keine Nutzer-Tabelle mit
  CASCADE gibt. Ein Test belegt das. Der Neustart loescht die manuellen
  Zeilen des Tutorials sofort.
- **Auskunft und Uebertragbarkeit:** Der DSGVO-Export (Art. 15/20) traegt
  einen Block `tutorials` mit `states` und `progress`.
- **Mandantentrennung:** Die Tabellen sind kontoweit und gehoeren keiner Org.
  Der Org-Transfer fuehrt sie deshalb in `GLOBAL_TABLES` (`_classify` ist
  fail-closed). Fremde Workspaces liefern keine Ableitung (404).

## 5. Folgen

- Neue Tutorials brauchen weder Code noch Migration, nur die drei Dateien aus
  §2.1. Neue Schritt-Typen brauchen Code und einen Nachtrag in §3.
- Das Web liest den Katalog **nicht** aus `packages/models` (Praezisierung
  P4, PM 2026-10-21): die Schritt-Definitionen liefert `GET /v1/me/tutorials`,
  das Web traegt nur den Markdown-Text, und der Paritaetstest JSON↔Markdown
  laeuft in Python (`packages/models/tests/test_tutorial_help_parity.py`) —
  das Web-Image bleibt unveraendert.
- Die Signale werden je Tutorial einzeln abgefragt. Bei wenigen Tutorials ist
  das unkritisch, waechst der Katalog, laesst es sich buendeln.
