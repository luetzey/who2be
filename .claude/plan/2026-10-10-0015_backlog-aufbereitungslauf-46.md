# Backlog-Aufbereitungslauf 46

**Datum:** 2026-10-10, 00:15 UTC
**Basis:** `main` @ `6858f707` (25 Commits seit der Lauf-45-Basis `7590c335`)
**Auftrag:** jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket"
(`.github/PROJECT.md` §Constraints) pruefen; Belegbares mit Beleg ins Issue,
Urteilsbeduerftiges als Kommentar mit drei Optionen + Empfehlung + `needs-decision`;
danach die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

**Umgebungs-Vorbehalt:** Der MCP-Server `Who2Be---Coder` ist in dieser Session
nicht erreichbar (CONNECT_TIMEOUT nach 30 s). Persona und Playbook-Katalog
liegen im System-Prompt vor und sind verankert; `fetch_playbook`,
`search_memory`/`save_memory` und `record_usage`/`submit_feedback` sind
nicht aufrufbar. Kein passendes Playbook ladbar — der Lauf faehrt nach dem
in #442 §Pflege-Regeln kodifizierten Verfahren der Laeufe 12-45.

## Lage vor dem Lauf (bereits gemessen)

- Klon war **shallow** (50 Commits), nach `git fetch --unshallow` **1497** (Regel 90).
- `main` @ `6858f707`: CI-Lauf **38007771495** ist **`in_progress`** (Start
  2026-10-10 00:08:58 UTC) — `status` und `conclusion` getrennt gelesen
  (Regel 91). Vorgaenger `8b1b0b5d` ist `success`. **`main` ist nicht rot,
  sondern ausstehend** (Regel 102/103) → Regel 80 greift nicht.
- **#869 ist gemergt** (`6aa50df4`). Die einzige Datei-Sperre von #632 **und**
  #633 aus Lauf 45 ist gefallen — **Regel 87 bestaetigt** („eine Sperre aus
  einem Zustand erledigt sich ohne Antwort").
- `ci.yml`: **1212** Zeilen, `timeout-minutes` → **0**, letzte Aenderung
  `11a243ff` (#839, 2026-10-06) — **unbewegt**, Adresse von #849 frei.
- `docker info` → **Exit 1** (22. Lauf). Node **v22.22.0**.
- Bewegung auf `main` seit `7590c335` (Regel 100): `locales/{de,en}.json`
  **11x**, `deploy/hetzner/RUNBOOK.md` **2x**, `apps/web/e2e` **1x**,
  `api/types.ts` **1x**; `ci.yml`, `MfaSection.tsx`, `LoginPage.tsx`,
  `SessionProvider.tsx`, `vite.config.ts`, `package.json`, `Caddyfile`,
  `plans.md`, `ROADMAP.md`, `README.md`, `PROJECT.md`, `STATE.md`,
  `orphan-baseline.json` je **0x**.
- PR-Bestand **12 offen**: #870 (Protokoll 45, neu), #851, #841, #831, #823
  (Protokolle 44/43/42/41), #827, #825, #824, #686, #683, #682, #674.
  **Der Protokoll-Rueckstand ist auf fuenf gewachsen**; dieser Lauf legt den
  sechsten dazu (Regel 2).

## Arbeitspakete (datei-disjunkt, ein Schreiber je Baum — Regel 30/31/76)

| WP | Inhalt | Baum | Modell | Begruendung der Modellwahl |
|---|---|---|---|---|
| **A** | Web-Gates: `npm run lint` (+ `eslint -f json`: Regelverteilung, `fixableWarningCount`), `npx tsc -b`, `npm run test:coverage`, `npm run i18n:check` | `apps/web` (allein) | Sonnet | vier Gates, Aggregation ueber JSON — mechanisch, aber zahlen-kritisch |
| **B** | Python-Gates: `import who2be_billing`, `pytest --collect-only`, `changelog_fragments.py check` (ohne Pipe, Regel 94), `ls changelog.d/*.md` | Repo-Root (Python) | Haiku | drei Kommandos, feste Ausgabeform — kleinstes ausreichendes Modell |
| **C** | PR-Inventar: je PR Head-SHA, Datei-Scope ueber explizite merge-base, `all-green` **namentlich**, Conclusions positiv auf `failure`/`timed_out` (Regel 101), Gate-Alter gegen `11a243ff`, `behind`, `git merge-tree --write-tree` | git read-only | Sonnet | 12 PRs x 6 Messungen, Klassifikation nach Regel 95 |
| **D** | Norm-Pruefung der 11 offenen Issues (vier Pflichtteile) + Nachmessen **jedes** Zeigers in #632/#633/#849/#540/#535/#428/#435 (Regel 93/97/98) | lesend | Sonnet | Urteil bleibt beim Orchestrator, der Agent liefert Fakten |
| **E** | CI-Spruch-Luecke ueber alle 25 Commits (Regel 104-Nachmessung) + zweite Achse der Sammelpunkte | API + git read-only | Sonnet | API-Paginierung + Zuordnung Commit → Lauf |

**Wellen:** A und B parallel (verschiedene Stacks), C/D/E parallel dazu
(lesend, kein Werkzeug-Zwischenstand). Kein Beteiligter setzt einen
git-Schreibbefehl (`add`, `commit`, `checkout`, `stash`, `restore`, `reset`).

## Danach (Orchestrator, Review-Phase)

1. Konsolidieren: Zahlen gegen Lauf 45 stellen, Abweichungen benennen.
2. Norm-Entscheidung je Issue: Beleg in den Body (eigene Entscheidung) vs.
   drei Optionen + Empfehlung als Kommentar + `needs-decision` (Urteil).
   **Regel 7:** `size/M` wird nie durch Nachtragen von Feldern startbar.
3. #442 neu ordnen (fuenf Kriterien) + Wellen neu schneiden.
4. Bericht in drei Bloecken: selbst erledigt · braucht Owner-Antwort · Reihenfolge + Wellen.
5. Protokoll committen, Draft-PR auf `claude/upbeat-mayer-svf19g`.

## Completion-Condition (messbar)

- [ ] Jedes der 11 offenen Issues ist gegen die vier Pflichtteile geprueft, Ergebnis belegt.
- [ ] Jeder Zeiger in den sieben Issue-Bodies ist mit dem Kommando nachgemessen, das ihn erzeugt hat.
- [ ] #442 traegt eine Reihenfolge, die aus den fuenf Kriterien folgt; Praeferenzen stehen getrennt.
- [ ] Jede Welle nennt Dateien, Stack und Vorbedingung.
- [ ] Protokoll liegt als Datei im Repo, PR offen.
