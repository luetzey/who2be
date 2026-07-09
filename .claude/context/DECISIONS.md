# DECISIONS — Warum so (append-only)

Tragende **Architektur**-Entscheidungen leben als ADR unter
[`../../docs/adr/`](../../docs/adr/) — das ist die kanonische Quelle
(vollständige, aktuelle Liste: siehe `docs/adr/`).
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

## 2026-07-05 — OAuth-Refresh-Reuse: Reject-only statt Ketten-Revocation
- **Entscheidung:** Wiederverwendung eines bereits konsumierten Refresh-Tokens
  außerhalb des 30-s-Grace-Fensters wird nur noch mit `invalid_grant` + Warn-Log
  abgelehnt — `revoke_refresh_chain` läuft dabei NICHT mehr. Die Ketten-Revocation
  bleibt für echte Sicherheits-Events (Membership-Verlust beim Refresh /
  Deprovisioning). Bewusste Abweichung von RFC 9700 §4.14.2 (Revocation-on-Reuse).
- **Begründung:** MCP-Clients (Claude) sind multi-runtime: mehrere Agenten teilen
  sich die Connector-Tokens, veraltete Refresh-Kopien werden gutartig retried.
  Jeder Retry killte alle aktiven Access-Tokens der Kette (auch frisch rotierte
  der gesunden Runtime) → permanenter „verbunden, aber keine Tools"-Lockout
  (Repro gegen echten Stack; #293-Grace war zu eng und single-use). Die
  Revocation stoppte zudem keinen echten Dieb: sie widerrief nur `api_token`-
  Zeilen, nie die Refresh-Kette — ein Dieb mit Nachfolge-Refresh mintet einfach
  neu. Kosten (täglicher Lockout) ohne Nutzen (kein Diebstahl-Schutz).
- **Verworfen:** Grace-Fenster verbreitern (Retry-Loops fallen aus jedem endlichen
  Fenster und killen dann doch); Refresh-Rotation abschaffen (OAuth-2.1-Vorgabe
  für Public Clients); Ketten-Kill inkl. Refresh-Tokens „richtig" bauen (würde
  multi-runtime Clients erst recht hart aussperren).

## 2026-07-09 — Builder-/UI-Block (PR #301): vier kleine Richtungsentscheidungen
- **Trigger-Migration 0063 normalisiert ALLE Versions-Snapshots in-place** (nicht
  nur aktive, keine neuen Versionen): rein syntaktische Kanonisierung (`;`→`,`,
  trim, dedupe) — sonst zeigt jeder künftige Versions-Diff dauerhaft
  Trigger-Rauschen gegen die neue Kanonik. Write-Pfad normalisiert ab jetzt via
  Pydantic-Validator (`normalize_triggers`), Read-Pfad heilt sich beim Parsen selbst.
- **`?group=` ist Anzeige-Präferenz, kein Filter:** zählt nicht in `active`,
  wird von `reset()` nicht geräumt (Gruppierung reduziert nie die Treffermenge).
- **`get_persona(mode=…)`/`render(mode=…)` statt persistentem Agent-Modus:**
  Modus-Anwendung bleibt zustandslos pro Abruf (identity_add append,
  output_style_override replace, 422 mit Modi-Liste bei Unbekanntem); ein
  gespeicherter „aktiver Modus" pro Agent wurde bewusst verworfen (Zustand ohne
  belegten Bedarf).
- **Builder darf Templates via MCP verfassen (Seed-Korrektur zu ADR-0040):**
  Das Agent-Playbook verbot den Template-Bau via MCP, obwohl ADR-0040 +
  `system_prompt_write` ihn vorsehen — Seeds folgen jetzt dem ADR (draft→review;
  Aktivieren bleibt Mensch/UI). Placeholder-Format ist über den neuen
  `GET …/placeholders`-Katalog + `list_placeholders` zur Laufzeit entdeckbar
  statt nur im Frontend-Code.

_Bei Wachstum: älteste Einträge zu Einzeilern komprimieren (Titel + Entscheidung
bleiben)._
