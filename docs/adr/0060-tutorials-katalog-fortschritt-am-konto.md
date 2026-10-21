# ADR-0060 — Tutorials als Katalog-Daten, Fortschritt am Konto

- Status: **Accepted** (Umsetzung Onboarding P1, Kanban-Karte t_cdf85bb8).
- Datum: 2026-10-21
- Grundlage: Onboarding-Design 2026-10 (P1), Karten t_3fbfc8ce und t_59b71492.

## 1. Kontext

Neue Konten brauchen einen gefuehrten Einstieg: Builder bereit, Claude
verbinden, eigenen Agenten bauen, Rueckmeldungen kennenlernen. Das Web
braucht dafuer einen Fortschritt, der Geraete und Workspaces ueberdauert und
den der Nutzer neu starten kann.

## 2. Entscheidung

1. **Tutorials sind Daten, kein Code.** Je Tutorial eine sprachneutrale
   JSON-Datei in `packages/models/src/who2be_models/tutorials/<id>.json`,
   validiert durch `who2be_models.tutorial.TutorialDefinition`. Texte liegen
   im Web (i18n). Der Katalog ist fuer alle Konten gleich.
2. **Fortschritt haengt am Konto, nicht an einem Mandanten.** Migration
   `0108_tutorial_progress.sql` legt `tutorial_state` (Begruessung gesehen,
   Neustart-Zeitpunkt) und `tutorial_progress` (nur manuelle Zustaende) an,
   beide ohne `workspace_id`. Jede Query filtert auf die authentifizierte
   `user_id`; Schreiben fuer ein fremdes Konto ist nicht ausdrueckbar.
3. **Automatische Schritte werden abgeleitet, nicht gespeichert.**
   `first_mcp_call`, `agent_created` und `own_agent_mcp_call` liest
   `PgTutorialRepository.derived` aus `usage_event` (Quelle `server`, eigener
   `actor_id`) und `agent` (nicht verwaltet) — unter `tenant_scope` des per
   `?workspace_id=` gewaehlten Workspace, der gegen die Mitgliedschaft
   geprueft wird (fremd/unbekannt: 404 `workspace_not_found`). Ein erkanntes
   Ereignis schlaegt ein frueheres Ueberspringen. Abhaken laesst sich ein
   automatischer Schritt nicht (422).
4. **Neustart je Tutorial.** `POST /v1/me/tutorials/{id}/restart` loescht
   nur die Zeilen dieses Tutorials und setzt `restarted_at`; Ereignisse davor
   zaehlen nicht mehr. `welcome_seen_at` bleibt (Begruessung automatisch nur
   einmal pro Konto).
5. **Routen nur fuer Menschen.** `GET /v1/me/tutorials`,
   `GET|PATCH /v1/me/tutorials/{id}`, `POST …/restart` haengen an
   `get_current_user`; Maschinen-Tokens enden mit 403
   `account_route_requires_human`. Unbekannte Tutorial-/Schritt-IDs: 422.

## 3. Folgen

- Konto-Purge (`PgAccountPurgeRepository.purge_account_data`) loescht beide
  Tabellen; der DSGVO-Export traegt einen Block `tutorials`.
- Org-Transfer fuehrt beide Tabellen in `GLOBAL_TABLES` (kontoweit, nie Teil
  einer Org).
- Neue Tutorials brauchen keine Migration — nur eine Katalog-Datei und die
  Web-Texte. Neue Schritt-Typen brauchen Code (Ableitung) und ein ADR-Update.
