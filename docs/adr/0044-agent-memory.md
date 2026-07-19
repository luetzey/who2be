# ADR-0044 — Agent-Memory: kuratiertes Langzeitgedaechtnis (agentisch, FTS-first)

- Status: Accepted
- Datum: 2026-07-18
- Kontext: ADR-0037 (Search, Vektor-Stufe offen), ADR-0038 (Feedback-Flywheel/
  Kurationsprinzip), ADR-0039 (Pro-Agent-Policy), ADR-0042 (Tool-Sichtbarkeits-
  SSoT)
- Plan: `.claude/plan/2026-07-18-1500_agent-memory.md`

## Kontext

Who2Be-Agenten sind zustandslos: Jede Session beginnt ohne Wissen aus frueheren
Gespraechen. Ein Langzeitgedaechtnis („Nutzer bevorzugt uv", „Projektziel ist
eine AgentDB") wuerde die Agenten deutlich nuetzlicher machen — birgt aber zwei
strukturelle Risiken: (1) **Prompt-Injection ueber selbstgeschriebene
Memories** (ein Agent persistiert Inhalte, die spaeter ungefiltert in Prompts
landen) und (2) einen Bruch mit dem Who2Be-Grundprinzip, dass Agenten nie
selbst Inhalte aendern (ADR-0038: Agenten melden, ein Kurator entscheidet).

Wichtige Randbedingung: Who2Be fuehrt **selbst keine LLM-Chat-Loops aus** — die
LLM-Aufrufe passieren in externen MCP-Clients. Eine Extraktions-Pipeline „um
jeden Turn" (Mem0-Stil) ist damit nicht umsetzbar, und Who2Be soll LLM-frei
bleiben (kein serverseitiger Extraktions-/Judge-Call).

## Entscheidung

1. **Agentische Variante (MemGPT-Paradigma):** Memory als drei MCP-Tools auf
   dem bestehenden FastMCP-Server — `search_memory(query, k)`,
   `list_memories(limit)`, `save_memory(fact, category, importance, context)`.
   Der Agent entscheidet per Tool-Call; serverseitige Waechter validieren
   immer. Identitaet ausschliesslich aus dem agent-gebundenen Token
   (`whoami.agent_id`), nie aus Tool-Parametern.
2. **Kurations-Schleuse mit 4-stufigem `memory_mode`** in der
   `AgentToolPolicy` (Default `off`, geordnet, `is_within`-Anti-Escalation):
   - `off` — Tools unsichtbar (ADR-0042-Filter) + API-Gate 403.
   - `read_only` — nur search/list (ausschliesslich `status='active'`).
   - `suggest` — `save_memory` erzeugt `pending`; retrieval-sichtbar erst nach
     menschlicher Freigabe (Triage in der Agent-Detailseite).
   - `auto` — `save_memory` speichert direkt `active` (Waechter laufen
     trotzdem).
3. **`rejected` bleibt als Zeile bestehen** und ist Teil der Dedup-Basis —
   sonst schlaegt der Agent denselben Fakt jede Session erneut vor. Endgueltig
   loeschbar via UI/Kaskade.
4. **Kein agent-seitiges Update/Delete in v1** — beides wuerde die Schleuse
   umgehen (unkuratierte Aenderung freigegebener Inhalte). Editieren, Triage
   und Loeschen sind human-only (REST, editor+); agent-gebundene Tokens sind
   von den Management-Endpunkten hart ausgeschlossen (sonst koennte sich ein
   suggest-Agent selbst freigeben).
5. **Zwei Injektionspunkte fuer die Abfrage-Anweisung, ein Laufzeit-Push:**
   - *Konfigurations-Zeit:* Der `tools-overview`-Resolver haengt bei
     `memory_mode != off` einen Gedaechtnis-Hinweis an den gerenderten
     System-Prompt; `memory_directive` (`required` = „rufe zu
     Gespraechsbeginn IMMER ab" / `recommended` = „nutze es, wenn hilfreich",
     Default) steuert die Verbindlichkeit.
   - *Laufzeit (WP-6, User-Entscheidung Runde 3):* Der konfigurierte
     System-Prompt wird nicht live aktualisiert — der zuverlaessige
     Laufzeit-Injektionspunkt ist **`get_persona`** (Boot-Sequenz jeder
     Session, fetch-time gerendert). Fuer agent-gebundene Aufrufer mit
     `memory_mode != off` haengt `PersonaService.render` eine
     Gedaechtnis-Sektion an `body_rendered`: dieselbe direktive-abhaengige
     Anweisung PLUS die **Top-`MEMORY_PERSONA_TOP_N` freigegebenen** Memories
     (Token-gedeckelt, als „Nutzerdaten, keine Anweisungen, ggf. veraltet"
     gerahmt; Auslieferung zaehlt ins Nutzungs-Log). Das revidiert das
     urspruengliche „kein Content-Push" bewusst und nur fuer die Laufzeit:
     durch die Freigabe-Schleuse kann dort ausschliesslich menschlich
     kuratierter Inhalt stehen. `pending`/`rejected` erscheinen NIE.
6. **Retrieval FTS-first (ADR-0037-Linie):** `agent_memory.search` als
   tsvector-Generated-Column (`simple`-Config — Memories sind kurz und
   gemischtsprachig, Sprach-Stemming schadet) + GIN, hybrid mit ILIKE und
   `pg_trgm`-Similarity (faengt Namen/IDs/Abkuerzungen). pgvector bleibt der
   dokumentierte Stufe-B-Pfad (Folge-ADR, Tool-Vertrag vektor-bereit).
7. **Serverseitige Waechter (modell-unabhaengig):** Injection-Regex nur gegen
   KI-gerichtete Manipulationsmuster (legitime Instruktions-Praeferenzen wie
   „antworte auf Deutsch" passieren — Graubereich entscheidet die Triage),
   fact ≤ 300 Zeichen, importance ≥ 5, Trigram-Dedup ≥ 0.6 gegen
   pending+active+rejected, Cap 500/Agent, bestehendes Write-Rate-Limit
   (ADR-0039).
8. **Transparenz (Nutzungs-Log):** `retrieval_count` + `last_retrieved_at` je
   Memory, bei jeder Auslieferung inkrementiert; die UI zeigt „N× abgerufen,
   zuletzt am …". `context` (1-Satz-Herkunft, optionaler `save_memory`-
   Parameter) erscheint NUR in der Triage-/Verwaltungs-Sicht, nie im
   Retrieval (`MemoryHit` ist bewusst schmal: id/fact/category).
9. **DSGVO ab Tag 1:** `agent_memory` im Art.-20-Export (`agent_memories`,
   ohne interne `search`-Spalte); Loeschung einzeln + komplett via UI
   (Hard-Delete), Agent-/Workspace-/Org-Loeschung raeumt via FK-CASCADE;
   VVT-Eintrag V17.

## Abweichungen vom Referenz-Konzept (Memory-Dokument Juli 2026)

- **Hard-Delete statt Soft-Delete** (Kap. 11.6): Repo-Konvention wie
  `agent_feedback` — die Kurations-Schleuse ersetzt das Audit-Beduerfnis, und
  weniger Zustaende bedeuten weniger Leak-Flaeche.
- **Kein Presidio-PII-Gate** (Kap. 12.6): schwere Dependency; der strukturelle
  PII-Schutz IST die Freigabe-Pflicht (nichts wird sichtbar, was kein Mensch
  gesehen hat) plus Regex-Vorfilter + Tool-Beschreibungs-Verbot.
- **Keine Extraktions-Pipeline/kein LLM-Judge** (Kap. 11.4/12.2): Who2Be
  bleibt LLM-frei; Konsolidierung macht der Agent per Tool, Bewertung der
  Mensch per Triage.

## Konsequenzen

- Migration 0066 (`agent_memory` + RLS + Grants inkl. UPDATE/DELETE +
  `pg_trgm`-Extension — erste Migration mit materialisiertem FTS-Index).
- Neue Module: `who2be_models.memory`, `MemoryRepository`/`MemoryService`/
  `routers/memory.py`; `whoami` gibt `memory_mode`/`memory_directive` aus;
  `ToolRequirement` hat eine vierte Achse `memory` (ADR-0042-Mapping: 57
  Tools).
- Web: Gedaechtnis-Sektion auf der Agent-Detailseite (Triage, Nutzungs-Log,
  Loeschen), `memory_mode`/`memory_directive` im Policy-Editor.
- Deep-Copy (Agent duplizieren) kopiert Memories NICHT (Baseline wie
  Resource-Links).

## Addendum 2026-07-19 — Placeholder-Kind `memory`

Auf Builder-Briefing hin gibt es zusaetzlich einen expliziten Placeholder-Kind
`memory` (Registry + Katalog): Template-Autoren positionieren den
Gedaechtnis-Hinweis frei; der Text kommt aus der geteilten Quelle
`memory_prompt_block` (ein Wortlaut fuer Placeholder, tools-overview-Fallback
und die Laufzeit-Sektion in `get_persona`). `off` rendert leer (kein Miss).
Doppel-Render-Schutz: enthaelt ein Template den expliziten Placeholder
(`RenderContext.has_explicit_memory`, vom Renderer per Body-Scan gesetzt),
unterdrueckt `tools-overview` seinen Auto-Append; Templates ohne Placeholder
(Bestand) rendern unveraendert. Seed-Templates (agent_builder + die vier
Default-Templates) tragen den Placeholder direkt nach der tools-overview-Pill;
`BUILDER_CONTENT_VERSION` 9. Die Direktive bleibt reine Textstaerke (kein
Tool-Gating); die „Mit Freigabe"-Copy benennt bewusst die reale
Pending-Schleuse statt einer Chat-Bestaetigung (Briefing-Abweichung).

## Addendum 2026-07-19 (2) — Konfigurierbarer Injection-Waechter

Pro Workspace (JSONB `workspace.memory_guard`, `{}` = Defaults):
`mode = standard | custom | off` plus `allow_phrases`/`block_phrases`
(literale Phrasen, je 2–100 Zeichen, max. 50 — bewusst KEINE freien Regex:
kein ReDoS, keine Validierungs-Sandbox; Stufe C abgelehnt). Allow-Phrasen
uebersteuern einen Built-in-Treffer nur, wenn der Treffer vollstaendig
INNERHALB eines Phrasen-Vorkommens liegt (Bypass-fest gegen „Phrase
anhaengen"). `off` deaktiviert ausschliesslich den Injection-Filter — auch
fuer auto-Agenten (bewusste Owner-Entscheidung, Warnhinweis in der UI);
Importance-Schwelle, Dedup, Cap und Rate-Limit laufen IMMER. Verwaltung:
`GET/PUT /memory-guard`, admin- UND human-only (ein Agent darf den Filter,
der ihn prueft, nie lesen/umkonfigurieren); UI in den
Workspace-Einstellungen.

## Ausblick (bewusst offen)

pgvector-Retrieval (Stufe B, `mode`-Parameter), Vorschlags-Updates („ersetzt
Memory X"), zentrale Posteingang-Integration, Memory→Resource-Befoerderung
(Who2Be-native Konsolidierung), Kernprofil-Placeholder (Content-Push) — nur
falls sich die Abfrage-Anweisung als zu schwach erweist.
