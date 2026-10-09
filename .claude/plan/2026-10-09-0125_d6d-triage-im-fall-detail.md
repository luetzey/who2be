# D6d – Triage im Fall-Detail und Prüffall aus Fall (Karte t_5ba15d0d)

Basis: origin/main 7590c335 (D6c, D6-API2 und D6c′ gemergt). Spec: Delta Phase D
§0, S8 (Tabelle „Nächster Schritt in D“, Zuordnen, Umgesetzt, Wieder öffnen,
Prüffall, Verknüpft, Zustände, 390 px), Barrierefreiheit, Zuschnitt D6d.

## Dateien (Budget 7, höchstens 8)
1. apps/web/src/components/cases/CaseActions.tsx (neu: Leiste, Status-Menü, Dialoge)
2. apps/web/src/components/cases/CaseActions.test.tsx (neu)
3. apps/web/src/features/feedback/pages/CaseDetailPage.tsx
4. apps/web/src/components/testcases/TestCaseForm.tsx (Prop `prefill`)
5. apps/web/src/i18n/locales/de.json
6. apps/web/src/i18n/locales/en.json
7. changelog.d/t-5ba15d0d-case-triage.added.md

## Schritte
1. `planNextStep(status, elements, hasTestCase)`: genau eine Hauptaktion je
   Zeile der S8-Tabelle, Rest ins Status-Menü. Keine Aktion für
   `in_progress`/`verified` (D2a). Ohne versionierte Zuordnung kein
   „Als umgesetzt markieren…“, sondern ein nicht klickbarer Hinweis im Menü.
2. Dialoge (ab `md` Dialog, darunter Bottom-Sheet mit fester Knopfleiste):
   Zuordnen (fieldset/legend je Gruppe, Werkzeugrechte, Gedächtnis,
   Modellgrenze als eigenes fieldset; Checkbox „Danach als eingeordnet
   markieren“ bei open/reopened, zwei Aufrufe), Umgesetzt (Baustein, dann
   Version neueste zuerst mit „aktiv“, Notiz optional), Verwerfen und Wieder
   öffnen (Begründung ≥ 10 Zeichen). „Als eingeordnet markieren“ ohne Dialog.
3. `case_transition_forbidden` → Toast mit Spec-Text, Seite lädt neu.
4. Prüffall: vorhandenes `TestCaseForm` mit neuer Prop `prefill`
   (Eingabe = Lage, Erwartung = Erwartet, `origin_case_id`), Agent fest,
   Bezug = erstes zugeordnetes versioniertes Element.
5. „Verknüpft“ (nur editor): Prüffälle über `GET /test-cases?origin_case_id=`,
   Quelle Lernvorschlag → `/memory?entry=`, Alt-Feedback → `/feedback/item/:id`,
   `source_ref` nur bei http(s) als Link (`rel="noopener noreferrer"`).
6. Fokus nach Übergang auf das Status-Wort (`tabIndex={-1}`, `aria-live`).
7. Review-Nit N2 aus D6c: Löschfehler zeigt `cases.delete.error`.
8. Checks: tsc -b, vitest, lint, i18n, build; Fotos 1280/390 hell/dunkel je
   Zustand und Dialog plus measure.json.

## Entscheidungen mit Beleg
- **Kein „Wieder öffnen…“ bei `dismissed`.** Die S8-Tabelle nennt es, der
  Server kennt die Kante aber nicht: `case_service.py` `_EDGES[dismissed]` ist
  leer, ADR-0053 3.3 führt `reopened` nur aus `addressed`. Der Knopf würde
  immer mit `case_transition_forbidden` enden. Rückmeldung an PM im Handoff.
- **Modellgrenze zugeordnet → Hauptaktion „Verwerfen…“** (Spec S8 „Zuordnen“)
  mit vorbelegter Begründung. Die übrigen Aktionen der Tabellenzeile wandern
  ins Menü.
- **`triaged` mit Prüffall, aber ohne versionierte Zuordnung:** Hauptaktion
  „Zuordnung ändern…“, denn erst eine versionierte Zuordnung ermöglicht
  „Umgesetzt“. So bleibt es bei genau einer Hauptaktion.
- Neue Texte über die Spec hinaus (Spec nennt keinen Wortlaut):
  `cases.address.note`, `cases.address.choose`, `cases.dismiss.submit`,
  `cases.reopen.submit`, `cases.reason.tooShort`.

## Stand
- [ ] 1–8
