# Phase-3 Runde 3 — Persona-Save-Bug, Auto-Save+Git-Status-UX, Agent-Konzept

Status: Draft — Review erbeten, **insbesondere fuer die offenen Architektur-
Fragen** in §"Hinterfragt & entschieden" und §"Offen — bitte bestaetigen".
Diese Runde ist groesser als die letzten, weil ein neues Domain-Konzept
(Agent + SystemPromptTemplate) dazukommt.

## Outcome

1. **Bugfix**: Persona-Profil und System-Prompt werden nach Save + Reload
   wieder korrekt angezeigt.
2. **Editor-Flow wie Git**: Draft-Versionen sind dauerhaft editierbar
   (Auto-Save), "Abschliessen" reicht den Draft als Version ein (→ Review
   bzw. Active je nach Setup), Status-Visualisierung wird klar und ruhig —
   einheitlich fuer Persona, Playbook, Resource.
3. **Neues Domain-Konzept**: Agent ist die Top-Level-Konfiguration; er
   verweist auf genau eine Persona (1:1) und einen SystemPromptTemplate
   (1:1 — Template ist wiederverwendbar). Templates haben Placeholders,
   die beim Klick auf "Kopieren" mit Persona-/Playbook-/Resource-Inhalten
   befuellt werden — ein Block, fertig zum Einfuegen in einen externen
   LLM-Chat.

## Out of scope

- **Aktor-LLM-Anbindung** (also tatsaechliches Ausfuehren der Prompts gegen
  ein LLM) — wir bleiben beim Copy-Output, kein eigener Inference-Layer.
- **Real-time-Collaboration / Operational Transform** — Auto-Save ist
  pro User, kein gleichzeitiges Mehr-User-Editieren.
- **Agent-Versioning** — Agent ist Konfig-Datensatz ohne Versionshistorie
  (kann spaeter nachgezogen werden).
- **Template-Inline-Bearbeitung im Agent** — Templates sind in der Agent-
  Detail-Ansicht read-only, Bearbeitung ausschliesslich in `/templates`.
- Migration bestehender Personae in das neue Agent-Modell. Konzepte leben
  parallel; Bestand bleibt unangetastet.

---

## Track 1 — Persona-Editor-Hydration-Bug (Quick-Win)

### Ursache (verifiziert)

`apps/web/src/features/personas/components/PersonaEditorForm.tsx:107` und
:218 instantiieren `ResourceEditor` bzw. `SystemPromptEditor` ohne
`key`-Prop. BlockNote's `useCreateBlockNote({ initialContent })`
initialisiert den ProseMirror-State **nur beim ersten Mount**; nach
Save → `reload()` → neuer `persona`-Wert → `form.reset(...)` wechselt
zwar `field.value`, aber der Editor bleibt auf dem alten internen
State. Folge: Profil + System-Prompt sehen leer aus (bzw. zeigen den
ersten Zustand vor der allerersten Aenderung). `ResourceDetailPage.tsx:127`
macht es korrekt: `key={`${resource.id}-${resource.current_version}`}`.

### Aenderungen

1. **`PersonaEditorForm.tsx`** — beide BlockNote-Wrapper bekommen einen
   `key` aus `persona.id + current_version`. Da die Form-Komponente das
   `persona`-Objekt nicht selbst kennt, kommt der Key entweder
   - via neuer Prop `formKey: string` rein, die `PersonaDetailPage`
     setzt (z. B. `${persona.id}-${persona.current_version}`), oder
   - aus dem Form-State (`form.getValues('profileBlocks').length`-Hash
     ist eine schlechte Idee — ein Key, der vom Inhalt abhaengt, springt
     bei jedem Tipper).
   Empfohlen: **explizite `formKey`-Prop** — kein magischer Default,
   sondern eine bewusste Render-Identitaet. Identische Loesung fuer
   `PlaybookEditorForm`, falls dort dasselbe Pattern existiert (Pruefen!).
