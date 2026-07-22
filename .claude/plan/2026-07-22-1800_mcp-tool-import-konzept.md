# Konzept — MCP-Tool-Import & Sync fuer External Tools (Ausbaustufe B+)

- Status: **Entschieden 2026-07-22 — Variante A+ (siehe §7)**; Umsetzung folgt
  nach ADR-Entwurf + WP-Schnitt
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
5. **Transport-Realitaet:** Erreichbar ist, was das *Backend* per HTTP
   erreicht (Streamable HTTP/SSE). Owner-Einwand 2026-07-22, berechtigt:
   Laeuft Who2Be lokal/On-Prem, sind auch `localhost`-/LAN-Server erreichbar —
   die Grenze ist also **edition- bzw. deployment-abhaengig** (Egress-Policy,
   s. §5), kein absolutes „lokal geht nicht". Was weiterhin nicht geht:
   `stdio`-Server (das hiesse, das Backend spawnt beliebige lokale Prozesse —
   bewusst out of scope) und, in der Cloud-Edition, private IP-Ranges. Die UI
   sagt das transparent an der Verbindungsmaske.
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

## 7. Entscheidung (2026-07-22, Owner)

**Variante A+ statt B:** One-Shot-Import (Option A) **plus** manueller
„Aktualisieren"-Button am Binding — mit erneuter Anmeldung, ohne persistierte
Secrets und ohne eigene `mcp_connection`-Entitaet. Damit beantworten sich die
Owner-Fragen: (a) A (erweitert um Button-Refresh), (b) kein Intervall-Job —
manueller Button reicht fuer v1, (c) Egress ist deployment-abhaengig:
On-Prem/lokal Default **offen** fuer private Ranges (der Owner kontrolliert
die Umgebung; lokale HTTP-Server sind legitime Ziele), Cloud-Edition
**hart geblockt** (SSRF).

Mechanik des Button-Refresh (praezisiert):

1. **Import (Wizard, wie §4):** Ergebnis-Drafts speichern zusaetzlich ihre
   Herkunft im JSONB-Content (ADR-0043 §Architektur-Vorbereitung erlaubt das
   abwaertskompatibel): `source_server_url`, `source_auth_kind`
   (`none`/`bearer`/`header`), `imported_at`, Snapshot der importierten
   `tool_names`. **Kein Secret** wird gespeichert — nur die unkritischen
   Verbindungs-Metadaten.
2. **Aktualisieren (Detail-Seite):** Button oeffnet einen Dialog mit
   vorbefuellter URL (editierbar); bei `auth_kind != none` wird das
   Credential **erneut eingegeben** (write-only, nur fuer diesen einen
   Request verwendet, nie geloggt/persistiert). Backend ruft `initialize` +
   `tools/list`, zeigt den Diff (neu/entfernt/geaendert) und legt auf
   Bestaetigung eine **neue Draft-Version** an — der Status-Workflow bleibt
   der einzige Weg zu `active` (§2.3 unveraendert gueltig).
3. **Kein Hintergrund-Sync:** ohne gespeicherte Credentials gibt es prinzipbedingt
   keinen Cron — bewusster Trade-off (Drift wird nur bei Klick erkannt).
   Ausbaupfad zu B (gespeicherte Connection + Intervall) bleibt offen und
   kompatibel: `source_server_url`/`source_auth_kind` sind dann die Basis.

**Reduzierter WP-Schnitt:** WP-1 Backend-Import-Endpoint (MCP-Client-Call
`initialize`+`tools/list` via httpx, Egress-Guard mit Editions-Default,
Timeouts/Groessenlimits) + Wizard-UI; WP-2 Refresh-Dialog + Diff-Ansicht +
Draft-Erzeugung. ADR-0045 dokumentiert A+ inkl. Abgrenzung zu ADR-0043-C und
Ausbaupfad B.

## 8. Gateway-Reflexion (2026-07-22, Owner: „eventuell doch ueber die
Gateway-Idee nachdenken")

### Was der Gateway strategisch boete

Der Gateway (Who2Be routet `call_tool` des Agenten an den echten Server)
ist nicht nur „Komplexitaet ohne Mehrwert" — die Bewertung aus ADR-0043 galt
fuer den *instruktiven* Anwendungsfall. Inzwischen existiert Infrastruktur,
die dem Gateway ueberraschend weit entgegenkommt und seinen Wert erhoeht:

