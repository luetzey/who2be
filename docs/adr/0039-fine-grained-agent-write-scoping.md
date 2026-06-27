# ADR-0039 — Feinkoernige Per-Agent-Write-Rechte (Praedikat-Scopes, getrennte Promote/Retire, TTL)

- Status: Partially Accepted
- Datum: 2026-06-27

## Umsetzungsstand (2026-06-27)

**Umgesetzt (Track 4-A, Branch `claude/track4-finer-rights`):**
- **Getrennte Promote/Retire pro Domain** — `TransitionGrant{promote,retire}` +
  `AgentToolPolicy.transition_grants` (Narrowing von `promote_retire`, additiv/
  JSONB-abwaertskompatibel), Gate `_require_transition_capability` + `can_transition`,
  `is_within`-Anti-Escalation. DB-frei getestet.
- **Befristete Grants (TTL)** — `TokenCreate.expires_at` exponiert (Spalte +
  Auth-Enforcement existierten bereits, Migration 0049).

**Umgesetzt (Track 4-B):**
- **Web-Policy-Editor-Sync** — `AgentEditorForm` exponiert `system_prompt_write`
  + `feedback_write`; `valuesToPolicy` merged unbekannte Policy-Felder (kein
  Datenverlust beim Speichern).
- **Tag-Praedikat-Write-Scoping** — `AgentToolPolicy.write_tags` (Dict je Domain
  → erlaubte Tags; leer = unrestricted, JSONB-abwaertskompatibel),
  `tags_permitted`/`write_tags_for`, `is_within`-Anti-Escalation. Gate
  `require_write_tags` in persona/playbook/resource create+update+restore:
  eingehende Tags immer, Bestands-Tags beim Update (verhindert Uebernahme/Retag
  eines out-of-scope-Elements). DB-Integrationstest gruen.

- **`write_tags`-Tag-Picker im `AgentEditorForm`** — drei kommaseparierte
  Tag-Felder je Domain (persona/playbook/resource), gemappt zum `write_tags`-Dict
  (Submit + Reset). `whoami` gibt `write_tags` + `transition_grants` aus.

**Offen (Folge):** Write-Rate-Limit; UI-Widgets fuer `transition_grants`
(per-Domain Promote/Retire) + Token-Ablauf im Editor (Backend steht).
- Kontext: User-Wunsch nach detaillierterer Einstellbarkeit; die Per-Agent-Policy
  ist heute grobkoerniger als das Vertrauensmodell erlaubt.
- Bezug: ADR-0023 (RBAC / Token-Snapshot), ADR-0009 (JSONB-Schema-Evolution),
  ADR-0030 (MCP-Write-Tools), `.claude/plan/2026-06-05-1500_per-agent-mcp-tool-policy.md`

## Kontext

`AgentToolPolicy` steuert Writes heute nur **pro Domain als Boolean**
(`playbook_write` an/aus) und kennt `promote_retire` als **eine** Capability ueber
alle Domains. Damit lassen sich reale Wuensche nicht abbilden:

- „Agent darf Playbooks mit Tag `support` editieren, aber nicht `legal`."
- „Agent darf Playbooks promoten, aber keine Personas; nie retiren."
- „Schreibrecht nur befristet (Pilot fuer 14 Tage)."

Lese-Scoping ist bereits granular (`all`/`assigned`/`none`); der Schreibpfad
hinkt hinterher.

## Entscheidung

Wir erweitern die Policy entlang dreier Achsen — **JSONB-abwaertskompatibel**
(ADR-0009): fehlende Felder deserialisieren zum bisherigen Verhalten, kein
destruktiver Migrationsschritt.

1. **Praedikat-basierter Write-Scope.** Jede Write-Domain wird von `bool` zu
   einem optionalen `WriteGrant{ enabled: bool, scope: WriteScope }` gehoben.
   `WriteScope ∈ { all, assigned, tagged(tags: list[str]) }`. Legacy `true`
   deserialisiert zu `{enabled:true, scope: all}`. Durchsetzung im Mutating-Service:
   Ziel-Tags muessen den Scope erfuellen (`tagged` ⇒ Schnittmenge nicht leer),
   sonst 403. `assigned` koppelt an das bestehende `visible_*_ids`.
2. **Getrennte Transition-Rechte.** `promote_retire` (eine Capability) wird durch
   ein optionales `transition_grants: dict[domain, {promote: bool, retire: bool}]`
   ueberlagert. Fehlt der Eintrag, gilt der Legacy-Wert `promote_retire` als
   Fallback fuer beide Richtungen — Bestands-Policies bleiben unveraendert.
   Hinweis: Die **Rollen**-Eskalation bleibt unangetastet — Promote/Retire bleibt
   serverseitig `admin`-pflichtig (ADR-0023, `version_status.required_role`); die
   Capability ist die *zusaetzliche* Pro-Agent-Schranke, nicht ihr Ersatz.
3. **Befristete Grants (TTL).** `api_token.expires_at` (nullable) — ein an einen
   Agenten gebundener Token kann ablaufen; abgelaufen ⇒ 401. Optional pro Token
   ein Write-Rate-Limit (Spalte vorgesehen, Enforcement separater Plan).

`is_within` (Anti-Escalation, `tool_policy.py`) wird auf die neuen Felder
erweitert: ein agent-gebundener Aufrufer darf via `agent_write` keinen Agenten
mit weiterem Scope, mehr Transition-Rechten oder spaeterem Ablauf anlegen als er
selbst hat.

## Konfigurierbarkeit (der eigentliche User-Request)

- **Web-UI `AgentEditorForm`** bekommt die reicheren Controls: pro Write-Domain
  Scope-Auswahl (all/assigned/tagged + Tag-Picker), Promote/Retire-Switches je
  Domain, optionales Ablaufdatum beim Token-Binding.
- **`whoami`** gibt die effektive Policy inkl. Scopes/Transition-Rechte/Ablauf
  aus, damit der Agent (und der Owner) die geltenden Schranken introspizieren kann.

## Konsequenzen

- `tool_policy.py`: neue Typen `WriteScope`/`WriteGrant`, erweiterte
  `allows(cap, target_tags?)`-Signatur, `is_within`-Erweiterung; Validatoren fuer
  Legacy→neu. Kein DB-Migrationszwang fuer `agent.tool_policy` (JSONB).
- Migration nur fuer `api_token.expires_at` (+ optional `write_rate_limit`).
- Enforcement-Punkte: dieselben Service-Gates wie ADR-0030 (`require_capability`),
  jetzt mit Ziel-Tag-Pruefung; Transition-Gate liest `transition_grants`.
- Risiko: groessere Policy-Oberflaeche ⇒ mehr Test-Matrix. Mitigation:
  Tabellen-getriebene Tests (Scope × Domain × Ziel-Tags × Transition).
