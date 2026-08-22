# i18n-Bestandsaufnahme Web-UI — was ist DE/EN, was nicht

Datum: 2026-08-22 · Status: Analyse (read-only, keine Code-Aenderung)
Anlass: „Uebersicht welche Elemente Uebersetzung DE/EN haben; die Uebersetzung
auf dem Frontend funktioniert nicht."

## 0. Kernbefund vorweg

Der i18n-Unterbau **funktioniert** — nachgewiesen, nicht vermutet. Probe-Test
(`react-i18next` + `changeLanguage`) rendert `common:actions.save` als
„Speichern" (de) und „Save" (en), inkl. Re-Render der Komponente. Der Fehler
liegt nicht in der Mechanik, sondern in **untersetzten Inseln** und einer
**Persistenz-Luecke**.

## 1. Schluessel-Ebene: vollstaendig

| Metrik | Wert |
|---|---|
| Namespaces (`de.json`/`en.json`) | 17 (+ `billing` zur Laufzeit registriert) |
| Keys DE | 1744 |
| Keys EN | 1744 |
| Keys nur in DE (EN fehlt) | **0** |
| Keys nur in EN | **0** |
| Werte DE == EN (bewusst identisch, z. B. Eigennamen) | 129 |
| `t()`-Aufrufe mit Literal-Key im Code | ~1590, alle aufloesbar |

`SUPPORTED_LOCALES = ['de','en']`, Default + Fallback `de`. Detector-Reihenfolge
`localStorage → navigator → htmlTag`, Cache-Key `who2be.locale`.
`features/billing/i18n.ts` registriert seinen Namespace separat (Build-Isolation
ADR-0029) — **mit** DE- und EN-Block.

## 2. Seiten-Ebene: 44 von 44 Seiten sind angebunden

Alle Route-Pages nutzen `useTranslation`. Rest-Hardcode nur in 4 Seiten:

| Seite | harte DE-Strings |
|---|---|
| `features/dashboard/pages/DashboardPage.tsx` | 8 (Buttons „Neues Playbook / Neue Persona / Neuer Agent", Gedaechtnis-Banner) |
| `features/settings/pages/AccountPage.tsx` | 4 (zod-Validierungstexte) |
| `features/system-prompts/pages/SystemPromptDetailPage.tsx` | 2 |
| `features/auth/pages/LoginPage.tsx` | 2 (MFA-Fehlertexte) |
| `features/agents/pages/AgentsPage.tsx` | 1 (`createAgent({name:'Neuer Agent'})` — Inhalt, kein UI-String) |

Voll uebersetzt (0 Hardcode): personas, playbooks, resources, tools, workarea/KB,
feedback, legal, settings (ausser oben), auth (ausser oben), agents.

## 3. Die untersetzten Inseln (das, was sichtbar deutsch bleibt)

| Bereich | Dateien | davon mit `t()` | harte DE-Strings |
|---|---|---|---|
| `components/editor/system-prompt/**` | 21 | **0** | 47 |
| `app/catalog/**` (DEV-only Showcase) | 22 | 0 | 28 |
| Hooks/Toasts/Fehler-Fallbacks (`hooks/`, `features/*/hooks/`, `lib/`) | ~20 | 0 | ~25 |
| `components/ui/dialog.tsx` | 1 | 0 | 1 (`sr-only` „Schliessen") |

**Der System-Prompt-Editor ist die groesste Luecke:** Slash-Menu, alle Picker
(Persona-Feld, Playbook, Resource, Tool, Datum, Katalog-Scope),
Placeholder-Popover und der Editor-Rahmen sind komplett hartkodiert deutsch.
`app/catalog` ist DEV-only und darum unkritisch.

## 4. Backend: gar keine Uebersetzung

- `apps/api` hat **keine** i18n-Schicht. `Accept-Language` wird vom Web-Client
  (`api/client.ts`) gesendet, aber serverseitig nirgends gelesen.
- **78 `detail="…"`-Strings sind fest deutsch** („Agent nicht gefunden.",
  „Datenbank nicht verfuegbar." …).
- Der Client zeigt diese Strings **woertlich** an: `client.ts` nimmt
  `body.detail` als Fehlermeldung, die Hooks reichen sie als `cause.message`
  in `ErrorAlert`/Toast durch.
- Ergebnis: **jede** Server-Fehlermeldung bleibt deutsch, egal welche UI-Sprache.

Dazu ~16 hartkodierte zod-Validierungstexte („Name erforderlich.",
„Bitte gueltige E-Mail eingeben.") in 11 Form-Hooks.

## 5. Verdachtsmoment „Sprache springt zurueck"

`useApplyStoredLocale` (montiert in `AppLayout`) setzt die Sprache aus
`session.user.user_metadata.preferred_locale`. `useLocale().setLocale` schreibt
diesen Wert per `supabase.auth.updateUser`.

In `@supabase/auth-js` setzt `updateUser` nur `session.user = data.user` und
**behaelt den bestehenden `access_token`**. `SessionProvider.apply()` dedupliziert
aber genau darauf:

```ts
if (lastTokenRef.current === nextToken) { return }   // SessionProvider.tsx
```

Das `USER_UPDATED`-Event wird also verworfen — der React-`session`-State behaelt
die **alte** `preferred_locale`. Solange nichts anderes den Effekt neu ausloest,
faellt nichts auf; sobald `stored` aber einmal auf dem alten Wert wieder
angewendet wird (Reload mit noch nicht rotiertem Token, zweites Geraet,
fehlgeschlagener `updateUser`), **ueberschreibt der gespeicherte Wert die frische
Wahl** und die UI springt auf Deutsch zurueck.

Belegt ist: der Dedupe-Pfad greift (Quellcode-Nachweis oben). Nicht belegt ist,
dass genau das die beobachtete Beschwerde ist — dafuer braucht es das konkrete
Symptom vom Nutzer.

## 6. Zahlen gesamt

- 336 Quelldateien (ohne Tests), davon **136 mit `t()`**
- **66 Dateien mit hartem deutschem Text**, zusammen **145 Strings**
  (davon 28 im DEV-Katalog → 117 produktiv relevant)
- plus 78 deutsche Server-`detail`-Strings

## 7. Vorgeschlagene Arbeitspakete (noch nicht umgesetzt)

- **WP-1 System-Prompt-Editor i18n** — neuer Namespace `editor`, 21 Dateien,
  47 Strings. Groesster sichtbarer Gewinn.
- **WP-2 Hooks/Toasts/zod** — geteilte Keys in `common.errors.*` /
  `common.validation.*`, ~40 Strings, 30 Dateien.
- **WP-3 Rest-Seiten** — Dashboard, AccountPage, SystemPromptDetail, Login,
  `dialog.tsx`-`sr-only`. ~17 Strings.
- **WP-4 Sprach-Persistenz haerten** — `SessionProvider`-Dedupe auf
  `USER_UPDATED` durchlassen (Token-Vergleich um `updated_at`/Metadaten
  erweitern) **oder** `useApplyStoredLocale` nur einmal pro Session anwenden
  (Ref-Guard), damit ein gespeicherter Altwert eine frische Wahl nie ueberschreibt.
- **WP-5 API-Fehlertexte** — Entscheidung noetig: Fehler-Codes statt Prosa
  (Client uebersetzt) vs. serverseitiges `Accept-Language`. Architektur-Weiche,
  gehoert in eine ADR.
