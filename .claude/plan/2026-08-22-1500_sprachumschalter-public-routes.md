# Plan — Sprache auf den öffentlichen Seiten wählbar machen

_Erstellt: 2026-08-22 15:00 · Branch: `claude/amazing-bardeen-u3gwoj` (neu ab `main`)_

## Ausgangslage (User-Report)

Der OAuth-Consent beim Verbinden des MCP-Connectors erschien auf Deutsch; die
Frage war, ob es eine englische Fassung gibt.

## Befund

**Die englische Fassung existiert und ist vollständig.** Alle 14 Keys unter
`auth.connector.*` sind in `apps/web/src/i18n/locales/en.json` übersetzt,
inklusive der in PR #406 neu dazugekommenen `lockedLabel` / `lockedHint`.

Das Problem ist die **Erreichbarkeit**, nicht die Übersetzung:

1. `LanguageSwitcher` ist ausschließlich in `AppShell` eingehängt
   (`components/layout/AppShell.tsx:107`).
2. Sämtliche öffentlichen Routen liegen **außerhalb** von `AppLayout`
   (`app/routes.tsx:287-305`): `/login`, `/signup`, `/reset-password`,
   `/auth/callback`, `/invitations/:token/accept`, `/oauth/consent`, `/legal/*`.
3. Folge: Auf genau den Seiten, die ein Nutzer **vor** dem Login sieht, gibt es
   keine Möglichkeit, die Sprache zu wechseln. `LoginPage.tsx` und
   `OAuthConsentPage.tsx` enthalten null Vorkommen von `LanguageSwitcher`.
4. Die Sprache bestimmt dort allein der Detektor
   (`localStorage → navigator → htmlTag`, `i18n/index.ts`). Ein deutscher
   Browser bekommt Deutsch — korrekt, aber unkorrigierbar.

**Zweiter Fund (unabhängig, A11y):** `apps/web/index.html:2` setzt statisch
`<html lang="de">`. Das Attribut wird nie an die aktive Sprache angeglichen —
auch eine englische UI deklariert sich als deutsches Dokument. Screenreader
wählen daraus die Aussprache, Browser ihr Übersetzungsangebot; zudem ist
`htmlTag` die letzte Stufe der Detektor-Kette und zeigt damit dauerhaft auf `de`.

## Design-Weiche — wo lebt der Umschalter auf öffentlichen Seiten?

### Option A — `PublicLayout` als Route-Element (Empfehlung)

Analog zum bestehenden `AppLayout`: ein Wrapper um die öffentlichen Routen, der
oben rechts eine kleine Steuerungs-Insel rendert (Sprache; Theme-Toggle
optional). Die Seiten selbst bleiben unverändert — sie zentrieren ihre Karte
weiterhin selbst über `min-h-screen`, der Wrapper legt sich nur darüber.

- Pro: eine Stelle für alle öffentlichen Seiten, künftige Public-Routes erben es
  automatisch; folgt dem etablierten Layout-Muster des Repos; `/legal/*` behält
  sein `LegalLayout` und wird zusätzlich umschlossen.
- Contra: berührt die Router-Struktur; der Wrapper muss die vorhandene
  Zentrierung der Karten unangetastet lassen (positionierte Insel, kein
  Flex-Container drumherum).

### Option B — Shared-Komponente je Seite einhängen

`PublicPageControls` bauen und in jede öffentliche Page einzeln importieren.

- Pro: kein Eingriff in den Router; jede Seite entscheidet selbst.
- Contra: sechs Einhäng-Punkte statt einem, und die nächste öffentliche Seite
  vergisst es garantiert — genau der Drift, den die Frontend-Standards
  („Single-Source pro Entscheidung") vermeiden wollen.

### Option C — nur auf der Consent-Seite

- Pro: minimal, löst exakt den berichteten Fall.
- Contra: Login und Invitation-Onboarding bleiben unumschaltbar — ein
  englischsprachiger Eingeladener landet weiter auf einer deutschen Seite.

**Empfehlung: A.** B und C lassen dieselbe Lücke an anderer Stelle stehen.

## Arbeitspakete

### WP1 — `PublicLayout` + Sprachumschalter
`app/PublicLayout.tsx` (neu), `app/routes.tsx` (öffentliche Routen umschließen).
Vor der UI-Arbeit `docs/frontend/design-language.md` lesen; Primitives aus
`@/components/ui/*`, keine rohen Elemente, keine `px`/`#hex` im JSX.
Tests: Umschalter auf `/login` und `/oauth/consent` sichtbar, Sprachwechsel
schlägt auf die gerenderten Strings durch, Karten-Zentrierung unverändert.

### WP2 — `<html lang>` an die aktive Sprache binden
`index.html` (Startwert) + ein `languageChanged`-Listener (i18n-Setup oder
`useApplyStoredLocale`-Nachbarschaft). Test: nach `setLocale('en')` trägt
`document.documentElement.lang` den Wert `en`.

### WP3 — Doku
`docs/frontend/i18n.md` (öffentliche Seiten + `lang`-Sync), CHANGELOG
(Unreleased), STATE.md.

## DoD
- Web: `npm run lint` (0 Errors), `npx tsc -b`, `npm run test:coverage`,
  `npm run build` — alle grün, lokal vor dem Push.
- Draft-PR; Issue nach Schwelle (≥2 Arbeitspakete + sichtbarer UI-Fluss).

## Anti-Scope
- Keine neuen Sprachen, keine Änderung an vorhandenen Übersetzungen.
- Keine Änderung an der Vorrang-Regel für `user_metadata.preferred_locale`
  (`shouldApplyStoredLocale`) — die ist frisch und bewusst so gebaut.
- Kein Umbau der Detektor-Kette.
