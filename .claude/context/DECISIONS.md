# DECISIONS — Warum so (append-only)

Tragende **Architektur**-Entscheidungen leben als ADR unter
[`../../docs/adr/`](../../docs/adr/) — das ist die kanonische Quelle (0001–0036).
Diese Datei hält **leichtere, session-übergreifende** Entscheidungen, die keinen
eigenen ADR rechtfertigen. Append-only: nie umschreiben; eine Revision bekommt
einen neuen Eintrag mit Verweis.

## 2026-06-14 — LLM-Standards als Repo-Markdown (`docs/standards/`)
- **Entscheidung:** Die stehenden Engineering-Standards (zuvor extern) werden als
  self-contained Markdown unter `docs/standards/` materialisiert; `AGENTS.md` als
  tool-agnostischer Einstieg; `.claude/context/` als Projekt-Gedächtnis.
- **Begründung:** Repo muss ohne externe Quelle vollständig LLM-verständlich sein
  (Anti-Drift). Single-Source: wo ADR/Skill existiert, wird verlinkt statt kopiert.
- **Verworfen:** nur indexieren ohne Materialisieren (Standards blieben verstreut);
  Enforcement-Tooling (zu viel Pflege-Overhead jetzt).

## 2026-06-14 — Repo von externem Agent-Workspace entkoppelt
- **Entscheidung:** Persönlicher Agent-Bootstrap aus `CLAUDE.md` → gitignored
  `CLAUDE.local.md`; öffentliche Docs selbsttragend. `.claude/plan/` bleibt
  öffentlich (Referenz-IDs gewähren ohne Auth keinen Zugriff).
- **Begründung:** Public-Switch-Vorbereitung; öffentliche Datei soll nicht auf
  eine private Quelle als Autorität verweisen.

## 2026-06-14 — Kein History-Rewrite für den Public-Switch
- **Entscheidung:** Bestehende Commits/IDs bleiben in der History.
- **Begründung:** IDs/E-Mail gewähren ohne Auth keinen Zugriff; Rewrite-Risiko
  überwiegt den Nutzen.

## 2026-06-25 — Per-Agent-Connector-URL `?agent=<uuid>` (OAuth)
- **Entscheidung:** Connector-URL darf `…/mcp?agent=<uuid>` tragen; `authorize`
  akzeptiert kanonische Resource **oder** Basis + genau `?agent=<uuid>`. Hint wandert
  in den signierten Blob (kanonische Resource bleibt die Audience); Consent **sperrt**
  den Agenten hart (signierter Wert gewinnt, client-`agent_id` ignoriert). UI zeigt die
  fertige URL auf der Agent-Detail-Seite (`AgentConnectorSection`). Detail: ADR-0036-Addendum.
- **Begründung:** Claude dedupliziert Connectoren nach URL → eindeutige URL je Agent nötig.
  Membership-Prüfung bleibt das autoritative IDOR-Gate; Audience-Kette unangetastet.
  Security-Review ohne ausnutzbaren Befund.
- **Verworfen:** Subdomain-/Pfad-pro-Agent (Infra-Overhead pro Agent); Token im Connector/
  Systemprompt (unnötig, da OAuth-gebunden). **Fail-safe:** ohne Query gilt die Consent-Auswahl.
- **Offen:** E2E gegen echten Claude-Client (ob der `?agent=`-Query als OAuth-`resource`
  ankommt) — durch Fail-safe unkritisch.

## 2026-07-01 — MFA-Step-up: Hold-back im `apply()`, nicht neuer Context-Vertrag
- **Entscheidung:** Die `aal1`-mit-fälligem-Step-up-Session wird zentral in
  `SessionProvider.apply()` zurückgehalten (autoritatives Gate gegen die
  onAuthStateChange-Race), nicht nur im `signIn`-Rückgabewert. Die Challenge/
  Verify-Logik lebt direkt in der `LoginPage` (via `supabase.auth.mfa`, analog
  `MfaSection`) statt als neue `verifyMfa`-Methode im `SessionValue`-Interface.
  `getAuthenticatorAssuranceLevel` fällt bei Fehler fail-open auf „kein Step-up"
  zurück — das Backend-Gate `require_aal2` bleibt die harte Grenze.
- **Begründung:** `apply()`-Gate schließt die Race deterministisch (egal ob der
  Event aus signIn, Reload oder Refresh stammt). Kein Interface-Zwang auf ~28
  Test-Literale (`signIn: vi.fn()` bleibt zuweisbar; Rückgabetyp-Wechsel auf
  `{ mfaRequired }` ist kompatibel). Fail-open verhindert, dass ein getAAL-
  Ausfall den Login komplett blockiert, ohne die Server-Autorität zu schwächen.
- **Verworfen:** Globaler Step-up-Modal bei jedem 403 `mfa_required` (größerer
  Eingriff, App-weiter Zustand); `verifyMfa` im Context (Test-Churn ohne Nutzen).

_Bei Wachstum: älteste Einträge zu Einzeilern komprimieren (Titel + Entscheidung
bleiben)._