2. **Test-Add**: `PersonaEditorForm.test.tsx` simuliert Save → `formKey`
   wechselt → der initiale BlockNote-Content im Editor entspricht den
   neuen `profileBlocks`. Mock `BlockNoteEditor` einfach durch ein
   `<div data-testid="bn">{JSON.stringify(initialBlocks)}</div>`, damit
   wir den Key-Effekt messen koennen ohne echten ProseMirror.

### Risiko

Niedrig. Eine Prop, ein Test. Konflikt mit Track 2 in derselben Datei —
Track 1 mergt zuerst.

---

## Track 2 — Auto-Save Draft + Git-Style Status-Flow

### Mental-Modell (Git-Analogie)

| Git | Who2Be |
|---|---|
| Active branch | aktive Version (`active`) |
| Working tree (uncommitted) | Draft-Version (`draft`) — auto-saved |
| `git commit` | "Draft abschliessen" → Status bleibt `draft`, aber Timestamp `submitted_at` wird gesetzt; oder direkt → `review`, je nach Setup |
| Pull-Request open | `review` |
| `git merge` | "Veroeffentlichen" → `active`; vorherige Active wird → `inactive` |
| `git stash drop` | "Draft verwerfen" → `draft` row deleted, current_version zurueck auf active |

**Wichtig**: Es gibt zu jedem Zeitpunkt **hoechstens einen Draft pro
Entity** (existierende Backend-Regel `_RACE_DRAFT_EXISTS`, Migration
0011). Auto-Save schreibt **in dieselbe Draft-Row**, keine neue Version
pro Keystroke.

### Was sich aendert

1. **Backend: Neuer Endpoint** `PATCH /v1/workspaces/{ws}/personas/{id}/draft`
   (analog Playbook + Resource). Body: `{ name?, content }`. Verhalten:
   - Wenn Draft existiert: aktualisiert die Draft-Row in-place, KEIN
     Version-Increment.
   - Wenn kein Draft existiert: erstellt ihn (current_version + 1, status='draft'),
     **ohne** den aktiven Stand zu beruehren — Active bleibt v(n), Draft
     ist v(n+1).
   - Optimistic Concurrency: `If-Match`-Header oder `version` im Body
     (Empfehlung Phase 1: weglassen — single-user-Schreiben pro Draft
     ist akzeptable Vereinfachung; in Phase 2 nachruesten, sobald
     Multi-User-Konflikte real werden).
2. **Backend: Behalte** `PUT /v1/.../personas/{id}` als "Update + Submit
   for Review" — semantisch jetzt: "Draft als fertig markieren, Status
   nach `review` schieben". Body bleibt gleich.
3. **Backend: Status-Transitions** bleiben unveraendert
   (`/versions/{version}/transition`).
4. **Frontend: `usePersonaForm` / `usePlaybookForm` / `useResourceForm`**:
   - Kein `onSubmit` mit "Neue Version speichern" mehr.
   - Stattdessen: `useEffect` lauscht auf `form.watch(...)`, debounced
     (`1500ms` nach letztem Keystroke + Flush bei `beforeunload`/`blur`),
     ruft `api.patchPersonaDraft(...)`.
   - Status-Indikator-State: `{ kind: 'idle' | 'saving' | 'saved' | 'error', at?: Date }`.
   - Optimistic UI: Form-Werte sind die SoT, Server-Antwort updated
     `current_version` (siehe unten).
5. **Frontend: `PersonaDetailPage` / `PlaybookDetailPage` / `ResourceDetailPage`**:
   - Header zeigt: `"<Name>" · Active: v3 · Du arbeitest auf Draft v4 · ⏺ saved (vor 4s)`.
   - Eine `BranchStatus`-Komponente neben dem Editor:
     - **Branch-Indikator**: kleines Diagramm `v3 (active) ──── v4 (draft, du)`.
     - **Actions**: `[Draft abschliessen]` (→ Submit for Review) und `[Draft verwerfen]`.
     - Wenn Status = Review: `[Veroeffentlichen]` (Admin/Editor) + `[Zurueck zu Draft]`.
     - Wenn Status = Active: `[Neuer Draft]` (clone von active in eine
       fresh draft) — semantisch wie `git checkout -b feature/X`.
   - Die alte `StatusActionBar` wird durch diese `BranchStatus`-Komponente
     abgeloest. Gleicher A11y-Vertrag, ruhigere Optik.
