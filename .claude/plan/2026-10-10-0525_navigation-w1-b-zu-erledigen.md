# Navigation W1-b: Seite „Zu erledigen“ (`/w/:ws/inbox`)

Kanban t_668d76d9 · Spec `navigation-transparenz-design-2026-10.md` §2.2, §2.4, §8, §9 ·
Weichen N2a, N3a, N5a, N6a, N7a · baut auf W1-api (#897) und W1-a (#898).

## Ziel (fertig heisst)

Die Glocke fuehrt auf eine Seite, die die offenen Aufgaben nach Art gruppiert
(Reihenfolge §2.2), je Art hoechstens 5 Zeilen plus „Alle n ansehen“, jede Zeile
mit genau einer Aktion als Link auf die Fachseite. Leerzustand „Alles erledigt“.
Filter `?kind=` (Arten-Chips) und `?agent=` ueber `ListFilterBar`, keine Suche.

## Schnitt (8 Dateien + Plan)

- `features/inbox/pages/InboxPage.tsx` (neu) — Filter, Zaehler (EINE
  `useInboxCounts`-Instanz, PM-Hinweis aus Review W1-a), Abschnitte, Leer/Fehler.
- `features/inbox/components/InboxSection.tsx` (neu) — Abschnitt (`section` +
  `h2` mit Zahl im Namen), Zeile, Laden/Fehler je Abschnitt, „Alle n ansehen“.
- `features/inbox/pages/InboxPage.test.tsx`, `InboxPage.a11y.test.tsx` (neu).
- `app/routes.tsx` — Route (lazy).
- `i18n/locales/de.json`, `en.json` — Namespace `inbox`.
- `changelog.d/t-668d76d9-inbox-page.added.md`.

## Arten und Rollen (§2.2)

| Art | Rolle | Zeilen aus | Zeilen-Ziel | Alle-Link |
|---|---|---|---|---|
| Nachkontrollen faellig | editor+ | — (kein Listen-Endpunkt, s. u.) | — | — |
| Gedaechtnis zur Freigabe | alle (viewer: eigenes) | `listMemories(status=pending, limit 5)` | `/memory?tab=approval&entry=<id>` | `/memory?tab=approval[&agent=]` |
| Versionen zur Freigabe | admin (Aufgabe), editor („Zum Anschauen“) | Listen Persona/Playbook/Resource/System-Prompt mit `current_status=review` | Version-Diff | gefilterte Liste je Typ |
| Rueckmeldungen | editor+ | `listCases(status=open,reopened, limit 5)` | `/feedback/cases/<id>` | `/feedback?tab=cases[&agent=]` |
| Muster | editor+, „Zum Anschauen“ | Zahl aus `/inbox/counts` | `/feedback?tab=patterns` | — |

Abschnitte laden unabhaengig und nur, wenn ihre Zahl > 0 ist; sie laden neu,
wenn sich ihre Zahl aendert (Tab-Rueckkehr, eigene Aktion — N5a, kein Polling).

## Auf Zuruf angenommen

- **Nachkontrollen ohne Zeilen:** Es gibt noch keinen Listen-Endpunkt fuer
  faellige Massnahmen (`?due=true` kommt mit Phase E) und noch kein Ziel
  (Tab „Weiterentwicklung“, W2-a/W3). Der Abschnitt zeigt Zahl und Erklaersatz
  plus Hinweis, dass die Einzelansicht mit der Weiterentwicklung folgt.
- **Leerzustand:** Karte verlangt „Alles erledigt“, Spec-Text „Nichts zu
  erledigen“ — Titel „Alles erledigt“, Beschreibung nach Spec.
- **viewer:** keine Filterleiste (nur eine Art, keine Agent-Facette).

## Verifikation

`npm run lint`, `npx tsc -b`, `npx vitest run src/features/inbox src/components/layout`,
`npm run i18n:check`, Gesamt-Suite vor Push, e2e mobile (`--project=mobile-iphone-13`),
Fotos 1280/390 hell/dunkel + measure.json unter `.shots/t_668d76d9/`.
