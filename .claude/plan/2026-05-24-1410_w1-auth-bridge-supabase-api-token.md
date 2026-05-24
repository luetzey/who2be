# W1 — Auth-Bridge Supabase-Session ↔ API-Token

> Task: [TASK-265](https://www.notion.so/36abe5372ab88162a02df9dc4675412d) ·
> Milestone: MS-1 (Web-UI Minimal-funktional) · Branch: `claude/pensive-euler-UAAsq`.

## Ziel / Completion-Condition

API-Calls aus dem Web tragen ein gueltiges `Authorization: Bearer <token>`, das
die FastAPI-Dependency `get_current_user` akzeptiert. Token-Quelle ist primaer
das Supabase-JWT (`session.access_token`); ein im Speicher gehaltener
`w2b_`-Override hat Vorrang, damit W2 spaeter eine Settings-UI darauf andocken
kann. `JWT_SECRET` ist in `.env.example` als "muss mit Supabase-Project-JWT-
Secret uebereinstimmen" dokumentiert.

**Transkript-Check:** `npm run lint`, `npx tsc --noEmit`, `npm test` (Vitest)
gruen — inkl. eines neuen Tests, der die Override-Praezedenz und den
Session-Fallback belegt.

## Guardrails (aus Projekt-Constraints + Konventionen)

- React-Conventions: TS strict, kein `any`, funktionale Komponenten + Hooks,
  Verhalten testen statt Implementierung.
- **Auth-Token nicht in localStorage** (react-conventions explizit). W2 darf
  das spaeter aendern, wenn noetig — W1 nicht.
- `persistSession: false` in `lib/supabase.ts` bleibt unveraendert.
- Out-of-Scope (kommt in W2): Settings-UI fuer Token-Verwaltung, Persistenz
  des `w2b_`-Override-Tokens ueber Reload, Anzeige/Revoke von Tokens.

## Aktueller Stand (gelesene Dateien)

- `auth/SessionProvider.tsx` haelt `Session | null` im State; `signIn` / `signOut`
  ueber Supabase.
- `auth/session-context.ts` exportiert `useSession()`.
- `api/useApi.ts` ruft heute `createApi(session?.access_token ?? '')` —
  funktioniert technisch schon, ist aber direkt an die Session gekoppelt und
  kennt keinen Override.
- `api/client.ts` schickt leeren Bearer-Header weg, wenn Token === '' (gut).
- `core/security.py` (API): JWT-Pfad braucht nur `JWT_SECRET`, Token-Pfad
  erkennt den `w2b_`-Praefix. Beide Wege liefern `owner_id`.
- `.env.example`: `JWT_SECRET=` ist auskommentiert ohne Kontext.

## Design-Entscheidung (kein Drei-Optionen-Bedarf)

W2 (Token-UI) und W1 (Auth-Bridge) sind disjunkt: W1 liefert das
Abstraktions-Layer, W2 fuellt es. Damit gilt fuer W1:

- **`w2b_`-Override = In-Memory-Context** (keine Persistenz). Konsistent mit
  `persistSession: false` und der react-conventions-Regel "Auth-Tokens nicht
  in localStorage". W2 entscheidet bei Bedarf, ob es Persistenz braucht.
- **Praezedenz:** Override (nicht-leer) > Supabase-JWT > leerer String. Leerer
  String triggert in `client.ts` bereits das Weglassen des Headers.

## Schritte

1. **`auth/auth-token-context.ts`** anlegen — `AuthTokenContext` (Value:
   `overrideToken`, `setOverrideToken`) + `useAuthTokenContext()`-Hook
   (Throw-on-missing analog `useSession`).
2. **`auth/AuthTokenProvider.tsx`** anlegen — kapselt `useState<string | null>`,
   stellt Context bereit. Single-Provider, in `App.tsx` direkt unter
   `SessionProvider` einhaengen.
3. **`auth/useAuthToken.ts`** anlegen — Hook, der `overrideToken` oder
   `session?.access_token` oder `''` (Praezedenz wie oben) liefert.
4. **`api/useApi.ts`** umstellen: zieht Token aus `useAuthToken()` statt
   direkt aus `useSession()`.
5. **`App.tsx`** — `<AuthTokenProvider>` zwischen `SessionProvider` und
   `Routes` einhaengen.
6. **`.env.example`** — `JWT_SECRET=` aktiv (statt auskommentiert) mit
   Kommentar-Erlaeuterung: "muss exakt dem Supabase-Project-JWT-Secret
   entsprechen (Project Settings -> API -> JWT Settings)". Zusatz-Hinweis,
   dass Web nur `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` braucht.
7. **Tests** — `auth/useAuthToken.test.tsx` (Vitest + RTL): drei Cases —
   (a) kein Override + keine Session → leerer Token, (b) Session, kein
   Override → JWT, (c) Override gesetzt → Override gewinnt. Bestehende
   `LoginPage.test.tsx` und `PersonasPage.test.tsx` muessen den neuen
   Provider mitwrappen, falls sie heute nur `SessionProvider` mocken —
   pruefen und ggf. ergaenzen.
8. **Verify-Lauf:** `npm run lint && npx tsc --noEmit && npm test`.

## Betroffene Dateien

- NEU `apps/web/src/auth/auth-token-context.ts`
- NEU `apps/web/src/auth/AuthTokenProvider.tsx`
- NEU `apps/web/src/auth/useAuthToken.ts`
- NEU `apps/web/src/auth/useAuthToken.test.tsx`
- AENDERN `apps/web/src/api/useApi.ts`
- AENDERN `apps/web/src/App.tsx`
- AENDERN `.env.example`
- Ggf. Test-Setup anpassen (LoginPage/PersonasPage-Tests) — pruefen.

## Risiken / offene Punkte

- Bestehende Tests koennten neuen Provider erwarten — wird in Schritt 7
  aktiv geprueft und nachgezogen.
- `JWT_SECRET`-Doku in `.env.example` ist informativ; Verifikation gegen eine
  echte Supabase-Instanz passiert in W6 (lokaler Smoke).

## Doku-Log

Nach Verify: kurze Notes-Zeile auf der Projektseite mit Pointer auf diese
Plan-Datei. Task-Status -> Review (nach Push) / Done (nach Merge).
