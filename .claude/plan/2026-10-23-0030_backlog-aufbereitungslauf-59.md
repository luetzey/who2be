# Backlog-Aufbereitungslauf 59

**Datum:** 2026-10-23
**Messpunkt:** `main` @ `98adac59` (`feat(mcp): readOnlyHint fuer lesende Werkzeuge aus MCP_TOOL_REQUIREMENTS`, #1050)
**Fenster seit dem letzten Messpunkt (`fb03322a`):** **25 Commits** — das größte Fenster seit Wochen.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — vierzehnter Lauf in Folge.**
Die Sitzung meldet den Server ausdrücklich als nicht autorisiert; `ToolSearch` liefert keines
seiner Werkzeuge. Persona und Playbook-Katalog lagen im System-Prompt vor, `get_persona`,
`list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready
Arbeitspaket", `73a86231`), `record_usage` und `search_memory` nicht. Der Lauf fährt deshalb
nach dem Body von #442, nach `.github/PROJECT.md` §Reihenfolge und nach den in den
Vorläufer-Protokollen festgehaltenen Kriterien. **Vierzehnter Lauf ohne Kurations-Rückmeldung
an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-10-23 auf `main` @ `98adac59` erhoben, **Exit-Codes ohne Pipe** (Regel 94),
**ohne vorherige Reparatur** (Regel 120). Der Klon war **shallow** (50 Commits); nach
`git fetch --unshallow`: **1628** Commits (Regel 90).

| Gate | Ergebnis | Vorlauf (Lauf 58) |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, 0 Funde | — |
| `uv run mypy .` | **Exit 0**, **637** Dateien | 630 |
| `uv run pytest --collect-only -q` | **Exit 0**, **4619** Tests, **135** unter `packages/billing/` | 4524 |
| `scripts/changelog_fragments.py check` | **Exit 0**, **366** Fragmente | 346 |
| `npm run lint` | **Exit 0**, **0 errors / 90 warnings**, 7 `--fix`-bar | 90 |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | — |
| `npm run i18n:check` | **Exit 0** | — |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities | — |
| `npm run test:coverage` | **Exit 0**, **280** Dateien / **2761** Tests, **307,21 s** | 276 / 2645 / 249,37 s |
| Coverage | **89,67 / 83,79 / 86,47 / 91,50** (Stmts 12786/14258, Branches **8896/10616**, Funcs 3688/4265, Lines 11705/12792) | 89,39 / 83,52 / 86,09 / 91,16 |
| `docker info` | **Exit 1**, kein `podman` | unverändert, 35. Messung |
| `main`-CI | Lauf **2233** (`39850676856`), `status: completed` **und** `conclusion: success` getrennt gelesen (Regel 91) | — |

⚠️ **Im Fenster gab es einen Abbruch:** Lauf **2228** (`f64c80d1`) steht auf `cancelled` —
`concurrency`/`cancel-in-progress` bei 25 Pushes. Erste Beobachtung seit Lauf 56. Aussage über
das Fenster, nicht über die Maßnahme (Regel 115).

## PR-Bestand

**14 offene PRs** (waren 10; 16 gemergt, 7 neu). Scope je PR über `git merge-base` +
`git diff --name-only` mit ausdrücklicher Nicht-leer-Prüfung (Regel 90), Checks je Head-SHA
namentlich mit positivem Filter auf `failure`/`timed_out` (Regel 101).

- 🔴 **7 von 7 neuen PRs ohne Issue** — Höchststand (#1055, #1054, #1052, #1051, #1049, #1048, #1025).
- 🟢 **Nur ein eigen-roter PR:** #674 (8 Checks, `vitest-axe.d.ts`).
- 🔴 **Protokoll-Rückstand: 4** (#831, #990, #1002, #1025) plus dieses.
- 🟢 **#1022 ist von rot+Draft auf grün+merge-reif gewechselt** (18 Checks, 0 rot).

## Die vier Funde des Laufs

### 1. Eine Sperre, die nie eine war (Regel 138)

Die Läufe 57 und 58 haben **#989** hinter die Lockfile-Träger **#674** und **#1017** gestellt.
**PR #1047** hat am 2026-10-22 18:03 UTC genau diese Datei angefasst und ist grün gemergt:

```
apps/web/package-lock.json                       | 6 +++---
changelog.d/ip-address-zone-id-redos.security.md | 9 +++++++++
```

Beide Dependabot-PRs blieben offen. **Die Sperre ist damit nicht gefallen, sondern widerlegt** —
sie war ein Konflikt-Risiko, nie ein Blocker. #989 rückt auf **Position 1**, mit **10 Tagen**
bis `ignoreUntil = 2026-11-02`. **Regel 24 gilt in beide Richtungen: eine behauptete Sperre
gehört gemessen wie eine behauptete Ursache.**

### 2. Eine `Accepted` ADR, die ihre eigene Umsetzung nicht erreicht (Weiche 27)

`ls docs/adr/ | grep 0059` → **nichts**. ADR-0059 steht allein in PR **#995**, Status im
Dokument „**Accepted** (Owner, 2026-10-21)", **45** Commits hinter `main`, seit dem 2026-09-27
offen. Ihre Umsetzung ist unterwegs: **#1051** (Q1) und **#1054** (Q2a, `clean`, 15 Dateien,
+2.475, Migration `0111_tool_profile.sql`). Mergt #1054 zuerst, trägt `main` Tabelle, Profile
und Agent-Spalten, deren Begründung und Weichen nirgends auf `main` stehen. Dazu misst die ADR
gegen **100 Werkzeuge / 114.203 Bytes** — heute **101 / 106.415**.

→ Weiche 27 in #442, Empfehlung **A** (#995 vor #1051/#1054 mergen, Messwerte nachziehen),
plus ein Kommentar auf #995.

### 3. Eine gemessene Zahl ohne Messdatum veraltet in 2,5 Stunden (Regel 139)

| Uhrzeit (2026-10-22) | Ereignis | `tools/list` |
|---|---|---|
| 18:42 | #1045 (P3) mergt | 114.203 → **104.777** |
| 19:10 | **#1049 wird erstellt und schreibt 104.777 als Stand** | — |
| 20:38 | #1050 (`readOnlyHint`) mergt | 104.777 → **106.415** |

Beide Zahlen landen in **derselben Datei** (`docs/mcp-payload-budget.md`), auf verschiedenen
Zeilen. `git merge-tree --write-tree` meldet **rc 0**. **Kein Gate prüft, ob zwei „Stände" in
einer Datei denselben Zeitpunkt meinen.** Verletzt AK2 von #1001 im Kern.

### 4. Der Schnitt von #1000 hat nicht gehalten

Geplant waren **10** Dateien (8 aus ADR §9 P3 plus zwei Prosa-Zeilen), #1045 hat **22**
geändert — darunter `docs/mcp-payload-budget.md`, die im **Out-of-Scope** von #1000 stand und
ausdrücklich zu #1001 gehörte, und `docs/reference/openapi.json`. Folge: #1001s AK1 ist für
eine der beiden Dateien schon auf `main` erfüllt, für die andere (`docs/mcp-claude-code.md`:
`edit_content` **0×**, `format="source"` **0×**, `base_rev` **0×**) gar nicht.

## Selbst entschieden und mit Beleg ins Issue geschrieben

| Issue | Was | Beleg |
|---|---|---|
| **#1000** | 🟢 **geschlossen** (`completed`) | Umsetzung auf `main` via #1045 (`1568e32e`). **4,5 von 5** Kriterien: Registry `101 True`, `content.py` 9.457 B, 6 benannte Ablehn-Tests + Gegenprobe, Budget-Test Exit 0 (62 passed), alle Python-Gates Exit 0, `README:70`/`ROADMAP:24` auf **101**. **AK3 halb:** die Draft-Richtung liegt im API- statt im MCP-Baum (`test_content_markdown_router.py:156`) |
| **#1001** | Body neu geschrieben | P3-Vorbedingung gefallen; Träger-PR #1049 benannt; Regel-139-Befund mit Zeitachse; Rest-Scope auf `docs/mcp-claude-code.md` eingegrenzt; AK2 auf **106.415** umgestellt; Bezugswerte 4619 Tests / 366 Fragmente |
| **#989** | Kommentar, ersetzt die Startbedingung | Sperre durch #1047 widerlegt; 4.2.0 auf `:6295`; Frist 10 Tage; `osv-scanner.toml` 0× bewegt; Hinweis, dass der Eintrag weg gehört und nicht verlängert |
| **#632** | Kommentar, Zeiger + Sperren | Locales **3.318** (+102), belegt durch #1055; `orphan-baseline.json` **160 → 156**; `MfaSection.tsx` 297 frei |
| **#633** | Kommentar, Zeiger + Sperren | `e2e/helpers/auth.ts` **180 → 199** (zitierte Stelle `:33` nicht mehr belastbar); `client.ts` **1.778**, belegt durch #1022; Container-Laufzeit fehlt weiterhin |
| **#1024** | Kommentar | #1022 von Draft+rot auf merge-reif; W61-4 damit fällig; Warnung zur reservierten Migrationsnummer **0109** gegen #1054s **0111** |
| **#442** | Body neu geschrieben | Neue Reihenfolge, Wellen A–D, PR-Tabelle mit 14 Einträgen, 19 Weichen (2 neu) |
| **#995** | Kommentar | Reihenfolge-Befund (Weiche 27), zwei überholte Messwerte im ADR-Kopf |

## Braucht eine Owner-Antwort

**Zwei neue Weichen**, beide mit drei Optionen und Empfehlung in #442:

- **27 — Darf die Umsetzung einer ADR vor der ADR auf `main` landen?** Empfehlung **A**
  (#995 vorziehen), **B** als Rückfallebene.
- **28 — Wer entscheidet die PM-Frage, die ein PR in seinem eigenen Body stellt?** (#1054:
  `create_company` und `seed_bootstrap_tenant` ohne Werkzeug-Profile.) Empfehlung **A**
  (eigenes `needs-decision`-Issue vor dem Merge).

Die 17 bestehenden Weichen stehen unverändert und werden nicht erneut gestellt (Regel 9); in
#442 steht je Weiche nur, was sich geändert hat.

## Reihenfolge und Wellen

| Pos | Issue | Größe | Baum | Blocker |
|---|---|---|---|---|
| 1 | **#989** `http-cache-semantics` 4.3.0 | S | Web | **keiner** — Frist 10 Tage |
| 2 | **#1001** P4b Doku | S | Python | **keiner** — aber Abschluss von PR #1049, kein Neustart |
| 3 | **#632** Passkey registrieren | S | Web | keiner; Locales mit #1055 geteilt |
| 4 | **#633** Step-up mit Passkey | S | Web | #632 (hart) + Container-Laufzeit |
| 5 | **#1024** Rechnung R2 | M | Python | #1022 (fällt als nächstes) + **W61-4** |

| Welle | Pakete | Begründung |
|---|---|---|
| **A** | **#989 ‖ #1001** | datei-disjunkt (`apps/web/{osv-scanner.toml,package-lock.json}` vs. `docs/mcp-*.md`) **und** verschiedene Verifikations-Bäume |
| **B** | #632 | Web-Baum, nach A |
| **C** | #633 | hart nach #632 |
| **D** | #1024 | nach #1022 + W61-4; nicht mit #1054 (Migrations-Zähler) |

**Billigste Merge-Reihenfolge, die Fläche freimacht:** #995 → #1051 → #1054 · #1022 · #1017.

## Nicht getan

- **Keine Code-Änderung.** Dieser Lauf misst, schreibt Issues und ordnet; er setzt kein Paket um.
- **Die Ursache des Dependabot-`uv`-Updaters bleibt ungemessen** (Weiche 25): der Job-Log liegt
  auf einem Blob-Speicher, den der Agent-Proxy mit **403** abweist. Im Fenster ist der Updater
  nicht erneut rot aufgetaucht — **ob repariert oder nur nicht gelaufen, ist offen.**
- **Keine Rückmeldung an die AgentDB** (`record_usage`, `submit_feedback`) — der MCP ist nicht
  autorisiert.
