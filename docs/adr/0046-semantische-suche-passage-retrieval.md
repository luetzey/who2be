# ADR-0046 — Semantische Suche & Passage-Retrieval (pgvector, Stufe B)

- Status: Accepted (Welle 1 in Umsetzung)
- Datum: 2026-07-25
- Kontext: Loest die als „Stufe B" offen gelassenen Folge-Entscheidungen aus
  ADR-0037 (Search) und ADR-0044 (Agent-Memory) ein — beide verweisen
  ausdruecklich auf einen Folge-ADR.
- Bezug: ADR-0037 (Discovery/Search, Stufe A), ADR-0042 (Tool-Sichtbarkeits-
  SSoT), ADR-0044 (Agent-Memory), ADR-0045 („Ein Element, eine Sprache"),
  ADR-0028/0029 (Editionen/Build-Isolation), ADR-0003 (asyncpg)

## Kontext

Drei Beduerfnisse treffen auf dieselbe fehlende Faehigkeit:

1. **Builder-Discovery** — beim Kuratieren die passenden Playbooks/Resources
   finden, die verknuepft werden sollen.
2. **Agent-Runtime-Retrieval** — ein Agent soll seine zugewiesenen Playbooks und
   Resources durchsuchen, statt alles im System-Prompt zu tragen, und relevante
   Inhalte finden, **ohne** dass ein Trigger exakt greift.
3. **Agent-Memory** — dieselbe Semantik fuer das kuratierte Langzeitgedaechtnis,
   sofern `memory_mode` es freischaltet.

Der Ist-Zustand traegt das nicht:

- **Stufe A ist schwaecher gebaut als ADR-0037 beschreibt.** Die Suche indexiert
  `ev.content::text` — die rohe jsonb-Serialisierung inkl. Schluesselnamen
  (`"type"`, `"styles"`, Block-IDs). Die in ADR-0037 §53-54 zugesagten
  `tsvector`-Generated-Columns + GIN-Indizes wurden **nie angelegt**; Volltext
  wird pro Query zur Laufzeit ueber den ganzen Content gerechnet. `snippet` ist
  nicht der Treffer-Kontext, sondern statisch `content->>'description'`.
- **Der Read-Scope wird hinter dem `LIMIT` angewandt**, entgegen ADR-0037 §47
  („serverseitig **vor** dem Ranking"). Ein `assigned`-Agent, dessen Top-k global
  ausserhalb seines Sets liegt, bekommt `[]`, obwohl passende zugewiesene
  Treffer dahinter laegen. Das ist ein Korrektheitsfehler, der sich mit
  Top-k-Semantik verschaerft.
- **Es gibt keine Chunk-Ebene.** Entity-Ranking allein loest Beduerfnis 2 nicht:
  ein Treffer „Playbook XY, Score 0.8" spart keinen Kontext, wenn danach
  `fetch_playbook` ueber den Volltext folgt.
- **Memory verspricht bereits Semantik, die es nicht liefert.** Der
  MCP-Docstring (`search_memory`) beginnt mit „Durchsucht dein
  Langzeitgedaechtnis […] **semantisch**"; implementiert ist FTS(`simple`) +
  `ILIKE` + `pg_trgm`. `pg_trgm` ist zeichenbasiert — Paraphrasen haben
  Similarity nahe null. Das Modell wird auf ein Verhalten konditioniert, das es
  nicht bekommt.

Das tragende sachliche Argument fuer Vektoren betrifft beide Korpora:
**cross-linguales Retrieval**. Seit ADR-0045 ist jedes Element einsprachig, ein
Workspace mischt aber de/en; Memories sind laut Migration 0066 ausdruecklich
„kurz und gemischtsprachig". Eine deutsche Query findet mit Volltext **niemals**
einen englischen Treffer. Das kann bessere FTS strukturell nicht nachbauen.

## Entscheidung

Wir fuehren **Chunk-basiertes Retrieval mit optionaler Vektor-Semantik** ein,
hinter den bestehenden Tool-Vertraegen, in drei Wellen.

### 1. Chunk-Ebene als Fundament (`content_chunk`)

Eine Tabelle `content_chunk` haelt die aktive Version jedes Inhaltselements in
Passagen, geschnitten **entlang der Heading-Bloecke**. Damit ist jeder Treffer
direkt als bestehende `"<uuid>#<block_id>"`-Referenz ausdrueckbar — keine zweite
Ankersprache neben den Block-Refs. Die Chunk-Erzeugung verwendet die vorhandene
Block-Logik wieder (`block_section_text()`, `list_blocks()`), nicht neuen Code.

Das **ersetzt** die in ADR-0037 §53-54 zugesagten, nie angelegten
Per-Tabelle-`tsvector`-Spalten: eine Text-Ebene statt vier, und sie traegt
sowohl den Volltext- als auch spaeter den Vektor-Index.

Chunks sind **abgeleitet und jederzeit regenerierbar** — sie werden bei
`transition → active` neu gebaut. Kein Verlust bei Neuaufbau, kein
Migrationsrisiko.

### 2. Zwei Vektor-Heimaten, eine Infrastruktur

Memory wandert **nicht** in `content_chunk`. Die beiden Korpora unterscheiden
sich in jeder relevanten Achse:

| | `content_chunk` | `agent_memory` |
|---|---|---|
| Herkunft | abgeleitet, regenerierbar | zur Laufzeit geschrieben |
| Bindung | Workspace + Version | Workspace + Agent |
| Lebenszyklus | folgt der Version | `pending`/`active`/`rejected` |
| Vertrauensgrad | kuratiert, versioniert | selbstformuliert, unbestaetigt |

Geteilt werden **`EmbeddingPort`, Vektordimension und Rang-Fusion** — nicht die
Tabelle. `agent_memory` bekommt eine eigene `content_vector`-Spalte; bei
`fact` ≤ 300 Zeichen ist das ein Vektor pro Zeile, ohne Chunking.

Der Spaltenname ist bewusst `content_vector`: `embedding_mode` (Migrationen
0040/0041) bezeichnet bereits die *Einbettung ins Prompt* (`lazy`/`inline`) und
darf nicht kollidieren.

### 3. Embeddings lokal, optional, best-effort

- **`EmbeddingPort`** nach dem Vorbild von `build_entitlement_port()`, mit einem
  **lokalen** Default-Adapter (multilinguales Modell, 384 Dimensionen), geladen
  als **optionale Dependency-Gruppe** (`--group embeddings`) analog zur
  Billing-Isolation (ADR-0029). Fehlt die Gruppe, bleibt `content_vector` NULL
  und beide Suchen laufen im Textmodus weiter.
- **Kein externer Provider.** `.env.example` sagt fuer On-Prem ausdruecklich
  „KEIN Phone-Home". Ein Embedding-Call schickte kuratierten Kundeninhalt **und
  persoenliche Memories** aus dem selbstgehosteten Deployment und schuefe einen
  neuen Subprozessor im VVT. Bei Memory ist das nicht verhandelbar.
- **Best-effort im Schreibpfad.** Der Vektor wird synchron versucht, aber ein
  Fehlschlag laesst die Spalte NULL und blockiert das Speichern **nie**. Ein
  CLI-Backfill holt nach. Das gilt verschaerft fuer `save_memory`: das ist ein
  rate-limitierter Laufzeit-Call des Agenten, kein Builder-Vorgang.
- **Kein ANN-Index in v1.** Beide Korpora sind klein (Groessenordnung 10^3
  Chunks pro Workspace; ≤ 500 Memories pro Agent, hart gecappt). Brute-Force
  innerhalb des Workspace- bzw. `(workspace_id, agent_id)`-Prefix ist schneller
  als ein IVFFlat/HNSW-Aufbau sich rentiert. Bewusste Entscheidung, kein
  Versaeumnis — HNSW kommt, wenn Messwerte es fordern.

### 4. Tool-Vertraege

- `search` behaelt seine Form und bekommt `mode: "text" | "semantic" | "hybrid"`
  mit Default `auto` (hybrid wenn Vektoren vorliegen, sonst text) — genau der in
  ADR-0037 §35-38 zugesagte, abwaertskompatible Schalter.
- **Neu `search_content`** liefert *Passagen* statt Entitaeten. Das ist der
  Vertrag, der Beduerfnis 2 tatsaechlich bedient. Neues Tool ⇒ Mapping-Eintrag
  in `who2be_models.tool_requirements` (ADR-0042), sonst unsichtbar in
  `tools/list`.
- `search_memory` behaelt seine Signatur; die Rangberechnung wird intern von der
  heutigen lexikografischen `ORDER BY`-Kaskade (`ts_rank` → `similarity` →
  `importance`) auf eine **Score-Fusion** umgebaut. Das ist kein Drop-in,
  sondern der eigentliche Aufwand von Welle 3.
- **Keine Zusammenlegung von Content- und Memory-Suche.** Kuratierte,
  versionierte Inhalte und selbstgeschriebene, unbestaetigte Notizen haben
  unterschiedliche Vertrauensgrade und unterschiedliche Gates. Die Provenienz
  eines Treffers muss fuer das Modell ablesbar bleiben.

## Rechte & Sichtbarkeit

- **Read-Scope wird vor dem Ranking angewandt** — die sichtbaren IDs gehen als
  Praedikat in die Query (`AND entity_id = ANY(...)`), nicht als Nachfilter.
  Damit erfuellt die Implementierung erstmals ADR-0037 §47.
- **Nur `status='active'`** ist auffindbar (Content wie Memory) — unveraendert.
- **Memory-Gating faellt automatisch an**: `search_memory` verlangt bereits
  `memory_mode ≥ read_only`, `save_memory` ≥ `suggest`. Semantik erbt das Gate;
  es braucht **kein neues**.
- **RLS** auf `content_chunk` strikt auf `app.current_tenant`, nach dem Muster
  aus Migration 0066 (inkl. `pg_roles`-Guard fuer On-Prem/Dev ohne
  `who2be_app`).
- **Prompt-Injection:** Retrieval zieht Text in den Agenten-Kontext. Fuer Memory
  existiert der Waechter (`MemoryGuardConfig`, admin-gated). Fuer
  Content-Passagen gilt zunaechst, dass sie aus kuratierten, freigegebenen
  Versionen stammen — die Freigabe *ist* die Kontrolle. Ein eigener
  Content-Waechter bleibt offen (siehe Ausblick).

## Verhaeltnis zu Triggern

Trigger bleiben die **verbindliche** Zuordnung („dieses Playbook musst du
anwenden"). Retrieval ist **additiv**: bei Trigger-Miss sucht der Agent, statt
frei zu arbeiten. Semantik ersetzt Trigger ausdruecklich nicht — sonst ginge
genau die Verlaesslichkeit verloren, die eine kuratierte AgentDB ausmacht.

## Konsequenzen

- Migrationen: `content_chunk` (+ RLS/Grants/GIN), pgvector-Extension mit
  **dynamischer Schema-Aufloesung** (Muster aus 0066: lokal `public`, Supabase
  `extensions`, Test-Schemata eigenes — ohne das bricht es in genau einer
  Umgebung), `content_vector` auf `content_chunk` und auf `agent_memory`.
- **Infra-Wechsel**: lokal/CI/Testcontainers laufen auf `postgres:16`, das
  `vector` **nicht** mitbringt → `pgvector/pgvector:pg16`. Prod
  (`supabase/postgres`) bringt es mit.
- Neue Module: `content_chunk_service`/`-repository`, `embeddings/` (Port +
  Adapter), Backfill-CLI analog `who2be-migrate`.
- Erste ausgehende Modell-Inferenz des Produkts — bisher enthaelt der Kern
  **null** KI-Calls. Lokal ausgefuehrt, optional installierbar; das ist der
  Grund fuer die Port-/Dep-Gruppen-Isolation statt eines direkten Imports.
- `apps/api/tests/contract/openapi_surface.json` bricht bei neuen Routen und bei
  Erweiterungen von `SearchHit`/`MemoryHit` — bewusst regenerieren.
- `SearchService` bekommt seine ersten Unit-Tests; `memory_repository.
  search_active` bekommt Regressionstests **vor** dem Fusions-Umbau.

## Bewusst nicht entschieden / Ausblick

- **Persona-Injektion bleibt `importance`-basiert.** `persona_service` haengt die
  Top-5-Memories an den gerenderten Body — dort existiert **keine Query**, also
  gibt es nichts semantisch zu ranken. Query-lose Relevanz waere Vortaeuschung.
- **Content-Injection-Waechter** analog `MemoryGuardConfig` — offen, bis
  Erfahrung mit retrievtem Passagen-Text vorliegt.
- **ANN-Index (HNSW)** — erst wenn Messwerte ihn rechtfertigen.
- **Cloud-Embedding-Adapter** — der Port laesst ihn zu; die Entscheidung, ob die
  Cloud-Edition einen nutzt, ist bewusst nicht Teil dieses ADR.
