# Backlog-Aufbereitungslauf 41 — 2026-10-05

**Basis:** `main` @ `54e48ee6` (11 Commits seit der Lauf-40-Basis `f38979bd`).
Alle Zahlen gegen `origin/main`-Refs gemessen, nicht fortgeschrieben.

## Der Lauf in drei Sätzen

🔴 **Alle sechs offenen PRs sind rot auf `all-green` — und kein Lauf vor
diesem hat den CI-Zustand eines PR überhaupt gelesen.** Die Lauf-39- und
Lauf-40-Tabellen führten die offenen PRs nach Datei-Scope und nannten #686,
#683 und #682 „kollidiert mit nichts"; gemessen ist ihr `mergeable_state`
**`blocked`**. Für drei von ihnen ist die Ursache ein Defekt, der seit sieben
Tagen behoben ist.

🔴 **Drei der vier Dependabot-PRs scheitern ausschließlich an einem
`changelog-guard`-Lauf, der 13–21 Minuten zu früh gestartet ist.** Der
Fragment-Bestand war am 2026-09-28 kaputt (zwei Dateien), PR **#678** hat ihn
um **04:42 UTC** repariert — die Läufe von #682/#683/#686 starteten
**04:21–04:29 UTC**. Heute: `changelog_fragments.py check` → **Exit 0, 204
Fragmente sauber**. Ein Re-Run macht die drei Einzeiler grün; niemand hat ihn
angestoßen.

✅ **Die Coverage ist in allen vier Dimensionen zurückgekommen — der
Alarm von Lauf 40 hat eine Prämisse, die einen Lauf später nicht hält.**
Statements 87,86 → **88,19** · Branches 82,10 → **82,28** · Functions 83,90 →
**84,37** · Lines 89,32 → **89,76**, bei einer Suite, die von 1826 auf
**1944** Tests gewachsen ist. Die Weiche bleibt inhaltlich richtig (das Gate
liegt unter dem Ist-Stand), ihre Dringlichkeits-Begründung ist widerlegt.

## Ausgangslage

