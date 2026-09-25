# Backlog-Aufbereitungslauf 31 — 2026-09-25

**Basis:** `main` @ `cee6478` (13 Commits seit der Lauf-30-Basis `116bfcd`).
Alle Zahlen in diesem Lauf sind gegen `origin/main`-Refs gemessen, nicht
fortgeschrieben.

## Ausgangslage

Lauf 30 (2026-09-24) fand **null startbare Issues bei fünf offenen PRs** und
meldete das als Befund über den Einstiegspunkt, nicht über den Vorrat
(Queue-Regel 65). Seither sind **alle fünf PRs gemergt** plus sechs weitere
(#620–#623, #626, #627, #629, #630).

## Der zentrale Befund dieses Laufs

**#431 ist fertig.** Seine drei offenen Akzeptanzkriterien (1, 4, 5) hingen
laut eigenem Body ausschließlich am Merge der Welle-7-PRs. Der ist durch, und
die im Body selbst formulierte Schließbedingung ist erfüllt:

| Bedingung (Body #431) | Messung |
|---|---|
| #615, #618, #622, #623 auf `main` | `c4999d3`, `4bc2d65`, `fa60461`, `09a322a` |
| `apps/web/e2e/helpers/` trägt den Scroll-Helfer | `auth.ts`, `consent.ts`, **`viewport.ts`** |
| `playwright.config.ts` führt vier Profile | `:45` chromium, `:47` mobile-iphone-13, `:51` tablet-ipad-gen-7, `:72` mobile-320 |
| `e2e-mobile` in `all-green.needs`, kein `continue-on-error` | `ci.yml:449` Job, `:764` in `needs`, `:847` `expect`-Zeile, `:314` Soft-Gate entfernt |
| erster `all-green`-Lauf auf `main` meldet die Mobile-Profile grün | **Run 36047465542, 12/12 Jobs `success`** |

## Arbeitspakete dieses Laufs

### A — selbst entschieden (Repo belegt es)

1. **#431 schließen** — Schließbedingung erfüllt, Beleg oben.
2. **#624 auf die Norm bringen** — trägt heute **kein einziges Label** und keine
   Verifikations-Kommandos. Felder ergänzen, Labels setzen; die Design-Weiche
   selbst bleibt offen → `needs-decision`.
3. **#435 W2a/W2b als Kind-Issues anlegen** — der Zuschnitt steht seit Lauf 30
   vollständig im Body (Weiche 6: Dateien, Zeilenzahlen, harte Abhängigkeit).
   Queue-Regel 34: eine Zerlegung ist erst vollständig, wenn jedes Stück ein
   Issue hat. Flächen am 2026-09-25 nachgemessen: `MfaSection.tsx` 297,
   `LoginPage.tsx` 383, `SessionProvider.tsx` 267 — unverändert.
4. **#428 Zeiger korrigieren** — `e2e-billing-cloud` steht auf `ci.yml:365`,
   der Body nennt `:299`.
5. **#540 fortschreiben** — der Satz „#536 und #537 schließen die Löcher"
   beschreibt einen Zustand mit offenen Geschwistern; #540 ist seit dem Merge
   von #576 das letzte offene Kind von #535. Docker: **19. Lauf in Folge ohne
   Daemon** (`/var/run/docker.sock` existiert nicht).
6. **`.github/PROJECT.md` §Reihenfolge reparieren** — ältester ungeschnittener
   Posten des Backlogs (seit Lauf 24). Die Tabelle nennt zehn Issues, von denen
   **keines mehr offen ist**; `:96` trägt `docker-compose.yml:50` für den
   GoTrue-Pin, richtig ist `:63`. Fix ist ein Repo-PR, kein Issue-Write.
7. **#442 neu ordnen** — Reihenfolge + Wellen gegen den neuen Stand.

### B — braucht eine Owner-Antwort

| Frage | Alter | Ort |
|---|---|---|
| Karten oder Issues? (Struktur) | seit Lauf 30 | #442 |
| #428 — Pro-Request-Limit anheben? | 15 Tage | #428 |
| #540 — welcher Rate-Limit-Mechanismus? | 6 Tage | #540 |
| #624 — Bottom-Bar auf Mobile? | neu aufbereitet | #624 |

### C — Befund an PR #631 (kein Issue, Karte `t_ce4d9a7f`)

Zwei Body-Angaben halten der Messung nicht stand; **der Diff ist in beiden
Fällen richtig, der Body falsch**:

1. „Das Verzeichnis `changelog.d/` existiert im Repo nicht" — es trägt auf
   `main` **38 Dateien** inkl. `README.md`, und der PR selbst liefert
   `changelog.d/cloud-auth-external-providers.changed.md`. `CHANGELOG.md` ist
   nicht im Diff, `changelog-guard` ist grün.
2. Die GoTrue-Handler-Tabelle ist gegen **`v2.158.1`** belegt. Auf `main` steht
   seit #499 an allen drei Stellen **`v2.196.0`**.

Dazu eine inhaltliche Wechselwirkung mit #435 W2b, siehe dort.

## Bedingungen

Read-only am Arbeitsbaum außer dem PROJECT.md-PR auf
`claude/upbeat-mayer-do2cp4`. Kein Docker (nicht vorhanden), keine Testläufe
im Repo-Baum.