- **Per-Agent-Policy existiert schon:** `PolicyFilterMiddleware` filtert
  `tools/list` pro Agent (ADR-0042, SSoT `tool_requirements`). Ein Gateway
  wuerde externe Tools in genau dieses Rechtemodell einreihen — Admins
  vergeben Todoist an Agent X, nicht an Agent Y. Das kann heute keine
  Agent-Runtime leisten.
- **Ein Connector pro Agent existiert schon:** OAuth-2.1-Connector mit
  per-Agent-URL (ADR-0036). Gateway hiesse: der User konfiguriert in
  Claude & Co. genau EINEN Connector und bekommt alle externen Tools mit —
  statt N Connectoren pro Runtime zu pflegen.
- **Observability existiert schon:** `usage_event`/Feedback-Flywheel
  (ADR-0038) + Rate-Limits (ADR-0039) wuerden externe Tool-Calls
  mitprotokollieren/begrenzen — zentrale Audit-Sicht ueber alles, was
  Agenten tun.

Der eigentliche strategische Hebel: Who2Be wird vom Anweisungs-Katalog zur
**Kontroll-Ebene fuer Agent-Faehigkeiten** (Persona + Playbooks + Memory +
Tools an einem Ort, mit RBAC/Audit).

### Was er kostet (die ADR-0043-Gruende gelten weiter)

1. **Credential-Storage wird Pflicht** — genau die Oberflaeche, die A+
   vermeidet (verschluesselte Secrets pro Workspace, Rotation, Export-Ausschluss).
2. **Who2Be steht im Laufzeit-Pfad jedes Tool-Calls:** Latenz, Timeouts,
   Streaming-/Session-Bridging (FastMCP als Client UND Server), neue
   Fehlerbilder („Server X antwortet nicht" mitten im Agent-Turn),
   Verfuegbarkeits-Kopplung.
3. **Confused-Deputy-Risiko:** Who2Be ruft mit Workspace-Credentials, was
   ein Agent verlangt — Autorisierung muss pro Agent UND pro Downstream-Tool
   hart geprueft werden; SSRF wird vom Import-Zeitpunkt zum Dauerthema.
4. **Namespacing:** Tool-Namen kollidieren (`add_task` von zwei Servern) —
   Alias-Praefix (`todo__add_task`) noetig, inkl. `tool_requirements`-Logik
   fuer dynamische (nicht mehr statisch gemappte) Tools.

### Drei Optionen fuer den Weg dorthin

- **G1 — Workspace-Credential-Gateway:** `mcp_connection` (aus Option B)
  speichert Verbindung + Secret; Gateway routet per Alias-Namespace; Policy
  via bestehendem Rechtemodell. Trade-off: schnellster Weg zum Nutzen, aber
  ein Workspace-Secret fuer alle Agenten (grobkoernig).
- **G2 — Delegierte Credentials (OAuth-Downstream pro Agent/User):** jeder
  Downstream-Server wird per OAuth vom User autorisiert, Who2Be haelt Tokens
  pro Agent. Feinstes Rechtemodell, aber deutlich groesster Aufwand
  (Downstream-OAuth-Flows, Token-Refresh, Consent-UX) — v2-Material.
- **G3 — Kein Laufzeit-Gateway (Kontroll-Ebene ohne Proxy):** A+/B zu Ende
  bauen; Who2Be verteilt Konfiguration (Connector-Listen, Anweisungen),
  routet aber nie Calls. Billigste Option, verzichtet auf Policy/Audit fuer
  externe Calls.

### Einordnung zur A+-Entscheidung

A+ (§7) wird durch die Gateway-Frage **nicht entwertet, sondern ist Stufe 1
desselben Pfads**: der MCP-Client (`initialize`/`tools/list`), der
Egress-Guard, `source_server_url`/`source_auth_kind` und die importierten
Kataloge sind exakt die Bausteine, die G1 braucht. Empfohlener Pfad:
**A+ jetzt umsetzen → Erfahrung sammeln → Gateway als eigenes ADR (G1 zuerst,
G2 als Ausbaustufe) entscheiden**, sobald der Treiber klar ist (zentrale
Rechtevergabe? Ein-Connector-Komfort? Audit?). Der Treiber bestimmt, ob G1
reicht oder G3 genuegt — Owner-Antwort ausstehend.
