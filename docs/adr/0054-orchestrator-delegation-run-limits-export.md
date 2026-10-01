# ADR-0054 — Orchestrator: Delegationsobjekt (A2A), `run_limits`, A2A-Agent-Card und AGENTS.md-Export, Prüffall `tool_trace`

- Status: **Accepted** (Owner, 2026-09-30). Alle fünf Weichen sind
  entschieden, der Owner-Wortlaut steht in Abschnitt 2.
- Datum: 2026-10-01
- Gemessen gegen: `origin/main` @ `e1fbe695`. Code-Aussagen tragen einen
  Symbolanker (Konvention `docs/code-references.md`).
- Grundlage: Recherche „Orchestrator-Agent und Multi-Agent-Systeme“
  (Karte t_03beff7a, Stand 2026-09-30, Bericht
  `orchestrator-agent-multi-agent-2026-09-30.md` mit Belegordner
  `-belege/`, außerhalb des Repos). Abschnittsangaben „Bericht §n“ beziehen
  sich darauf.
- Bezug: ADR-0040 (Aktivierung nur durch Menschen), ADR-0047 und ADR-0053
  („Who2Be ist kein Runtime-Host“), ADR-0053 (Prüffälle, `check_kind`,
  `submit_test_results`), ADR-0043 (externe Tools beschreiben, nicht
  erzwingen), ADR-0024 (Composite-Playbooks), ADR-0026 (Persona-`skills`
  nur deskriptiv, Feld deaktiviert).
- Umfang: **nur Entscheidung.** Diese ADR ändert keinen Code, kein Schema und
  keine Migration. Die Umsetzung beginnt erst nach dem Cloud-Test
  (Abschnitt 7).

## Inhalt

1. Kontext und Kernbefunde
2. Entscheidung (Owner-Wortlaut)
3. Leitplanke: deklarieren und nachprüfen, nicht durchsetzen
4. Die fünf Weichen im Einzelnen
5. Offene Detailfragen
6. Konsequenzen
7. Umsetzungsreihenfolge (Vorschlag, nach dem Cloud-Test)

---

## 1. Kontext und Kernbefunde

Die Recherche prüft, ob und wie Who2Be einen Orchestrator-Agenten beschreiben
kann: einen Agenten, der Aufgaben zerlegt, an Fachagenten delegiert, prüfen
lässt und zusammenführt. Die Befunde, auf die sich die Entscheidung stützt
(Typangaben wie im Bericht: MESSUNG, DOKU, NORM, EINSCHÄTZUNG):

**Multi-Agent lohnt sich nur bei zerlegbaren Aufgaben** [MESSUNG]. Die größte
kontrollierte Studie (Google/DeepMind u. a., arXiv 2512.08296, 260
Konfigurationen) misst je nach Aufgabe „+80,8 % (zerlegbares
Finanz-Reasoning) bis −70,0 % (sequenzielle Planung) gegenüber
Einzelagent“ (Bericht §1.1). Die Fehlerverstärkung liegt bei „Einzel 1,0 ·
zentral 4,4 · hybrid 5,1 · dezentral 7,8 · unabhängig 17,2“. Ab einer
Obergrenze gilt: „beyond 3–4 agents [...] communication cost dominates
reasoning capability“ (aus einem Fit extrapoliert, Bericht §8). Ein
Einzelagent mit Skills erreicht laut arXiv 2601.04748 „gleiche Genauigkeit
(−2,0 … +4,0 %), −54 % Tokens, −50 % Latenz“.

**Wirksam sind Zustand, Vertrag und getrennte Prüfung** [MESSUNG/DOKU].
Magentic-One (arXiv 2411.04468) misst „ohne Task-/Progress-Ledger −31 %“.
Anthropic nennt für jeden Auftrag an einen Subagenten „Specific research
objectives, ideally just 1 core objective per subagent“, „Expected output
format“, „Relevant background context“, Quellen, „Specific tools“ und „If
needed, precise scope boundaries to prevent research drift“ (Cookbook,
research_lead_agent.md). Das Claude Agent SDK hält fest, dass ein Subagent
weder „The parent's conversation history or tool results“ noch „The parent's
system prompt“ bekommt. Die Fehleranalyse MAST (arXiv 2503.13657) ordnet
„Task Verification 21,3 %“ der Fehler zu.

