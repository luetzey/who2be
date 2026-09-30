# Mobil P3: Listenkarten kompakt (Spec M3, M6-Expander)

Karte t_dd172ec5 · Spec `/home/luetzey/recherche/mobile-spec-2026-09-29.md` §M3, §M6 Punkt 2, §3 P3.
Basis: origin/main cccd4e00 (P2 #721 gemergt).

## Ziel / Completion-Condition

- Scrolltiefe bei 320 px (eigener Stack, Seed + `audit.mjs` aus P2, gebautes Stylesheet):
  Resources-Liste ≤ 5, Playbooks-Liste ≤ 6, Personas-Liste ≤ 3 Bildschirme.
- Expander-Zusammenfassung: keine Ellipse unter 96 px Breite; Knopf ≥ 24 px hoch.
- Tests mit Rot-Probe; lint, tsc, i18n:check, test:coverage, build, license:check grün.

## Schritte

1. [x] Vorher-Messung auf origin/main (320/390/430 + 768/1024).
2. [x] `EntityCard.tsx`
   - Beschreibung: `line-clamp-2 md:line-clamp-3` (präfixiertes Muster, R-F5), `wrap-anywhere`.
     Kein Knopf: der Stretched-Link der Karte ist der Weg zum Volltext (W3, Spec M3).
   - Unter `md` sitzt die Kachel klein (`sm`, 32 px) in der Titelzeile, der Titel
     füllt den Rest der Zeile (`basis-[calc(100%-2.5rem)]`); die große Kachel erst
     ab `md`. Aktionen oben rechts (`items-start` unter `md`).
   - Expander: `expandSummary` unter `md` ausgeblendet, ab `md` mit `min-w-24`.
3. [x] `PlaybookRow.tsx`: dieselben Punkte; zusätzlich steht die Trigger-Pille neben
   dem Blitz statt darunter (`max-w-[calc(100%-1.375rem)]`, gemessen 22 px/Karte).
4. [x] Tests (Klassen-/DOM-Vertrag) in den Responsive-Suites, zwei Rot-Proben.
5. [x] Changelog-Fragment `changelog.d/mobile-list-cards-compact.changed.md`.
6. [x] Nachher-Messung, Screenshots hell/dunkel, DoD. PR.

## Entscheidung (aus dem Repo belegt): keine neuen `…expandCount`-Schlüssel

Die Spec (M6 Punkt 2, „Texte") nimmt an, dass der Expander-Knopf die Anzahl noch
nicht nennt. Im Code trägt `expandLabel` sie bereits:

- Personas → `playbooks:list.subPlaybooksCount` („{{count}} Sub-Playbooks")
- Resources → `resources:card.subResourcesToggle` („{{count}} Sub-Resources")
- Playbook-Liste → `playbooks:list.subPlaybooksCount`

Neue Schlüssel mit demselben Text wären eine zweite Kopie (SSOT) und ohne Aufrufer
Waisen. Deshalb entfällt unter `md` nur die Namensliste; der Knopf zeigt dann
„6 Sub-Playbooks" — genau das Zielbild der Spec. Die Aufrufer
(`PersonaPlaybooksCard.tsx`, `ResourcesPage.tsx`, `PlaybooksPage.tsx`) bleiben
unverändert; die Änderung sitzt an einer Stelle in `EntityCard`/`PlaybookRow`.

## Ergebnis (Bildschirme der ganzen Liste, hell/de, vorher → nachher)

| Liste | 320 | 390 | 430 |
|---|---|---|---|
| Personas | 6,37 → **2,88** | 3,11 → 1,67 | 2,48 → 1,48 |
| Resources | 14,77 → **5,11** | 7,18 → 2,86 | 5,61 → 2,59 |
| Playbooks (20, Seed + 6 verwaltete) | 24,13 → **12,50** | 11,97 → 7,10 | 9,59 → 6,37 |
| Playbooks (14, wie Spec-Seed) | 20,57 → **9,68** | 10,02 → 5,39 | 8,06 → 4,86 |
| System-Prompts | 6,63 → 3,61 | 3,49 → 2,17 | 2,90 → 1,90 |
| Agents | 5,22 → 2,69 | 2,78 → 1,69 | 2,39 → 1,47 |

Einzelkarte bei 320: max. 4,13 → 1,03 (Resources), 4,11 → 0,82 (Personas),
3,15 → 0,72 (Playbooks). Beschreibung: max. 87 → 2 Zeilen. Textspalte 162 → 222/254 px.
Expander: Namensliste unter md weg (vorher 17 bzw. 76 px), Knopf 40/32 px hoch.

### Akzeptanzkriterien

- Personas ≤ 3: **erfüllt** (2,88).
- Resources ≤ 5: **knapp nicht** (5,11). Rest: Tags (12 Chips je Karte) und der
  Filterblock über der Liste (1,47 Bildschirme). Simuliert mit Tags „+3" (t_ed841778):
  4,15 → erfüllt.
- Playbooks ≤ 6: **nicht** (12,50; normiert auf den Spec-Seed 9,68). Zerlegung der
  14 Seed-Karten bei 320 (Summe 8,32 Bildschirme): Tags 2,46, Titelzeile inkl.
  Status/Badges 1,71, Trigger 1,07, Beschreibung 0,99. Die Beschreibung — der
  Umfang von P3 — ist von 10,60 auf 0,99 geschrumpft; der Rest liegt in Tags
  (t_ed841778) und Karten-Grundgerüst. Simuliert mit Tags „+3": 8,40 (Spec-Seed).
  Das Ziel ≤ 6 ist mit P3 + t_ed841778 allein nicht erreichbar; es braucht eine
  weitere Weiche (z. B. Trigger/Tags unter md weglassen) — Rückfrage an @pm.
- Expander ≥ 24 px, Text nicht auf 17–27 px gequetscht: **erfüllt**.

### Desktop-Gegenprobe (768/1024)

Beschreibung 3 Zeilen, große Kachel 44 px, Namensliste ≥ 96 px sichtbar.
Nebenbefund (Bestand, nicht durch P3): Die Playbook-Liste hat bei 768/1024 px
horizontalen Überlauf (scrollWidth 1516 bei 768), weil die `md:w-auto`-Tag-Spalte
mit 12 Tags die Textspalte auf 0 px drückt. Vorher 123 Bildschirme bei 768, nachher 22.
Als Folgekarte gemeldet.
