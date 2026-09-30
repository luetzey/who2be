# Mobil P3b: Playbook-Liste unter md ohne Trigger und Tags

Karte t_1c5a1a34 · Owner-Entscheidung W6=b (2026-09-30): „Trigger und Tags auf dem
Handy ausblenden, nur Name, Status und zwei Zeilen Beschreibung bleiben."
Basis: origin/main 19ca5e9d (t_2a3882b4 / #737 gemergt).

## Ziel / Completion-Condition

- 320 px, Playbook-Liste, 14er-Spec-Seed, gebautes Stylesheet in Chromium:
  Scrolltiefe ≤ 6 Bildschirme (Messung wie P3: Nicht-Seed-Karten ausgeblendet).
- 768/1024/1280: Zeilenbreiten, -höhen und Scrolltiefe identisch zum Stand nach
  t_2a3882b4 (Messung vorher = nachher, Screenshots hell/dunkel).
- Test mit Rot-Probe: unter md keine Trigger-Liste und keine Tag-Gruppe im
  Accessibility-Tree, ab md vorhanden.
- Web-DoD (lint, tsc -b, i18n:check, test:coverage, build, license:check), CI grün,
  Changelog-Fragment, ≤ 8 Dateien.

## Schritte

1. [x] Vorher-Messung auf origin/main (eigener Stack, Seed aus t_2a3882b4 +
   je ein Playbook mit 0 und 2 Tags; 320/390/430 und 768/1024/1280, hell/dunkel).
2. [x] `PlaybookRow.tsx`: Trigger-Liste `hidden md:flex`, Meta-Spalte (Tags +
   Chevron) `hidden md:flex`. `display:none` nimmt beides aus dem
   Accessibility-Tree (nicht nur visuell versteckt).
3. [x] Responsive-Test: Kaskade per eingefügtem Stylesheet simuliert, Rot-Proben.
4. [x] Changelog-Fragment `changelog.d/playbook-list-mobile-no-triggers-tags.changed.md`.
5. [x] Nachher-Messung + Screenshots, DoD, PR.

## Entscheidungen (aus dem Repo belegt)

- **Die ganze Meta-Spalte fällt unter md weg, nicht nur die Tags.** Sie enthält
  außer den Tags nur den Chevron (`aria-hidden`, dekorativ). Stünde der Chevron
  allein, bliebe unter md eine eigene Zeile samt `gap-4` (16 + 16 px je Karte)
  ohne Inhalt. Die Karte ist per Stretched-Link des Namens klickbar; das
  Klick-Ziel bleibt unverändert. Der Wortlaut der Owner-Entscheidung („nur Name,
  Status und zwei Zeilen Beschreibung") deckt das.
- **„Teil von"-Link und Composite-Umschalter bleiben.** Sie sind weder Trigger
  noch Tags und von der Entscheidung nicht erfasst; der Seed misst sie ohnehin
  nicht (keine Composites in den 14 Spec-Karten).
- **Unter md keine „+N"-Anzeige für Trigger/Tags.** Mit W6=b gilt „+3" aus
  t_ed841778 für PlaybookRow nicht mehr (PM-Kommentar auf t_ed841778).
- **Die Meta-Spalte trägt ihre md-Klassen jetzt als Basis.** Aus
  `flex w-full flex-row items-center md:w-auto md:flex-col md:items-end` wird
  `hidden flex-col items-end md:flex`: unter md ist sie nicht mehr sichtbar, die
  Quer-Anordnung war nur dort wirksam. Ab md ergibt sich dieselbe berechnete
  Darstellung (Messung unten: vorher = nachher).
- **Nach Tags filtern bleibt möglich:** `PlaybooksPage.tsx` reicht
  `availableTags`/`onTagChange` an den Filterblock (unverändert).

## Ergebnis (gebautes Stylesheet, Chromium, eigener Stack)

Scrolltiefe der Liste in Bildschirmen, 14er-Spec-Seed (übrige Karten ausgeblendet,
Verfahren wie P3 `norm.mjs`), hell und dunkel identisch:

| Viewport | vorher | nachher |
|---|---|---|
| 320 × 568 | 11,60 | **5,55** |
| 390 × 844 | 6,34 | 3,42 |
| 430 × 932 | 5,72 | 3,08 |

Zerlegung bei 320 (Summe über 14 Karten, in Bildschirmen): Karten 10,24 → 4,19;
Trigger 1,07 → 0; Meta-Spalte (Tags) 4,39 → 0; Titelzeile 1,71 und Beschreibung
0,99 unverändert. Mit dem P3-Seed (Tags 3–11 je Playbook statt 12) ebenfalls 5,55
(nachher), da Tags unter md nicht mehr zur Höhe beitragen. Die P3-Zahl 9,68 lag
unter der hier gemessenen 11,60, weil jener Seed weniger Tags je Playbook hatte.

Desktop 768/1024/1280, hell und dunkel: alle 22 Zeilen vorher = nachher
(Breite Text- und Meta-Spalte, Kartenhöhe, Höhe Trigger und Tags), scrollWidth
= clientWidth, Scrolltiefe 7,95 / 5,02 / 4,61 unverändert. 12 Tags: Text
210/306/546 px wie nach t_2a3882b4.

Rot-Proben (Vitest, `PlaybookRow.responsive.test.tsx`, 11 Tests):
1. Beide Ausblendungen zurück → 2 rot (Klassenvertrag, Accessibility-Tree).
2. Meta-Spalte nur `sr-only` statt `hidden` → 2 rot.
3. Nur Trigger-Ausblendung zurück → 1 rot (Trigger-Liste im Tree).
