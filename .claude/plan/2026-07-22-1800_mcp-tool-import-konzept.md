# Konzept — MCP-Tool-Import & Sync fuer External Tools (Ausbaustufe B+)

- Status: **Vorschlag — Owner-Entscheidung ausstehend** (kein ADR, keine Umsetzung)
- Datum: 2026-07-22
- Kontext: ADR-0043 (External-Tool-Bindings, bewusst Ausbaustufe B „rein
  instruktiv"), ADR-0031 (Audit-Journals), ADR-0038 (Feedback-/Triage-Muster),
  ADR-0036 (OAuth — Who2Be als MCP-*Server*; hier geht es erstmals um Who2Be
  als MCP-*Client*)
- Anlass: Feature-Wunsch des Owners — „Verbindungsparameter eines MCP-Servers
  eingeben, Tools werden geladen statt manuell angelegt; Verbindungen sollen
  sich automatisch aktualisieren."

## 1. Ausgangslage

External Tools (ADR-0043) sind heute versionierte, **rein instruktive**
Workspace-Aggregate: `display_name`, `mcp_server_name`, `tool_names`,
`usage_notes`, `fallback_note` — **bewusst keine Server-URLs, keine
Credentials** (Ausbaustufe C „Gateway" wurde explizit vertagt). Der User tippt
heute alle Tool-Bezeichner von Hand in `ToolEditorForm` ab; bei Aenderungen am
echten MCP-Server driftet die Bindung unbemerkt.

Der Feature-Wunsch fuellt genau die Luecke zwischen B und C: Verbindungsdaten
erfassen, `tools/list` des Servers abrufen, Bindings daraus erzeugen und
aktuell halten — **ohne** dass Who2Be Tool-Calls proxied.

## 2. Hinterfragung (was ist der eigentliche Job?)

1. **Der Kern-Painpoint ist Erfassung + Aktualitaet, nicht Laufzeit-Routing.**
   Der Agent ruft die Tools weiterhin ueber seine eigene Runtime auf; Who2Be
   liefert nur die Anweisung. Ein Import-Feature muss also nur den *Katalog*
   (Tool-Namen, Beschreibungen, Server-Name) spiegeln — der Gateway (C) bleibt
   aussen vor.
2. **„Verbindungsparameter speichern" ist eine neue Security-Oberflaeche.**
   ADR-0043 hat URLs/Credentials genau deshalb ausgeklammert. Sobald wir sie
   persistieren, brauchen wir: verschluesselte Secret-Ablage, SSRF-Schutz
   (Server-seitige Requests an vom User eingegebene URLs!), Egress-Limits,
   RBAC (admin-only), Audit-Events, Ausschluss aus Export/GDPR-Dumps.
   Das ist machbar, aber der teuerste Teil des Features — und nur fuer den
   Auto-Refresh noetig, nicht fuer den Import selbst.
3. **„Automatisch aktualisieren" kollidiert mit dem Kuratierungs-Modell.**
   `usage_notes`/`fallback_note` sind menschlich kuratierte Inhalte mit
   Status-Workflow (draft→review→active). Ein Silent-Overwrite aktiver
   Versionen durch einen Sync waere ein Bruch des Modells (und ein
   Injection-Vektor, s. u.). Richtig ist: Sync erkennt **Drift** und erzeugt
   **Vorschlaege** (Draft-Versionen / Posteingang-Eintraege nach dem
   Triage-Muster von ADR-0038), niemals stille Aenderungen an Aktivem.
4. **Granularitaet:** `external_tool` ist eine *Faehigkeits*-Bindung (Alias
   `todo`) mit N `tool_names` — nicht 1:1 pro MCP-Tool. Ein Server mit 20
   Tools soll nicht automatisch 20 Aggregate erzeugen. Der Import muss dem
   User die Gruppierung ueberlassen (Default: 1 Binding pro Server,
   abwaehlbare Tools; optional aufsplitten).
5. **Transport-Realitaet:** Von einem self-hosted Server aus sind nur
   HTTP-basierte MCP-Server (Streamable HTTP/SSE) erreichbar. `stdio`-Server
   auf dem Rechner des Users kann das Backend nie erreichen — das muss die UI
   ehrlich sagen (Erwartungsmanagement), sonst wirkt das Feature kaputt.
6. **Untrusted Input:** Tool-Namen und -Beschreibungen eines fremden MCP-
   Servers sind fremdgesteuerter Text und landen ueber `tool-ref`-Pills in
   System-Prompts von Agenten → klassischer Prompt-Injection-Pfad. Importierte
   Beschreibungen muessen als Import gekennzeichnet, laengenbegrenzt und vor
   Aktivierung von einem Menschen gesehen worden sein (Draft-Pflicht).
7. **Braucht es einen Push-Kanal?** MCP kennt `notifications/tools/
   list_changed`, aber das setzt eine stehende Session voraus. Fuer den
   realen Aenderungstakt (Tools aendern sich selten) reicht Poll: manueller
   „Jetzt synchronisieren"-Button + optionaler Intervall-Job. Kein
   Dauer-Socket, keine Timeouts im Rendering-Pfad (Lehre aus ADR-0043-C).

## 3. Drei Optionen

### A) One-Shot-Import ohne gespeicherte Verbindung

Wizard: URL/Auth eingeben → `tools/list` → Auswahl → Drafts anlegen.
Verbindungsdaten werden **nicht persistiert** (nur im Request verwendet).

- Pro: Loest 80 % des Painpoints (kein Abtippen); minimale Security-
  Oberflaeche (keine Secret-Ablage, SSRF-Check nur im Wizard-Call); klein.
- Contra: Kein Auto-Refresh — Drift bleibt unerkannt; fuer jeden Re-Sync
  muss der User die Verbindung neu eingeben.

### B) Import + gespeicherte Connection + Diff-basierter Sync (Empfehlung)

Neue, **nicht versionierte** Workspace-Entitaet `mcp_connection` (Name, URL,
Transport, Auth-Typ, verschluesseltes Secret, `last_sync_at`,
`last_sync_status`). Wizard wie A, zusaetzlich: Bindings merken ihre Herkunft
(`source_connection_id`, `synced_tool_names_hash` im JSONB-Content —
ADR-0043 §Architektur-Vorbereitung erlaubt das abwaertskompatibel). Sync
(Button + optionaler Cron) zieht `tools/list`, vergleicht und erzeugt
**Sync-Vorschlaege**: neue Tools → Import-Vorschlag, entfernte/umbenannte
Tools → Drift-Hinweis am Binding (Badge + Posteingang), geaenderte
Beschreibungen → Draft-Vorschlag. Nie Auto-Write auf aktive Versionen.

- Pro: Loest beide Wuensche (Import + Aktualitaet) im Kuratierungs-Modell;
  `mcp_connection` ist exakt die Vorarbeit, die Ausbaustufe C (Gateway)
  spaeter braucht — kein Wegwerf-Code; Security-Oberflaeche klar begrenzt
  (Read-only-Calls `initialize` + `tools/list`, admin-only).
- Contra: Groesster Teil ist Infrastruktur (Secret-Verschluesselung,
  SSRF-Guard, Sync-Job, Diff-UX) — realistisch 4–6 Arbeitspakete; On-Prem
  braucht konfigurierbare Egress-Policy (private IP-Ranges default geblockt,
  fuer lokale Server aufschaltbar).

### C) Voller Gateway-Modus (Ausbaustufe C aus ADR-0043)

Who2Be proxied zusaetzlich die Tool-Calls des Agenten an den echten Server.

- Pro: Ein Ort fuer Verbindungen *und* Ausfuehrung; Agent-Runtimes brauchen
  keine eigenen Connectoren mehr.
- Contra: Genau die Komplexitaet, die ADR-0043 bewusst vertagt hat
  (Credential-Delegation, Laufzeit-Fehlerbilder, Latenz, Haftung fuer fremde
  Tool-Ausfuehrung); fuer den formulierten Wunsch (nicht manuell anlegen +
  aktuell halten) ueberdimensioniert.

**Empfehlung: B.** A ist als Zwischenschritt legitim (Wizard zuerst, Connection
+ Sync als zweite Welle) — B so schneiden, dass Welle 1 exakt A ist.

## 4. UX-Skizze (instinktiv fuer den User)

1. **Einstieg:** Tools-Liste → Button „Von MCP-Server importieren" (neben
   „Neu"). Wizard Schritt 1: Name, Server-URL, Auth (kein Auth / Bearer /
   Header) — mit Hinweis „nur ueber HTTP erreichbare Server; lokale
   stdio-Server bitte weiterhin manuell beschreiben".
2. **Verbindungstest:** expliziter „Verbinden"-Schritt mit klarem
   Fehlerbild (Timeout, 401, kein MCP-Handshake). Erst nach Erfolg geht es
   weiter — kein stiller Fehlschlag.
3. **Tool-Auswahl:** Checkbox-Liste aller Tools (Name + Server-Beschreibung
   als Vorschau), Default alle an. Gruppierungs-Wahl: „Ein Binding fuer den
   Server" (Default) vs. „Ausgewaehlte Tools als separate Bindings".
   Alias-Vorschlag aus dem Server-Namen, editierbar, Kollisions-Check (409).
4. **Vorbefuellung:** `mcp_server_name`, `tool_names` aus dem Handshake;
   `usage_notes` aus den Tool-Beschreibungen als gekennzeichneter
   „Importiert am …"-Block. Ergebnis entsteht als **Draft** — der normale
   Review-/Aktivierungs-Workflow bleibt der einzige Weg zu `active`.
5. **Sync:** Settings-Sektion „MCP-Verbindungen" (admin-only): Liste mit
   letztem Sync-Zeitpunkt/-Status, „Jetzt synchronisieren", optionales
   Intervall (z. B. taeglich). Drift erscheint als Badge am betroffenen
   Binding + Eintrag im bestehenden Posteingang; ein Klick zeigt den Diff
   (neu/entfernt/geaendert) und bietet „als Draft uebernehmen" an.

## 5. Sicherheits-Leitplanken (Pflicht, Welle-1-relevant)

- SSRF: URL-Validierung + DNS-Resolve-Check gegen private/link-local Ranges,
  Default-deny, per Env fuer On-Prem oeffenbar; Redirects nicht folgen;
  harte Timeouts; Response-Groessenlimit.
- Secrets: Envelope-Verschluesselung in der DB, nie im API-Read zurueckgeben
  (write-only Feld), nie in Exporten/GDPR-Dumps, Audit-Event bei Anlage/
  Aenderung/Sync (ADR-0031-Muster).
- RBAC: `mcp_connection` CRUD + Sync nur `admin`; Import-Ergebnis (Drafts)
  folgt normalem Editor-RBAC.
- Prompt-Injection: importierte Beschreibungen sind untrusted — Kennzeichnung,
  Laengenlimits (bestehende `max_length` greifen), keine Auto-Aktivierung.
- `security-reviewer`-Subagent vor Merge jeder Welle (CLAUDE.md §Security).

## 6. Naechste Schritte (bei Zustimmung)

1. ADR-Entwurf „0045 — MCP-Connections & Tool-Import (Ausbaustufe B+)"
   inkl. Abgrenzung zu ADR-0043-C.
2. WP-Schnitt (Wellen): WP-1 Wizard one-shot (=Option A), WP-2
   `mcp_connection`-Entitaet + Secret-Storage + SSRF-Guard, WP-3 Sync-Job +
   Diff/Drift-UX, WP-4 MCP-/Builder-Exposure (optional, spaeter).
3. GitHub-Issues je WP, dann Umsetzung ueber Code-Task-Flow.

Offene Owner-Fragen: (a) Option B bestaetigen oder bewusst nur A? (b) Sync-
Intervall-Job noetig oder reicht manueller Button fuer v1? (c) On-Prem-Egress-
Default (private Ranges blocken vs. offen)?