Lauf 40 (2026-10-04) meldete **ein** startbares Paket (#632), sieben offene
PRs, einen gefallenen Coverage-Wert und stellte die Coverage-Boden-Weiche neu.
Seither sind **11 Commits** und ein PR (#812) gelandet, alle in der
Gedächtnis- und Test-Stabilisierungs-Fläche.

## Messwerte (einzeln, sequenziell, ein Schreiber im Baum), Node v22.22.0

| Kommando | Ergebnis | Lauf 40 |
|---|---|---|
| CI-Run zu HEAD `54e48ee6` (Regel 91) | Run **1724** (`37190904326`), `status: completed`, `conclusion: success`, **13/13 Jobs success** | Run 1703, success |
| `npm run lint` | **Exit 0, 91 problems, 0 errors**, 59 Dateien, 8 Regeln, **9** `--fix`-bar | 90 |
| `npx tsc -b` | **Exit 0** | Exit 0 |
| `npm run test:coverage` | **Exit 0, 248 Dateien, 1944 Tests**, 88,19 / **82,28** / 84,37 / 89,76 | 245/1826, 87,86 / 82,10 / 83,90 / 89,32 |
| `npm run i18n:check` | **Exit 0**, Parität ok, keine Duplikate, **159** Altwaisen je Locale | 159 |
| `uv run pytest --collect-only -q` | **2971 Tests**, Billing in der Collection (`import who2be_billing` → ok) | 2969 |
| `changelog_fragments.py check` | **Exit 0, 204 Fragmente sauber** | nicht gemessen |
| `docker info` | **Exit 1** | Exit 1 |
| `git rev-parse --is-shallow-repository` | **`true`** → nach `--unshallow` **1436** Commits | `true` |

**Lint-Reihe:** 73 → 88 → 84 → 84 → 90 → **91**. Zuwachs allein in
`react-refresh/only-export-components` (11 → **12**); die anderen sieben Regeln
unverändert. Die 9 `--fix`-baren liegen in denselben fünf Dateien wie in
Lauf 40.

**E2E-Zählung je Testkörper** (Schleifen expandiert, Skip-Direktiven
ausgeschlossen — Regel 92): `scroll-guard` **15/12** · `journeys` 6/6 ·
`public` 4/0 · `navigation` 3/3 · `billing` 2/2 · `review-gate` 2/2 ·
`consent-overlay` 2/0 · `status-actions-viewport` 1/1 → **35 Körper, 26 über
`createUser`**. Reihe: 17 → 19 → 24 → 27 → 31 → 33 → 35 → **35**. **Erster
Stillstand dieser Zahl.**

## PR-Scope und PR-Zustand

Scope über `git diff --name-only $(git merge-base origin/main <head>) <head>`
**nach `git fetch --unshallow`**, jede merge-base ausdrücklich auf nicht-leer
geprüft (Regel 90).

| PR | Inhalt | Schreibt nach | `all-green` | Fehlschläge | Alter der Läufe |
|---|---|---|---|---|---|
| **#802** | MCP `save_memory` mit Herkunft (ADR-0053 C4b) | `apps/mcp/**` (4), `apps/api/…/services/placeholders/resolvers/tools.py` + 3 Tests, `packages/models/**` (2), `ROADMAP.md`, `README.md` | 🔴 failure | **`python`** | 2 Tage |
| **#686** | redis 7 → 8 | `deploy/hetzner/who2be/docker-compose.cloud.yml` | 🔴 failure | **nur `changelog-guard`** (veraltet) | 7 Tage |
| **#683** | redis 7 → 8 | `deploy/dokploy/docker-compose.cloud.yml` | 🔴 failure | **nur `changelog-guard`** (veraltet) | 7 Tage |
| **#682** | redis 7 → 8 | `docker-compose.cloud.yml` | 🔴 failure | **nur `changelog-guard`** (veraltet) | 7 Tage |
| **#681** | fastmcp 3.4.7 → **4.0.9** (Major) | `uv.lock` | 🔴 failure | `changelog-guard` (veraltet) **+ `python`** | 7 Tage |
| **#674** | `web-vite-major`, 3 Updates | `apps/web/package.json`, `apps/web/package-lock.json` | 🔴 failure | **`web`, `e2e`, `e2e-mobile` ×3, `e2e-billing-cloud`, `compose-smoke`** (`changelog-guard` ✅) | 7 Tage |

**Alle sechs:** `mergeable_state` = **`blocked`**.

**Der Beleg für „veraltet":** #678 (`baf4da69`) hat den Fragment-Bestand am
2026-09-28 um **04:42 UTC** repariert. Die `changelog-guard`-Läufe starteten
#681 **04:21:06Z** · #682 **04:28:56Z** · #683 **04:28:58Z** · #686
**04:29:20Z** — alle davor. #674s Lauf startete **18:05:50Z**, also danach,
und sein `changelog-guard` ist **grün**. Die zwei damals gemeldeten Fragmente:
`20260926_211500_fetch_playbook_block_selection.md` (falsche Namensform, von
#678 gelöscht) und `t5c8d5364-backup-alarm-ci.added.md` (kein Listenpunkt, von
#678 korrigiert; liegt heute korrekt auf `main`).

**Freigeworden:** `apps/web/src/features/agents/**` inkl. `AgentsPage.tsx` —
#812 ist gemergt. Regel 84 damit zum dritten Mal belegt, diesmal in der
Freigabe-Richtung: die Sperre hat den Träger verloren, nicht die Stelle
gewechselt.

## Zeiger-Prüfung (Regel 93: mit dem Kommando messen, das sie erzeugt hat)

### ✅ Was hält

- **#428, alle 20 Option-B-Zeiger** — mit dem im Body stehenden Muster
  `100[_.]?000` gemessen: **20 quota-tragende Zeilen in 10 Dateien**,
  unverändert. Gegenprobe `test_access_log_rotation.sh:155`/`:165` sind
  Zeitstempel, kein Quota-Bezug — wie im Body vermerkt.
- **#428 CI-Zeiger** — `ci.yml` **1092** Zeilen, `all-green` ab **`:955`**,
  `needs:` **`:978`**, die zehn Einträge **`:979-988`**, `e2e-billing-cloud`
  **`:438`**, Playwright-Aufruf **`:503`**. 11 Jobs über den `jobs:`-Block
  gezählt, 10 im `needs`.
- **#428** `mcp_limit_service.py:98` · `plans.py:118` · `webhook.py:448`
  (`packages/billing/src/who2be_billing/webhook.py`, 454 Zeilen) ·
  `ROADMAP.md:69`.
- **#535** `mcp_limit_service.py:98-99`/`:118` · `core/config.py:159` ·
  `licensing/entitlement.py:61-62`/`:70-71`/`:83-84` (283 Zeilen) ·
  `plans.md:26-29` · `test_doc_price_drift.py:15`.
- **#540** Caddyfile **195** Zeilen, `(access_log)` **`:107`–`:123`**,
  importiert `:127`/`:159`/`:170`/`:185`, `respond @internal … 403` **`:137`**
  **und** `respond @internal_alt … 403` **`:146`**, `grep -nE "\brate\b"` →
  **0 Treffer** · `ci.yml:351`/`:367` ziehen `caddy:2.8-alpine`, `CADDY_IMAGE`
  `:352`/`:368` · `test_headers_ci.sh:47` und
  `test_access_log_rotation.sh:43` Default 2.8-alpine ·
  `who2be/docker-compose.yml:352` → `caddy:2.11.4-alpine`, genau **ein**
  `image: caddy:`-Treffer · `test_compose_hardening.py:216` weist Pins unter
  2.11 zurück (Testfunktion `:194`) · `core/config.py:83`,
  `core/rate_limit.py:47`.
- **#632/#633/#435** `MfaSection.tsx` **297** · `SessionProvider.tsx` **267**
  (`:57` `mfaStepUpPending`) · `LoginPage.tsx` **394** (`:38`
  `completeMfaChallenge`) · `auth.ts` **180** (`:33` `createUser`, `:55` Aufruf,
  `:97` `enrollTotpAal2`) · `audit.test.ts` **371** (`:297` `it.each`, `:321`
  blankes `it(` — beide gelesen, nicht gegrept) · `security.py:202`
  `require_aal2` · `billing.spec.ts:43` Direktive ·
  `scroll-guard.spec.ts:236` Schleife · `package.json:15` `vitest run` ohne
  `--coverage`, `:37` `@supabase/supabase-js ^2.117.1` ·
  `ci.yml:296`/`:302`/`:423`/`:503`/`:737`/`:871` · GoTrue **v2.197.0** an drei
  Stellen: `docker-compose.yml:63`,
  `deploy/hetzner/supabase/docker-compose.yml:92`,
  `deploy/dokploy/docker-compose.yml:82`.
- **`fail2ban`** — `git grep -il fail2ban` über das ganze Repo: **genau ein**
  Treffer (eine Plan-Datei). Fünfter Lauf. #540s Empfehlung A hängt
  vollständig an einem Host-Setup außerhalb des Repos.
- **`check_code_refs.py`** läuft in keinem Workflow (`git grep -n
  check_code_refs -- .github/ scripts/ci/` → 0 Treffer).
- **OSV-Frist** `apps/web/osv-scanner.toml`, `ignoreUntil =
  2026-11-02T00:00:00Z` → heute **28 Tage**.
- **Tote Referenz** `docs/cloud-hosting-owner-guide.md`: **10 Dateien**
  (6 Plan, 3 Changelog-Fragmente, `test_doc_price_drift.py`); Datei existiert
  weiterhin nicht.

### 🔴 Was verrottet ist

1. **`apps/web/vite.config.ts:49-54` trägt die Coverage-Thresholds nicht mehr
   — sie stehen auf `:81-85`.** Die Zeilen `:49-54` sind heute der
   `include`-Kommentar des Vitest-Projekts `unit`. Die Thresholds (`80 / 79 /
   75 / 80`) liegen im `coverage`-Block ab **`:67`**, `thresholds:` auf
   **`:81`**, die vier Werte auf **`:82-85`**; die Datei ist **89** Zeilen
   lang. **Ursache ist ein Commit, nicht ein Messfehler:** **#817**
   (`9351ffdd`) hat das eigene Vitest-Projekt `a11y` eingeführt und die
   `projects`-Struktur vor den `coverage`-Block gezogen. Der Zeiger steht in
   **#632, #633, #435** und in der Lauf-40-Weiche 3 — vier Stellen, Regel 58.
2. **`.github/PROJECT.md` §Reihenfolge, drei Zeiger und eine Tabellenzeile.**
   `:90` nennt den GoTrue-Pin `v2.196.0` (ist `v2.197.0`, PR #671), `:91`
   `deploy/hetzner/supabase/docker-compose.yml:63` (ist `:92`), `:92`
   `deploy/dokploy/docker-compose.yml:81` (ist `:82`). Die Tabelle führt
   **#624**, das geschlossen ist. Stand-Zeile stand auf Lauf 31.
3. **`deploy/hetzner/RUNBOOK.md:944-945` nennt als „zuletzt" gehobenen Pin
   `v2.158.1 → v2.196.0`.** Der jüngste Sprung im Repo ist
   `v2.196.0 → v2.197.0` (PR #671). Der Rest des Abschnitts ist bewusst der
   historische #499-Fall und bleibt, wie er ist.

### Eigener Messfehler dieses Laufs (Regel 49)

`changelog_fragments.py check | head -20` meldete **Exit 1** — das war
**SIGPIPE** durch das eigene `head`, nicht der Prüfbefund. Ohne Pipe gemessen:
**Exit 0**. Der Lauf stand kurz davor, einen Defekt auf `main` zu melden, den
`main`s eigener grüner `changelog-guard`-Job widerlegt. Gegenmaßnahme-Vorschlag
als **Regel 94**.

## Arbeitspakete dieses Laufs

### A — selbst entschieden (das Repo belegt es)

1. **`vite.config.ts:49-54` → `:81-85`** in #632, #633, #435 und im
   Queue-Body nachziehen, mit dem Verursacher-Commit als Beleg.
2. **Messwerte nachziehen** in #632, #633, #435, #428, #535, #540, #442:
   Lint 90 → 91, Suite 245/1826 → 248/1944, Coverage **gestiegen**, Python
   2969 → 2971, E2E 26/35 unverändert, Waisen 159, CI-Run 1703 → **1724**,
   PR-Zahl sieben → **sechs**, OSV-Frist 29 → **28** Tage.
3. **Den PR-Zustand erstmals in die Liste aufnehmen** — sechs von sechs
   `blocked`, mit Fehlschlag-Ursache je PR und dem #678-Zeitbeleg.
4. **`AgentsPage.tsx`/`features/agents/**` als frei zurückmelden** (#812
   gemergt) — in #632s und #633s Startbedingung steht es als Negativ-Beispiel.
5. **`.github/PROJECT.md` reparieren** — drei Zeiger, #624-Zeile, Stand-Zeile,
   unbelegte Laufzahl beim Docker-Satz. Repo-PR.
6. **`deploy/hetzner/RUNBOOK.md:944-945`** — „zuletzt"-Angabe auf #671
   nachziehen. Derselbe PR.
7. **#442 neu ordnen** — Reihenfolge, Wellen, Kollisionen, Sammelpunkte gegen
   `54e48ee6`.

### B — braucht eine Owner-Antwort

| Frage | Alter | Ort |
|---|---|---|
| 🔴 **NEU — Was passiert mit sechs blockierten PRs, drei davon grün-fähig?** Drei Optionen + Empfehlung | 0 Tage | #442 (Kommentar) |
| Arbeitspaket-Vertrag auch für Tracking-Issues? (Empf. **B**) | 4 Tage | #442 |
| Bleibt `audit` im Required Check? (Empf. **A**, **C** als Paket) | seit Lauf 36 | #442 |
| Coverage-Boden anheben? (Empf. **B**) — **Prämisse teilweise widerlegt** | 1 Tag | #442 |
| Caddy-Versions-Widerspruch (Empf. **A**) | seit Lauf 35 | #442 |
| ESLint-Warnungen (Empf. **B**) — Zahl jetzt **91** | seit Lauf 36 | #442 |
| #540 Mechanismus + Prüfbarkeit (Empf. **A**/**C**) | 16 Tage | #540 |
| #428 Pro-Request-Limit (Empf. **A**) | 30 Tage, wird nicht erneut gestellt | #428 |
| #542 Rechnungsmodell/USt | 16 Tage, `human-only` | #542 |

### C — Norm-Befunde (unverändert, hängen an Weiche 1)

- **#428 und #535** haben **weder Outcome noch Verifikations-Abschnitt**.
  Vorhanden: Problem, Acceptance criteria, Out of scope.
- **#435** führt 6 Akzeptanzkriterien, zwei ohne Schwelle; `size/M` → Regel 7,
  der nächste Schritt wäre Zuschnitt, nicht Refinement. W2 ist geschnitten
  (#632/#633), W1 erledigt.
- **#540** ist norm-vollständig (Fertig heißt / AK / Verifikation / Out of
  scope), aber dreifach blockiert.
- **#632, #633** erfüllen die Norm vollständig — `agent-ready` zu Recht.

## Bedingungen

Read-only am Arbeitsbaum außer diesem Plan, `.github/PROJECT.md` und
`deploy/hetzner/RUNBOOK.md` auf `claude/upbeat-mayer-5j51pv`. Kein Docker
(nicht vorhanden), keine E2E-Läufe. Alle Web-Messungen sequenziell, ein
Schreiber im Baum (Regel 31/76). Kein Re-Run und kein Merge an einem fremden
PR — das ist Teil B, nicht Teil A.