6. **Frontend: Auto-Save-Indikator**:
   - Live-Region `aria-live="polite"` mit "Speichert …" / "Gespeichert"
     / "Konnte nicht speichern — Retry" (siehe design-language §11).
   - Bei `error`: subtiler Toast + Retry-Button im Header (kein modaler
     Block, sonst Workflow-Bruch).

### UX-Detail "Editor-Inhalt nach Aktiv-Branchen-Wechsel"

Wenn Active = v3, Draft = v4 (du), und der User klickt "Draft verwerfen":
Draft-Row weg, `current_version` zurueck auf v3 (active), Form muss neu
geladen werden. `formKey` aus Track 1 macht das jetzt sauber.

### Backend-Migrationen

- Keine neuen Spalten noetig. Die Draft-Update-Logik ist in
  `repositories/persona_repository.update` schon angedeutet
  (`existing_draft`-Check, status-Fork). Wir nutzen sie.
- Eine kleine **Konvention** im Service: `update_draft` (PATCH) vs.
  `submit_for_review` (PUT) — getrennte Service-Methoden, der Router
  routet entsprechend.

### Tests

- Pytest: Repository-Tests pro Entity fuer PATCH-Verhalten (Draft
  upsert; kein Touch von Active; 409 wenn kein Draft existiert *und*
  current=`inactive` — Fall pruefen).
- Vitest: `BranchStatus.test.tsx`, `useAutoSave.test.tsx` (debounce,
  optimistic update, error-Retry), DetailPage-Integration.
- Manueller Smoke pro Entity: tippen → 1.5s warten → "Gespeichert"-Toast;
  Tab schliessen → Re-open → Draft ist da; "Abschliessen" → Status =
  review; "Veroeffentlichen" → Active wechselt, alte Active wird
  inactive.

### Risiko

Mittel-hoch. Vier Editor-Seiten, drei Repos, neue Frontend-State-Machine.
Pflichtspeck: Debounce darf bei `unmount` nicht verloren gehen — beim
Wegnavigieren in noch ungespeicherten State pending PATCHes flushen.

---

## Track 3 — Agent + SystemPromptTemplate-Hierarchie

### Domain-Modell

```
┌──────────────┐ 1     1 ┌──────────────────────┐
│    Agent     ├─────────│ SystemPromptTemplate │
│              │         │  (mit Placeholdern)  │
│  status      │         └──────────────────────┘
│  name        │
│  description │ 1     1 ┌──────────┐ n m ┌──────────┐
│              ├─────────│ Persona  ├─────│ Playbook │
└──────────────┘         └──────────┘     └──────────┘
                                              │ n m
                                              ▼
                                          ┌──────────┐
                                          │ Resource │
                                          └──────────┘
```

- `Agent` ist workspace-scoped, hat `persona_id` (FK NOT NULL) und
  `system_prompt_template_id` (FK NOT NULL). Status `enabled|disabled`.
  Keine Versionshistorie.
- `SystemPromptTemplate` ist workspace-scoped, hat `name`, `description`,
  `content` (Text mit Placeholders). Versioniert wie Persona/Playbook/
  Resource (draft/review/active/inactive) — konsistent mit dem Rest.
- Bestehende Persona/Playbook/Resource-Konzepte bleiben unangetastet.
  `persona.system_prompt` bleibt das Persona-eigene Voice-Statement
  (als Placeholder-Wert fuer `{{ persona.system_prompt }}`).

### Placeholder-Syntax (Liquid-Style)

| Placeholder | aufgeloest als |
|---|---|
| `{{ persona.name }}` | Persona-Name |
| `{{ persona.description }}` | Persona-Description |
| `{{ persona.system_prompt }}` | Persona's eigener System-Prompt |
| `{{ persona.profile }}` | Profil-Blocks als Plaintext (`blocksToPlainText`) |
| `{{ persona.tags }}` | Komma-getrennte Tag-Liste |
| `{{ playbooks }}` | Alle verlinkten Playbooks als Block ("### NAME\nDESCRIPTION\nBODY") |
| `{{ resources }}` | Alle ueber Playbook-Block-Refs verknuepften Resource-Snippets, dedupliziert |

