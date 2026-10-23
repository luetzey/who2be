# Plan: UI-Texte DE — „Agenten“, ein Wortschatz für Versionen, interne Begriffe raus

Kanban-Karte t_c54bcfaf (UX-Audit K3, K7, B5, B6, B7-Wortwahl). Basis: origin/main 3a1ee878.

## Ziel (fertig heißt)

Die deutsche Web-UI und die DE-Hilfe benutzen einen Wortschatz:
„Agenten“/„Agent“ (auch Nav, Titel, Knöpfe), „Aktivieren“ als einzige
Freigabe-Aktion, „Deaktivieren“ statt „Zurückziehen“, „Entwurf“ statt „Draft“,
„System-Prompt“ statt „Systemprompt“/„Template“, „Platzhalter“ statt
„Placeholder“. EN bleibt unverändert.

## Entscheidungen (Owner/Karte, nicht neu entschieden)

- W-A Owner 2026-10-22: DE überall „Agenten“, EN bleibt „Agents“.
- Banner: „Aktiv: v3 · Entwurf v4 in Arbeit“ bzw. „Aktiv: v3 · v4 wartet auf
  Freigabe durch einen Admin“.
- API-Fehlertexte in apps/api bleiben ohne Umlaute (nicht angefasst). Die
  deutschen Web-Texte zu `common.errors.*` in de.json sind UI-Texte und folgen
  dem Wortschatz.

## Vom Coder entschieden (mit Beleg)

- „Einreichen“: Personas/Playbooks hießen „Entwurf abschließen“, Resources,
  Werkzeuge und System-Prompts „Zur Freigabe einreichen“ (common.statusBar.submit,
  systemPrompts.statusBar.submitForReview), der Toast überall „Zur Freigabe
  eingereicht.“ → überall „Zur Freigabe einreichen“. Ein Wortschatz je Aktion.
- „Zurück zu Draft“ → „Zurück in den Entwurf“ (gleich dem vorhandenen Toast
  systemPrompts.statusBar.toast.backToDraft). „Reaktivieren als Draft“ →
  „Als Entwurf reaktivieren“.
- Werkzeug-Satz (B5): OAuth-Tokens sind immer an den Agenten gebunden
  (apps/api/src/who2be_api/services/oauth_service.py:438), die Tool-Policy
  gilt also für beide Wege → „Gilt für jedes verbundene Programm, ob über die
  Anmeldung (OAuth) oder einen API-Token.“
- Unter-Tab Einstellungen › „Verbindung“ → „API-Tokens“ (B6), nur DE-Text.
- Muster: keine Muster-Entscheidung nötig (reine Texte, keine Logik).

## Umfang

1. apps/web/src/i18n/locales/de.json — nur Werte, keine Schlüssel.
2. DE-Hilfe, nur Wortersatz: erste-schritte/{connect-claude,own-agent,
   who2be-in-2-minutes}.de.md, tutorials/getting-started.de.md, bausteine/
   {persona,playbooks,resources,system-prompts}.de.md (Abschnitt Versionen
   gleich formuliert, B7 nur Wörter).
3. Tests, die die alten DE-Texte als Matcher nutzen: nur Erwartungstext.
4. Changelog-Fragment.

Billing (PM-Kommentar): `billing/i18n.ts` hat auf main schon „Gültig bis“,
keine sichtbaren Ersatzumlaute im DE-Block → keine Änderung, im PR belegt.

## Out of Scope

„Wirkt bei: …“-Zeile, Platzhalter {{ui:…}} (t_b792c7b3), Routen/URLs, EN-Texte,
Tab „Kuration“ (B11), Feedback-„Triage“-Labels außerhalb der B5-Liste.

## Verifikation (CONTRIBUTING §Definition of Done, Web)

```
cd apps/web
npm run lint && npx tsc -b && npm run i18n:check
npx vitest run src/i18n/umlauts.test.ts
npm run test:coverage
npm run build && npm run license:check
grep -n "Agents" src/i18n/locales/de.json   # nur Schlüssel
```

Fotos 1280/390 hell/dunkel: Nav (Agenten-Liste), Persona-Seite mit Banner.

## Kollision

PR #1060 (offen, freigegeben) ändert de.json, connect-claude.de.md und
TutorialChecklist.test.tsx. Wer später merged, merged main nach.
