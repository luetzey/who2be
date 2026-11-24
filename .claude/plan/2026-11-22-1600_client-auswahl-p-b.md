# Client-Auswahl P-B: ChatGPT als Option, Hilfe-Seite connect-chatgpt

Karte t_e1d048c4 · Spec `client-auswahl-design-2026-10.md` (Karte t_eb9ad00c) §2.4 ChatGPT, §2.5, §3, §4, §5.1–5.3, §5.5, §6 P-B.
Voraussetzung: Owner-Test t_e97d5c21 am 2026-11-22 „ok, alles funktioniert“. P-A (#1060) ist auf main.

## Completion-Condition

- Auswahl: 6 Kacheln in der Reihenfolge Claude (Web, App, Handy) · ChatGPT · Claude Code · Cursor oder VS Code · Hermes Agent · Etwas anderes (`CONNECT_CLIENTS`).
- ChatGPT-Zweig: 3 Schritte, kein Install-Link, kein Rückfall-Aufklapper. Kopierfelder Name und Server-URL. „URL kopieren“ ist die einzige `brand`-Aktion und startet das Warten. „ChatGPT öffnen“ ist `outline`, externer Link in neuem Tab mit `sr-only`-Hinweis, und startet ebenfalls das Warten. Englische Menünamen stehen in `<b lang="en">`.
- Hinweise Plan, Business, Werkzeug-Rückfrage. „Klappt es nicht?“ zeigt auf `/help/connect-chatgpt#troubleshooting`.
- Begrüßung: Chips ChatGPT · Claude Code · Cursor oder VS Code · Hermes Agent · Etwas anderes. Der Erfolg nennt ChatGPT beim Namen.
- Hilfe DE/EN: neue Seite `connect-chatgpt` (order 25), Satz in `connect-other-clients#andere` und in `connect-claude`, News ChatGPT. Tutorial unverändert.
- Web-DoD grün, `helpContent.test.ts` und Paritätstest grün, Rot-Proben rot, Fotos 320/390/1280 hell/dunkel, measure ohne Überlauf.

## Entscheidungen

- **Owner-Test-Ergebnis:** Der Test meldet nur „ok“. Zu den Menünamen, zum Namen im @-Menü und zur Werkzeug-Rückfrage gibt es keine Angaben. Darum gelten die Menünamen aus der Spec (englisch). Ziel von „ChatGPT öffnen“ ist `https://chatgpt.com/`, das ist laut Spec §7.3 der sichere Weg, weil `/plugins` nicht als stabiler Pfad belegt ist.
- **Hinweis `chatgptConfirm`:** Seit #1050 tragen die Lesewerkzeuge `readOnlyHint` (`apps/mcp/src/who2be_mcp/tool_annotations.py`). ChatGPT fragt dann nur noch vor Schreibaufrufen nach. Der Text aus der Spec („fragt vor Werkzeug-Aufrufen nach … sonst bleibt der Test stumm“) stimmt deshalb nicht mehr. Neu: „ChatGPT fragt nach, bevor ein Werkzeug etwas ändert. Erlaube den Aufruf, sonst passiert nichts.“ Belegt im Repo, deshalb keine Weiche.
- **Hervorhebung:** kein `<Trans>`, weil das Repo es nirgends nutzt (Entscheidung P-A). `WithCode` wird zu einem allgemeinen Platzhalter-Satz (`[[0]]`, `[[1]]` …). Die Menünamen sind feste Konstanten im Code (`CHATGPT_MENU`), weil ChatGPT sie in beiden Sprachen englisch zeigt. So steht kein HTML im JSON.
- **Dateibudget (Karte: bis 6):** 8 Dateien Code/Tests: `installLinks.ts`, `ConnectGuide.tsx`, `WelcomeDialog.tsx` (Erfolgsname, Spec §3), `de.json` + `en.json` (in Spec §6 ein Punkt), zwei Testdateien und `umlauts.test.ts` (Allowlist „business“). Zählt man das Locale-Paar als eine Stelle wie die Spec, sind es 7. Dazu kommen Hilfe, News, Changelog und Plan. Die Überschreitung ist im PR genannt.

## Schritte

1. `installLinks.ts`: `chatgpt` an Stelle 2, `CONNECT_HELP_PATHS.chatgpt`, `CHATGPT_URL`.
2. `ConnectGuide.tsx`: ChatGPT-Zweig, Platzhalter-Satz.
3. `WelcomeDialog.tsx`: `NAMED_CLIENTS` + chatgpt.
4. i18n DE/EN.
5. Tests Baustein und Dialog, Rot-Proben.
6. Hilfe DE/EN, News, Changelog-Fragment.
7. DoD, Fotos, PR.

## Stand (2026-11-22)

Schritte 1–7 erledigt. Web-DoD grün: lint (0 Fehler), tsc, i18n:check, test:coverage mit 282 Dateien und 2857 Tests (Branches 83,96 %), Skip-Gate 0/0, build, license:check. Python: Paritätstest und Changelog-Tests 43 passed, `changelog_fragments.py check` grün.

Nachgezogen: `umlauts.test.ts` kennt „business“ als englischen Wortteil (Produktname „ChatGPT Business“), sonst hält der Umlaut-Test das „ss“ für ein Ersatz-ß. Damit sind es 8 Dateien Code/Tests.

Rot-Proben (je zurückgesetzt): URL-Kopieren ohne Warten-Start 4 rot, Ziel `/plugins` 2 rot, ohne sr-only 2 rot, „ChatGPT öffnen“ als brand 2 rot, chatgpt nicht in `CONNECT_CLIENTS` 10 rot, Hilfe-Ziel `#andere` 1 rot, Erfolgsname ohne chatgpt 1 rot, Menüname ohne `lang="en"` 1 rot.

Fotos in `.shots/t_e1d048c4/` (nicht committet): Baustein ChatGPT vor und während des Wartens, Begrüßung Schritt 1 und Schritt 2 ChatGPT, Hilfe-Seite, je 1280/390/320 hell und dunkel. 30 Messungen, alle `scrollWidth == clientWidth`, Dialog 598/598, 390/390, 320/320. Kachelhöhen bei 320: Zeile 1 54/54, sonst 44.

## Auf Zuruf angenommen

- Keine.