Unbekannte Placeholders bleiben als Klartext (kein Fail) und werden im
Copy-Output **markiert** (z. B. `⚠ {{ unknown_field }}`), damit der User
sieht, was nicht aufgeloest wurde.

### Neue Endpoints

```
GET    /v1/workspaces/{ws}/system-prompts                # list
POST   /v1/workspaces/{ws}/system-prompts                # create
GET    /v1/workspaces/{ws}/system-prompts/{id}           # detail
PUT    /v1/workspaces/{ws}/system-prompts/{id}           # update (+ Versions-Logik wie Persona)
PATCH  /v1/workspaces/{ws}/system-prompts/{id}/draft     # auto-save (Track 2 Pattern)
GET    /v1/workspaces/{ws}/system-prompts/{id}/versions  # versions list

GET    /v1/workspaces/{ws}/agents
POST   /v1/workspaces/{ws}/agents
GET    /v1/workspaces/{ws}/agents/{id}
PUT    /v1/workspaces/{ws}/agents/{id}
DELETE /v1/workspaces/{ws}/agents/{id}
GET    /v1/workspaces/{ws}/agents/{id}/render            # liefert den befuellten Prompt
```

`/render` macht die Placeholder-Aufloesung server-side (Single Source of
Truth, identisch fuer UI-Copy und ggf. spaetere MCP-Tools/CLI).

### Frontend-Routen

- `/w/:ws/agents`, `/w/:ws/agents/new`, `/w/:ws/agents/:id`
- `/w/:ws/system-prompts`, `/w/:ws/system-prompts/new`, `/w/:ws/system-prompts/:id`
- Nav: zwei neue Eintraege in `AppShell` (Bot-Icon fuer Agents,
  FileText-Icon fuer System-Prompts).

### Agent-Detail-Page (Hierarchie-Darstellung)

```
┌─────────────────────────────────────────────────┐
│ Coach Carla — Senior Customer-Support-Coach    │
│ [Enabled] [Disable] [Edit]                     │
├─────────────────────────────────────────────────┤
│ ↓ Template: "Support-Agent v1" (Active)        │
│   Placeholder-Coverage: 4/4 aufgeloest         │
│                                                │
│ ↓ Persona: "Coach Carla" (Active)              │
│   2 Playbooks verlinkt:                        │
│     • Reset-Mail beantworten                   │
│     • Eskalations-Workflow                     │
│       └ 3 Resource-Blocks aus "Tone-Guide"     │
│                                                │
│ [📋 Prompt kopieren]                           │
└─────────────────────────────────────────────────┘
```

`Prompt kopieren` ruft `GET /agents/{id}/render`, kopiert ins
Clipboard, Toast `"Prompt in Zwischenablage."`.

### Migrationen

- `0022_system_prompt_template.sql`
- `0022b_system_prompt_template_version.sql`
- `0023_agent.sql`

Schemata analog zum bestehenden Pattern (persona/persona_version,
workspace_id-FK, status-Enum auf der Version, timestamps).

### Permissions (ADR-0023)

- Admin + Editor duerfen Templates und Agents anlegen/aendern/loeschen.
- Viewer sieht nur Listen + Render-Output.

### Tests

- Pytest: Migration-Forward, Repo/Service-CRUD beide Entities,
  Placeholder-Aufloeser (Unit-Tests fuer alle Placeholders + Unknown-Fall),
  Tenant-Isolation, Permission-Matrix.
- Vitest: Agent-Hierarchie-Render, Copy-Button (clipboard-API mocken),
  Template-Editor mit Placeholder-Hint.
- MCP-Tool (optional Phase 2 dieses Tracks): `render_agent_prompt`
  als read-only Tool — *nicht in Slot 1*, eigenes Followup.

### Risiko

Hoch — neues Domain-Konzept, zwei Tabellen, neuer Render-Service, neue
Frontend-Routen. Aber: alle existierenden Konzepte bleiben unangetastet,
und der Render-Endpoint ist ein reiner Read.

