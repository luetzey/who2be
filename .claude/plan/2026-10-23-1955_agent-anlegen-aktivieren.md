# Plan: Eigenen Agenten anlegen + „Agent jetzt aktivieren?“ (UX-Audit B4)

Karte: t_95f43700 · Owner-Entscheidung W-D (2026-10-22): nachfragen, nicht automatisch aktivieren.

## Umsetzung

1. `AgentsPage.createAgent` navigiert nach `?tab=settings` mit Router-State
   `focusPersona` (State statt URL: Reload/geteilter Link fokussiert nicht erneut).
2. `AgentDetailPage`: `useFocusPersonaOnCreate` setzt den Fokus auf „Persona“
   (`form.setFocus`, im nächsten Task, weil `form.reset()` die Feld-Refs neu bindet).
3. `useAgentForm.onSaved` bekommt den gespeicherten Agenten (PUT-Antwort).
4. Dialog nach dem Speichern nur bei `activatable && status === 'disabled' &&
   !is_managed && role ∈ {editor, admin}` (dieselbe Grenze wie der Status-Select).
5. „Aktivieren“ = vorhandener `PUT /agents/{id}` mit nur `{status: 'enabled'}`
   (keine neue Route), danach Überblick `#connect` (Karte „Verbindung“).
   „Später“ schließt nur.
6. Hilfe `own-agent.{de,en}.md` §Selbst anlegen, Changelog-Fragment.

## Verifikation

- Unit: AgentDetailPage (6 neue Fälle), AgentsPage (Ziel-URL + State).
- Rot-Proben M1–M6 (Status-, Rechte-, Vollständigkeits-Bedingung, „Später“
  aktiviert, Fokus entfernt, alte Navigation) → jeweils rot.
- Web-DoD laut CONTRIBUTING.md; Fotos `.shots/t_95f43700/` (nicht committet).

## Out of Scope

Aufräumen verwaister Hüllen, Zeile „Wirkt bei: …“.
