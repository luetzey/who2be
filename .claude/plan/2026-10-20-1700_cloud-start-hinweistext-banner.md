# Cloud-Start: Hinweistext frei pro Sprache, OAuth-Ablehnung, Wartungsbanner

Kanban-Karte t_27d7c6ad. Kein GitHub-Issue.

## Ziel

Betreiber setzt freien Text pro Sprache über Runtime-Env (kein Rebuild):

- `WHO2BE_LAUNCH_MESSAGE_DE` / `_EN` ersetzt den Fließtext der Hinweisseite (`/signup` im Launch-Modus).
- Lehnt GoTrue eine Provider-Anmeldung wegen gesperrter Registrierung ab
  (`error_code=signup_disabled`, Fallback Text „Signups not allowed“), zeigt
  `/auth/callback` dieselbe Hinweisseite statt des Rohfehlers.
- `WHO2BE_NOTICE_DE` / `_EN` + `WHO2BE_NOTICE_LEVEL` (info|warning) zeigen ein
  Banner auf `/login` und oben in der App. In der App pro Sitzung wegklickbar.

## Entscheidungen (aus dem Repo belegt)

- GoTrue-Fehlerform belegt im Quelltext (supabase/auth `internal/api/external.go`,
  `getErrorQueryString` + `redirectErrors`): `error=access_denied`,
  `error_code=signup_disabled`, `error_description=Signups not allowed for this instance`,
  im Query UND im Fragment.
- Sprachwahl: aktive Sprache, sonst die andere (EN → DE wie verlangt, DE → EN symmetrisch).
- Länge: 500 Zeichen (Code-Points), getrimmt, in `src/config.ts`.
- Rendering: React-Textknoten + `whitespace-pre-line`; kein HTML, keine Links.
- Titel der Hinweisseite bleibt (einzige H1); ersetzt wird der Fließtext.
- Banner-Rolle: info → `status`, warning → `alert`.
- Wegklicken: `sessionStorage`, Schlüssel speichert den Text — neuer Text erscheint wieder.
- Runtime-Skript: neuer `json_str()` (sed/awk, busybox-tauglich) für die Freitext-Felder:
  `\`, `"`, Zeilenumbruch → `\n`, `<`/`>` → `\u003c`/`\u003e`, Steuerzeichen entfernt.
  Bestehende Felder bleiben bei `sanitize()`.

## Schritte

1. config.ts + Runtime-Skript + Tests (Skript per `sh` + `node:vm` geprüft).
2. NoticeBanner-Komponente + Tests (Escaping, Rollen, Wegklicken, axe).
3. ComingSoonPage (Freitext), AuthCallbackPage (Erkennung), LoginPage + AppShell (Banner).
4. i18n DE/EN, Doku (§1, RUNBOOK), `.env.example` ×2, Compose ×3, changelog.d.
5. DoD lokal, Fotos 1280 hell / 390 dunkel, PR.