---

## Hinterfragt & entschieden (Defaults — sag Bescheid, wenn anders gewuenscht)

| Frage | Entschieden | Begruendung |
|---|---|---|
| Persona behaelt `system_prompt`-Feld? | **Ja**, als Persona-Voice | Templates wrappen drumherum, Persona bleibt eigenstaendig nutzbar; keine Migration noetig. |
| Template-Placeholder-Syntax? | **Liquid `{{ … }}`** | Industriestandard; einfach zu parsen; keine Verwechslung mit JS-Templates. |
| Template-Versionierung? | **Ja**, draft/review/active/inactive | Konsistent mit anderen Entities; Templates aendern sich = Audit-Trail wichtig. |
| Agent-Versionierung? | **Nein** | Agent ist Konfig, nicht Inhalt. Spaeter nachruestbar. |
| Wer darf Agents/Templates erstellen? | **Admin + Editor** | Konsistent zu Persona/Playbook (ADR-0023). |
| Auto-Save-Debounce | **1500 ms + flush on blur/unmount** | Erfahrungswert; nicht so kurz dass Server flooded, nicht so lang dass User "weg-tippen" kann. |
| Konflikt-Handling Multi-User-Edit | **Nicht in Slot 1** | Phase-1 vereinfacht: last-write-wins; Optimistic-Lock in Phase 2 nachziehen. |
| Auto-Save bricht Test fuer "Save-Button-Klick" | **Tests rewriten** | Save-Button ist weg; Tests pruefen das neue Verhalten. |
| Submit-for-Review bei Editor-Click? | **Eigener Button**, kein impliziter Trigger | User-Intent muss explizit sein; Editor-Tipper soll nichts ausser Auto-Save tun. |
| Active bleibt unangetastet bis Publish? | **Ja** | "Active-Version bleibt unangetastet" laut Repository-Comment Z.250 — bewahren wir. |

## Offen — bitte bestaetigen (oder ein Wort dazu)

1. **Placeholder-Erweiterbarkeit**: Reichen die obigen 7 Placeholders fuer
   Phase 1? Falls du spezielle Felder (z. B. `{{ persona.tags_as_yaml }}`)
   willst, sag Bescheid — sonst kommt das in Phase 2.
2. **Agent-Limit pro Workspace**: Hard-Limit setzen (z. B. 50)? Heute
   sind alle Entities unlimited; spaeter via Lizenz-Gating. Default: kein
   Limit.
3. **Template-Default-Bibliothek**: Sollen wir ein paar Standard-Templates
   (Support-Agent, Knowledge-Worker, Coach) als Seed mitliefern? Default:
   nein — leere Liste; User kann eigene anlegen.
4. **Copy-Output-Format**: Plain text (Default) oder Markdown mit Headern
   pro Section? Empfehlung **Plain Text** — die meisten LLM-Chats nehmen
   Plain Text sauberer an als Markdown.

---

## Vorgeschlagene Reihenfolge

1. **Slot 1 (3 parallele Agenten):**
   - **Agent A — Persona-Editor-Hydration-Bugfix** (Track 1). Klein,
     ~1 Datei + 1 Test. Mergt zuerst.
   - **Agent B — Auto-Save + Git-Style Status-UX** (Track 2). Gross,
     beruehrt alle drei Entity-Editoren + Hooks + Backend-PATCH.
     Rebased auf Agent A's Merge.
   - **Agent C — Agent + SystemPromptTemplate-Konzept** (Track 3).
     Groesster Track, neues Domain. Disjunkt zu A/B.

2. **Slot 2 (Followups, nach Slot 1):**
   - MCP-Tool `render_agent_prompt` (optional; kann auch ein Mini-PR
     in Slot 1 sein, wenn Agent C es bequem mitnimmt).
   - Optimistic-Lock fuer Multi-User-Auto-Save.
   - Template-Default-Bibliothek (falls in §"Offen" 3 bestaetigt).

## Notion-Follow-up

Nach Merge: Eintrag in PROJ-19 `## Notes` mit Pointer auf diese
Plan-Datei und Liste der PRs.
