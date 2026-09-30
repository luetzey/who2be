# Playbook-Liste ab md: Tag-Spalte begrenzen

Karte t_2a3882b4 · Nebenbefund aus P3 (t_dd172ec5, PR #727), geprüft in t_69709a79.
Basis: origin/main e1fbe695.

## Ziel / Completion-Condition

- 768 und 1024 px, Playbook-Liste, 12 Tags je Playbook, gebautes Stylesheet in Chromium:
  `document.documentElement.scrollWidth <= clientWidth` und Textspalte > 200 px.
- 1280+ mit 0, 2 und 12 Tags nicht schlechter als vorher (Screenshots 768/1280, hell/dunkel).
- Test mit Rot-Probe für die neue Klasse.
- DoD Web (lint, tsc -b, i18n:check, test:coverage, build, license:check), CI grün, Changelog-Fragment.

## Schritte

1. [x] Vorher-Messung auf origin/main (eigener Stack, Seed aus P3 mit 12 Tags an allen
   Seed-Playbooks plus je eins mit 0 und 2 Tags; 768/1024/1280/1440, hell/dunkel).
2. [x] Kandidaten per injiziertem CSS gemessen, dann `PlaybookRow.tsx`:
   `md:max-w-40 lg:max-w-xs` an der Meta-Spalte, Kommentare nachgezogen.
3. [x] Responsive-Test erweitert, Rot-Probe (ohne Fix 1 failed, mit Fix 9/9).
4. [x] Changelog-Fragment `changelog.d/playbook-list-tag-column-md.fixed.md`.
5. [x] Nachher-Messung + Screenshots, DoD, PR.

## Wertwahl (Messung, 12 Tags, Textspalte in px bei 768 / 1024 / 1280)

| Deckel | 768 | 1024 | 1280 | Karte 12 Tags bei 1280 |
|---|---|---|---|---|
| ohne (main) | 0, scrollWidth 1593 | 0 | 0 | 1322 px hoch |
| `md:max-w-[40%]` | 192 (< 200) | 345 | 489 | 158 |
| `md:max-w-[30%]` | 236 | 415 | 583 | 210 |
| `md:max-w-xs` (20rem) | 50 | 306 | 546 | 184 |
| `md:max-w-48` | 178 | 434 | 674 | 288 |
| `md:max-w-40` | 210 | 466 | 706 | 340 |
| **`md:max-w-40 lg:max-w-xs`** | **210** | **306** | **546** | **184** |

Gewählt: `md:max-w-40 lg:max-w-xs`. 40 % und 20rem ab `md` reißen die 200 px bei 768
(Karte dort 480 px neben der Sidebar). 30 % hält 768, würde aber schon 2 Tags bei 768
umbrechen (Tag-Höhe 22 → 48 px) — „wenige Tags sehen aus wie vorher" wäre verletzt.
Ab `lg` gibt 20rem den Tags vier Chips pro Zeile (Karte 184 statt 340 px hoch).

## Ergebnis (gebautes Stylesheet, Chromium, hell und dunkel identisch)

| Viewport | scrollWidth / clientWidth | Text min (12 Tags) | Meta max | Bildschirme |
|---|---|---|---|---|
| 768 | 1593/768 → **768/768** | 0 → **210** | 1236 → 160 | 28,66 → 7,95 |
| 1024 | 1593/1024 → **1024/1024** | 0 → **306** | 1236 → 320 | 27,52 → 5,02 |
| 1280 | 1601/1280 → 1280/1280 | 0 → 546 | 1236 → 320 | 27,33 → 4,61 |
| 1440 | 1681/1440 → 1440/1440 | 0 → 546 | 1236 → 320 | 27,33 → 4,61 |

0 und 2 Tags: Text- und Meta-Breite, Kartenhöhe vorher = nachher (768: 354/217 px,
1280: 850/713 px).

## Hinweis DoD-Lauf

Der erste Lauf lief versehentlich unter Node 26 (190 Ausfälle, `localStorage` in
jsdom undefined) — Repo pinnt Node 22 (`mise.toml`). Unter Node 22: 1619/1626,
die 7 Ausfälle sind a11y-Timeouts (5 s) unter Last paralleler Suiten; isoliert 7/7 grün.