**Budgets sind ohne Konfiguration offen** [DOKU]. Das Claude Agent SDK kennt
Tiefe („Default \"3 layers of subagents below your main agent.\"“),
Parallelität („Default \"20 subagents running at once\"“) und Kosten
(„maxBudgetUsd in TypeScript, max_budget_usd in Python“ – Default „No
limit.“). Magentic-One bricht bei einem Stall-Zähler ab: „As long as this
counter remains below a threshold (≤ 2 in our experiments), the Orchestrator
initiates the next team action“.

**A2A ist der einzige Standard für Delegation zwischen Agenten** [NORM]. A2A
1.0 (a2a-protocol.org, Spec 1.0.0, Release v1.0.1 vom 2026-05-28)
definiert: „Task is the core unit of action for A2A. It has a current status
and when results are created for the task they are stored in the artifact.“
(§4.1.1). Die Agent Card ist „A self-describing manifest for an agent. It
provides essential metadata including the agent's identity, capabilities,
skills, supported communication methods, and security requirements.“
(§4.4.1). Skills sind „largely a descriptive concept but represents a more
focused set of behaviors that the agent is likely to succeed at.“ AGENTS.md
dagegen ist laut eigener FAQ „just standard Markdown. Use any headings you
like“ – kein Delegations- und kein Rechte-Standard (Bericht §4).

**Ist-Stand Who2Be** (Bericht §5.1, gemessen gegen `e65e5a72`, hier gegen
`e1fbe695` nachgeprüft). Rechte (`AgentToolPolicy`), menschliche Freigabe
(ADR-0040), Rolle und Prozeduren (Persona, Playbooks) tragen bereits. Es
fehlen vier Dinge:

| Lücke | Inhalt | Beleg |
|---|---|---|
| L1 | Delegationsbeziehung „A delegiert an B, mit Vertrag X“ | kein Feld in `packages/models/src/who2be_models/agent.py#AgentRead` |
| L2 | Budget/Abbruch (Worker, Tiefe, Kosten, Stall-Schwelle) | kein Feld in `packages/models/src/who2be_models/tool_policy.py#AgentToolPolicy`; nächster Verwandter ist `write_rate_limit` |
| L3 | Prüffall, der Handlungen statt Text prüft | `packages/models/src/who2be_models/test_case.py#TestCheckKind` kennt nur `human_rule`, `must_contain`, `must_not_contain` |
| L4 | Eskalationszustand (A2A `TASK_STATE_INPUT_REQUIRED`) | nur als Prompt-Text abbildbar |

Der Bericht folgert daraus: „Who2Be kann Budget und Delegation nicht
**durchsetzen**, weil es nicht ausführt. Es kann sie nur **deklarieren** (als
Vertrag für die Laufzeit: Hermes, Claude SDK, A2A-Client) und **nachprüfen**
(Prüffälle). Die Lücken L1–L4 sind deshalb Beschreibungs- und Prüflücken,
keine Laufzeitlücken.“ (Bericht §5.1, als EINSCHÄTZUNG gekennzeichnet).

## 2. Entscheidung (Owner-Wortlaut)

Owner-Entscheidung vom 2026-09-30 zu den Weichen W1–W5 aus Bericht §7,
Wortlaut: **„1. C, 2.B 3. B + C, 4. b, 5. a“**.

| Weiche | Gewählt | Inhalt der gewählten Option |
|---|---|---|
| W1 Delegation im Modell (L1) | **C** | Vollständiges Delegationsobjekt mit Feldschema (Ziel, Format, Grenzen, Abnahme) als A2A-Task-Vorlage. |
| W2 Budget/Abbruch (L2) | **B** | Deklaratives Feld `run_limits` am Agent (`max_parallel`, `max_depth`, `stall_threshold`, `max_budget_usd`), das die Laufzeit liest und Prüffälle referenzieren. Keine Durchsetzung in Who2Be. |
| W3 Standard-Export | **B + C** | A2A-Agent-Card je Agent **und** AGENTS.md-Export. Vorab offen: A2A-`skills`-Schema gegen Playbooks abgleichen. |
| W4 Handlungsprüfung (L3) | **B** | Neuer `check_kind: tool_trace`. Die Laufzeit meldet die Aufrufsequenz, Who2Be prüft Muster. Kein LLM-Richter. |
| W5 Standard für neue Nutzer | **A** | Default bleibt Einzelagent + Playbooks, Orchestrator nur als Vorlage. |

Bei W1 wich der Owner bewusst von der Empfehlung des Berichts ab (dort: „B.
C erst, wenn eine Laufzeit A2A spricht.“) und ebenso von der PM-Empfehlung B.
C ist die Option mit dem größten Aufwand und am nächsten am Standard. Diese
ADR setzt C um, ohne sie auf B zurückzuschneiden. Bei W3 wählte der Owner
über die Empfehlung (B) hinaus zusätzlich C.

## 3. Leitplanke: deklarieren und nachprüfen, nicht durchsetzen

Für alle fünf Weichen gilt die bestehende Grenze aus ADR-0047 und ADR-0053:
Who2Be ist kein Runtime-Host und führt keine LLM-Aufrufe aus. Daraus folgt
für diese ADR:

- **Delegationsobjekt (W1) und `run_limits` (W2) sind Deklarationen.** Who2Be
  speichert, versioniert, validiert und exportiert sie. Befolgen muss sie die
  Laufzeit (Hermes, Claude Agent SDK, ein A2A-Client). Who2Be startet keinen
  Task, zählt keine Parallelität mit und bricht nichts ab.
- **Nachprüfen ist Aufgabe der Prüffälle (W4).** Ob eine Laufzeit die
  Deklaration eingehalten hat, prüft Who2Be deterministisch an einer
  gemeldeten Aufrufsequenz, nicht an einer Selbstauskunft in Prosa.
- **Kein LLM in der Bewertung.** Das bleibt aus ADR-0044 und ADR-0053
  bestehen. W4-C (LLM-Richter) ist ausdrücklich verworfen.
- **Aktivierung bleibt beim Menschen** (ADR-0040). Ein Agent-Token kann weder
  ein Delegationsobjekt noch `run_limits` scharf schalten, die an einem
  aktiven Agenten hängen, ohne dass der übliche Versions- und
  Freigabeweg greift. Wie das im Detail aussieht, klärt Abschnitt 5 (O1.6).

## 4. Die fünf Weichen im Einzelnen

### 4.1 W1 = C — Delegationsobjekt als A2A-Task-Vorlage

**Gewählt:** Ein eigenes, versioniertes Objekt beschreibt eine Delegation von
einem Agenten (Delegierender) an einen anderen (Empfänger). Es ist eine
**Vorlage** für den A2A-Task, den die Laufzeit beim Delegieren erzeugt – kein
laufender Task.

**Skizze der Felder** (Arbeitsstand, feldgenau festgelegt erst in der
Spezifikation, Paket O1 in Abschnitt 7):

| Feld | Pflicht | Inhalt | Herkunft |
|---|---|---|---|
| `from_agent_id` | ja | delegierender Agent | Who2Be |
| `to_agent_id` | ja | Empfänger (Agent im selben Workspace) | Who2Be |
| `goal` | ja | ein Kernziel („1 core objective per subagent“) | Owner-Schema „Ziel“, Anthropic |
| `output_format` | ja | erwartetes Ergebnisformat | Owner-Schema „Format“, Anthropic „Expected output format“ |
| `context` | nein | Hintergrund, den der Empfänger sonst nicht hat | Anthropic „background context“, Claude SDK „only content you pass“ |
| `tools_sources` | nein | Werkzeuge, Startquellen, Qualitätskriterien | Anthropic „Specific tools“, „starting points and sources“ |
| `boundaries` | ja | Scope-Grenzen, Out-of-Scope, verbotene Aktionen | Owner-Schema „Grenzen“, Anthropic „scope boundaries“ |
| `acceptance` | ja | Abnahmekriterium, wer abnimmt (nie der Ersteller) | Owner-Schema „Abnahme“, Bericht §2 |
| `escalation` | nein | wann der Empfänger `INPUT_REQUIRED` statt einer Annahme meldet | A2A §4.1.3, Lücke L4 |

Die vier Owner-Felder (Ziel, Format, Grenzen, Abnahme) sind Pflicht. Die
übrigen ergänzen sie zu den sechs Vertragsfeldern aus Bericht §5.2.

**Bezug zu A2A.** Das Delegationsobjekt ist die Vorlage für die erste
`Message` (Rolle Nutzer bzw. Client) eines neuen A2A-`Task`:

- `goal`, `output_format`, `context`, `tools_sources`, `boundaries` und
  `acceptance` werden zu `Part`s dieser Message – als Text-Part für den
  Empfänger lesbar und zusätzlich als strukturierter Data-Part, damit eine
  Laufzeit sie maschinell auswerten kann.
- Ergebnisse kommen als A2A-`Artifact` zurück („An output (e.g., a document,
  image, structured data) generated by the agent as a result of a task,
  composed of Parts.“). `acceptance` beschreibt, woran ein solches Artifact
  gemessen wird.
- `escalation` bildet auf die unterbrochenen Zustände
  `TASK_STATE_INPUT_REQUIRED` und `TASK_STATE_AUTH_REQUIRED` ab. A2A §7.6.4
  gilt dabei unverändert: „Agents MUST NOT treat the
  TASK_STATE_AUTH_REQUIRED state transition, by itself, as authorization for
  any particular operation.“
- Eine Who2Be-Kennung der Vorlage (ID und Version) wandert in `Task.metadata`,
  damit ein gemeldeter Lauf (W4) auf die Vorlage zurückführt.

**Beziehung Agent → Agent.** Ein Delegationsobjekt verbindet genau einen
Delegierenden mit genau einem Empfänger. Ein Agent kann mehrere
Delegationsobjekte haben, auch mehrere an denselben Empfänger (verschiedene
Auftragsarten). Daraus ergibt sich zugleich die Liste der möglichen Empfänger
– die Relation `delegates_to` aus W1-B entsteht als Sicht auf die
Delegationsobjekte und wird nicht getrennt gepflegt (Single Source of Truth).

**Verworfen:**

- **A – gar nicht im Modell, Team als Resource im Prompt.** Kein Aufwand,
  aber Delegation bliebe Prompt-Wahrscheinlichkeit – genau das, wovon sich
  Who2Be abgrenzt (Bericht §5, Kurzantwort 5).
- **B – Relation `delegates_to` mit Kurzvertrag je Kante.** Empfehlung von
  Bericht und PM, weil billiger. Der Owner hat C gewählt, weil C
  standardnah ist und den Vertrag feldgenau statt als Freitext führt. B geht
  in C auf (siehe Beziehung oben), ein getrennter Bau von B entfällt.

**Folgen:**

- *Datenmodell:* neues Aggregat mit eigener Tabelle, `workspace_id`, RLS-Policy
  `tenant_isolation` wie jede neue Tabelle (ADR-0053 §1), Fremdschlüssel auf
  zwei Agenten. Versionierung nach dem Muster der übrigen versionierten
  Aggregate (O1.2).
- *API:* CRUD unter dem Agenten, Lesen für alle Rollen mit Lesezugriff auf den
  Agenten, Schreiben wie Agent-Konfiguration.
- *MCP:* Lesen über ein neues Lese-Werkzeug oder als Teil von `get_agent`;
  Schreiben nur mit einer neuen Write-Capability (O1.5). Eine Pill
  `{{agents-catalog}}` (Bericht §5.2: „FEHLT als Pill“) rendert die Empfänger
  samt Kurzbeschreibung ins Template.
- *Migration:* additiv, neue Tabelle, kein Umbau bestehender Daten.
- *Export:* Das Delegationsobjekt ist die Quelle für den A2A-Task-Entwurf; die
  Agent-Card (W3-B) verweist auf die möglichen Empfänger nur, wenn O3.3 das
  vorsieht.

### 4.2 W2 = B — deklaratives Feld `run_limits`

**Gewählt:** Ein Feld `run_limits` am Agenten mit vier Werten. Die Laufzeit
liest sie, Prüffälle referenzieren sie. Who2Be setzt sie nicht durch.

| Wert | Bedeutung | Abbildung (Beleg) |
|---|---|---|
| `max_parallel` | höchstens so viele Delegationen gleichzeitig | Claude SDK `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (Default 20); Google-Obergrenze 3–4 |
| `max_depth` | Delegationstiefe; 1 heißt „Empfänger delegiert nicht weiter“ | Claude SDK `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (Default 3) |
| `stall_threshold` | Runden ohne Fortschritt bis Neuplanung bzw. Abbruch | Magentic-One Stall-Zähler (≤ 2) |
| `max_budget_usd` | Kostenobergrenze je Lauf | Claude SDK `max_budget_usd` (Default „No limit.“) |

Jeder Wert ist optional; fehlt er, deklariert Who2Be **keine** Grenze. Einen
Default setzt Who2Be nicht still, weil ein unsichtbarer Default wie eine
Durchsetzung wirken würde. Die Orchestrator-Vorlage (W5) bringt eigene Werte
mit (Bericht §5.2: „max. 4 parallele Aufträge, Tiefe 1 [...], Abbruch nach 3
Runden ohne Fortschritt“).

**Verworfen:**

- **A – nur im Prompt.** Heute möglich, aber nicht maschinenlesbar und nicht
  prüfbar.
- **C – Durchsetzung in Who2Be.** „Widerspricht ‚kein Runtime-Host‘.“
  (Bericht §7).

**Folgen:**

- *Datenmodell:* Ort des Feldes ist offen (O2.1): eigene Spalte am Agenten
  oder Teil von `AgentToolPolicy`. Beides ist additiv.
- *Rechte:* Legt ein Agent einen Agenten an, dürfen dessen `run_limits` nicht
  weiter gehen als die eigenen – analog zu `write_rate_limit` in
  `packages/models/src/who2be_models/tool_policy.py#AgentToolPolicy.is_within`.
- *API/MCP:* Lesen mit dem Agenten, Ausgabe über `get_agent` und im Export.
- *Migration:* additiv, `NULL` bzw. leeres Objekt für Bestandsagenten.
- *Export:* Wert-für-Wert in die Laufzeit-Konfiguration (Claude SDK, Hermes);
  in der A2A-Card als Extension (O3.4).

### 4.3 W3 = B + C — A2A-Agent-Card je Agent und AGENTS.md-Export

**Gewählt:** Zwei Exporte, beide lesend und aus denselben Daten erzeugt.

**B – A2A-Agent-Card.** Eine Card je Agent. Vorläufiges Mapping (Bericht
§4, „Persona-Kurzbeschreibung → `description`, Playbooks → `skills`, Policy →
`securitySchemes`/Capabilities“):

| Card-Feld (A2A §4.4.1) | Quelle in Who2Be |
|---|---|
| `name`, `version` | Agent-Name, Version des aktiven Stands |
| `description` | Kurzbeschreibung der Persona |
| `skills[]` | Playbooks des Agenten – **Abgleich offen**, siehe unten |
| `capabilities` | fest nach Laufzeit bzw. leer; Who2Be hostet keinen Endpunkt |
| `securitySchemes`, `securityRequirements` | offen (O3.4): Who2Be-Policy ist Rechtebeschreibung, kein Auth-Schema |
| `supportedInterfaces`, `defaultInputModes`, `defaultOutputModes` | von der Laufzeit, die den Agenten betreibt; Who2Be füllt Platzhalter oder lässt den Export erst mit Laufzeit-Angabe zu (O3.2) |

**Offener Punkt aus dem Bericht: A2A-`skills` gegen Playbooks.** Der
Bericht hat den Abgleich ausdrücklich nicht gemacht („Deckt das
A2A-`skills`-Schema Playbook-Semantik ab? Das habe ich nicht geprüft.“,
§7; ebenso §8). Belegt ist nur das Schema: AgentSkill hat Pflichtfelder
`id`, `name`, `description`, `tags` und optional `examples`, `inputModes`,
`outputModes`, `securityRequirements` (A2A §4.4.5). Offen ist unter anderem:

- Playbook-`triggers` → `examples`? Trigger sind Stichworte, Examples sind
  „Example prompts or scenarios“.
- Applied gegen Triggered: Ein Applied Playbook ist immer eingebettet und
  eher Verhalten als Fähigkeit – gehört es in `skills` oder nicht?
- Constraint-Libraries und Composites (ADR-0024): ein Skill je Composite, je
  Kind oder gar keiner?
- Persona-`skills` (ADR-0026: deskriptiv, derzeit als „Coming Soon“
  deaktiviert) als mögliche zweite Quelle neben Playbooks – Konflikt mit
  Single Source of Truth?

Der Abgleich ist **Voraussetzung** für den Card-Export und Teil der
Spezifikation (Paket O1).

**C – AGENTS.md-Export.** Ein Markdown-Export für Coding-Agenten. AGENTS.md
kennt „weder Rechte noch Delegation“ (Bericht §7) und hat kein Schema. Der
Export ergibt deshalb nur für Agenten Sinn, die in einem Code-Repository
arbeiten. Er wird **nicht** für jeden Agenten angeboten; die Kriterien
(z. B. Kennzeichnung des Agenten als Coding-Agent oder vorhandene
Coding-Playbooks) legt O3.5 fest. Inhalt: Rolle aus der Persona, Applied
Playbooks als Regeln, Verweise auf Triggered Playbooks, `run_limits` und
Delegationen nur als Hinweistext.

**Verworfen:**

- **A – kein Export.** Widerspricht der Positionierung „Standards statt
  Wahrscheinlichkeit“ (Bericht §7).
- Der Bericht empfahl B allein; der Owner nahm C dazu. Die Einschränkung
  „trifft nur Coding-Agenten“ bleibt als Umfangsgrenze von C bestehen, nicht
  als Grund zum Verwerfen.

**Folgen:**

- *Datenmodell:* keins; beide Exporte sind reine Ableitungen.
- *API:* zwei Lese-Endpunkte je Agent (Card als JSON, AGENTS.md als
  `text/markdown`). Ob die Card zusätzlich unter
  `/.well-known/agent-card.json` erreichbar ist, bleibt offen (O3.2), weil
  Who2Be den Agenten nicht selbst betreibt.
- *MCP:* optional ein Lese-Werkzeug je Export.
- *Migration:* keine.
- *Exportformate:* A2A Agent Card nach der Version, die zum Bau-Zeitpunkt gilt
  (heute Spec 1.0.0 / Release v1.0.1); das normative Schema ist laut Spec
  `spec/a2a.proto`. AGENTS.md als freies Markdown.

### 4.4 W4 = B — neuer `check_kind: tool_trace`

**Gewählt:** Prüffälle erhalten eine vierte Art `tool_trace` neben
`human_rule`, `must_contain` und `must_not_contain`
(`packages/models/src/who2be_models/test_case.py#TestCheckKind`). Die Laufzeit
meldet mit dem Ergebnis die Sequenz der Werkzeugaufrufe; Who2Be prüft sie
deterministisch gegen ein Muster in `check_pattern`. Beispiele aus Bericht
§7: „`delegate` vor `write`“, „kein `approve` durch Ersteller“.

Damit werden die Prüffälle P1–P8 der Orchestrator-Vorlage (Bericht §5.2), die
heute auf `human_rule` angewiesen sind, teilweise maschinell prüfbar –
insbesondere P4 (delegiert statt selbst geschrieben), P5 (keine Delegation vor
Entscheidung), P6 (Prüfauftrag an Dritten) und P8 (kein Merge).

**Verworfen:**

- **A – bei `human_rule` + `human_rating` bleiben.** Trägt, skaliert aber
  nicht und prüft nur, was ein Mensch nachsieht.
- **C – LLM-Richter.** „C ist genau die ‚Wahrscheinlichkeit‘, gegen die sich
  Who2Be positioniert.“ (Bericht §7). Zudem widerspricht er ADR-0044 und
  ADR-0053 (kein LLM in der Bewertung).

**Folgen:**

- *Datenmodell:* Wert `tool_trace` im Enum und im DB-CHECK der Prüffälle; der
  gemeldete Trace wird am Lauf gespeichert (Größengrenze O4.3).
- *API/MCP:* `submit_test_results` (ADR-0053 §6) bekommt ein optionales Feld
  für den Trace; Pflicht, wenn der Prüffall `tool_trace` ist.
- *Attestierung:* Ein Trace über `client_self_report` bleibt eine
  Selbstauskunft der Laufzeit. Das ist besser als Prosa, aber kein
  unabhängiger Beleg. Ob und wie ein Trace signiert oder aus einem Protokoll
  (z. B. OpenTelemetry, das MCP 2026-07-28 statt Logging nennt) übernommen
  wird, bleibt offen (O4.4).
- *Migration:* additiv (Enum-Wert, CHECK erweitern, Spalte am Lauf).

### 4.5 W5 = A — Einzelagent bleibt Default

**Gewählt:** Neue Nutzer bekommen weiterhin einen Einzelagenten mit
Playbooks. Der Orchestrator wird nur als **Vorlage** angeboten (Persona,
Template, Playbooks, Policy, Prüffälle wie Bericht §5.2), nicht als
Standard-Seed.

**Verworfen:** **B – Orchestrator als Standard-Seed neben dem Builder.** Die
Messlage (Google 2512.08296, arXiv 2601.04748, arXiv 2604.02460) spricht
für Multi-Agent nur bei zerlegbaren Aufgaben (Bericht §7).

**Folgen:** Kein neuer Seed, keine Seed-Migration. Die Vorlage wird erst
gebaut, wenn W1, W2 und W4 so weit stehen, dass sie ohne Prompt-Ersatz
auskommt.

## 5. Offene Detailfragen

Diese Fragen entscheidet die ADR nicht. Sie gehen an die Spezifikation
(Paket O1); was Urteil verlangt, wird dem Owner als Option mit Empfehlung
vorgelegt.

**Delegationsobjekt (W1)**

- O1.1 Endgültige Feldliste, Längen- und Formatgrenzen, Pflichtfelder über
  die vier Owner-Felder hinaus.
- O1.2 Versionierung: Agenten selbst tragen heute keine Versionshistorie wie
  Persona, Playbook und Resource. Wird das Delegationsobjekt eigenständig
  versioniert, oder hängt es an der Version des Delegierenden?
- O1.3 Darf `to_agent_id` auf einen deaktivierten Agenten zeigen, und was
  passiert beim Löschen eines Agenten (CASCADE oder Sperre)?
- O1.4 Zyklen (A → B → A) und Selbstdelegation: verbieten, oder nur über
  `max_depth` begrenzen?
- O1.5 Neue Write-Capability (z. B. `delegation_write`) oder Teil von
  `agent_write`? Gilt `is_within`?
- O1.6 Wirkt eine geänderte Delegation sofort, oder erst mit der nächsten vom
  Menschen aktivierten Version (ADR-0040)?
- O1.7 Genaue Abbildung auf A2A-`Part`s (Text- plus Data-Part, Schema des
  Data-Parts), und ob ein eigenes A2A-Extension-URI dafür nötig ist.
- O1.8 Wird Lücke L4 (Eskalationszustand) nur über das Feld `escalation`
  beschrieben, oder braucht sie ein eigenes Modell?

**`run_limits` (W2)**

- O2.1 Ort: eigene Spalte am Agenten oder Teil von `AgentToolPolicy`.
- O2.2 Typen und Grenzen (Ganzzahl ≥ 1 für Parallelität und Tiefe, Dezimal ≥ 0
  für Budget), Einheit von `stall_threshold` (Runden, Minuten).
- O2.3 Abbildung auf Hermes (Kanban-Board) – welche Werte Hermes heute lesen
  kann.

**Export (W3)**

- O3.1 Abgleich A2A-`skills` ↔ Playbooks (Abschnitt 4.3), mit Entscheidung
  über Applied/Triggered, Composites und Persona-`skills`.
- O3.2 Pflichtfelder der Card, die Who2Be nicht kennt
  (`supportedInterfaces`, Modes); `.well-known`-Pfad ja oder nein.
- O3.3 Erscheinen mögliche Empfänger (W1) in der Card, und wenn ja, wie?
- O3.4 `run_limits` und Policy in der Card: A2A-Extension oder weglassen.
  Signatur der Card (`signatures`) ja oder nein.
- O3.5 Kriterium, für welche Agenten der AGENTS.md-Export angeboten wird.

**`tool_trace` (W4)**

- O4.1 Meldeformat eines Trace-Eintrags (Werkzeugname, Zeitpunkt, handelnder
  Agent, Ziel-Element).
- O4.2 Mustersprache: Reihenfolge („X vor Y“), Verbot („kein X“), Bindung an
  Akteur („kein `approve` durch Ersteller“). Bewusst klein halten, keine
  allgemeine Regex über den Trace.
- O4.3 Größengrenze und Aufbewahrung des gespeicherten Trace.
- O4.4 Herkunft und Vertrauen: Selbstmeldung, Signatur oder Übernahme aus
  OpenTelemetry.

## 6. Konsequenzen

**Positiv**

- Who2Be beschreibt Delegation, Budget und Abnahme eines Orchestrators
  feldgenau statt als Prompt-Text und schließt die Lücken L1–L3 als
  Beschreibungs- und Prüflücken.
- Die Nähe zu A2A macht einen Who2Be-Agenten mit einem Standard austauschbar,
  statt mit einem Who2Be-eigenen Format.
- Handlungen werden deterministisch prüfbar, ohne LLM in der Bewertung.
- Neue Nutzer bekommen weiter den gemessen günstigeren Einzelagenten.

**Negativ / Risiken**

- W1-C ist der größte Aufwand der drei Optionen. Solange keine Laufzeit A2A
  spricht, ist das Delegationsobjekt eine Vorlage, die niemand
  maschinell ausführt (der Einwand des Berichts gegen C).
- Deklarierte `run_limits` wirken nur, wenn die Laufzeit sie liest. Eine
  Laufzeit, die sie ignoriert, fällt erst im Prüffall auf.
- Ein `tool_trace` per `client_self_report` meldet die geprüfte Laufzeit
  selbst. Das senkt, aber beseitigt nicht das Problem „Handoff ist
  Behauptung“ (Bericht §6).
- Die A2A-Spec ist jung (1.0.0 vom März 2026). Ein Versionssprung kann den
  Card-Export nachziehen lassen.
- Der Card-Export hängt am offenen Abgleich `skills` ↔ Playbooks (O3.1).

**Neutral**

- Keine bestehende ADR wird abgelöst. ADR-0053 wird durch W4 um einen
  `check_kind` ergänzt; die Ergänzung wird beim Bau in ADR-0053 vermerkt.

## 7. Umsetzungsreihenfolge (Vorschlag, nach dem Cloud-Test)

Die Umsetzung beginnt **erst nach dem abgeschlossenen Cloud-Test** und nach
Freigabe durch den Owner. Den endgültigen Paketschnitt legt der PM danach
fest; die folgende Reihenfolge ist ein Vorschlag. Jedes Paket bleibt bei
höchstens acht Dateien, sonst wird es geteilt.

| # | Paket | Abhängig von | Art |
|---|---|---|---|
| O1 | Spezifikation: Felder Delegationsobjekt, `run_limits`, Trace-Format und Mustersprache, Card-Mapping inkl. Abgleich `skills` ↔ Playbooks, AGENTS.md-Kriterium, Kollisionsmatrix | ADR-0054 auf main | Recherche/Doku, kein Code |
| O2 | `run_limits`: Modell, Migration, Validierung inkl. `is_within`, Ausgabe über API und `get_agent` | O1 | Code |
| O3 | `tool_trace`: Enum, DB-CHECK, Trace-Feld an `submit_test_results`, deterministischer Musterprüfer mit Rot-Probe | O1 | Code |
| O4 | Delegationsobjekt: Modell, Migration mit RLS, Repository, API | O1 | Code |
| O5 | Delegationsobjekt: MCP-Werkzeuge, Pill `{{agents-catalog}}`, Web-Oberfläche (i18n de+en) | O4 | Code, ggf. zwei PRs |
| O6 | A2A-Agent-Card-Export | O1 (Abgleich), O2, O4 | Code |
| O7 | AGENTS.md-Export | O1 | Code |
| O8 | Orchestrator-Vorlage (W5): Persona, Template, Playbooks, Policy, Prüffälle P1–P8 mit `tool_trace` wo möglich | O2–O5 | Inhalt/Seed-frei |

O2, O3 und O7 können nach O1 parallel laufen, wenn die Kollisionsmatrix aus
O1 keine gemeinsamen Dateien zeigt. O6 wartet auf den Abgleich aus O1.
