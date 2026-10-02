# Listen-Karten unter md: Tags „+n“ mit TagList

Karte: t_bf17bd0e · Status: erledigt · Basis: origin/main de6d5e1a
Folge zu #777 (TagList-Baustein, Audit A13-Rest); Patch aus Karte t_648b4527
(kein Stapeln, deshalb eigener PR nach dem Merge von #777).

## Completion-Condition

- Personas-, Resources- und Tools-Liste: unter md drei Tags + „+n“, Knopf
  klappt im Fluss auf (W3=a), Klick navigiert nicht (Knopf `z-10` über dem
  Stretched-Link der EntityCard).
- Ab md pixelgleich (Screenshot 1280, hell/dunkel, 0 abweichende Pixel).
- Gemessen 390 px: Höhe der ersten Karte vorher/nachher.
- Rot-Probe: Seiten auf origin/main → neue Verdrahtungstests rot.
- Web-DoD (CONTRIBUTING.md) unter Node 22 grün.

## Vorentschiedene Weichen

- `TagList` unverändert aus #777 (max 3, `hidden md:contents`, `md:hidden`,
  44 px Trefferfläche, Accessible Name „n weitere anzeigen“, Gruppe „Tags“);
  keine neuen i18n-Schlüssel.
- Badge-Klassen je Seite bleiben wie bisher (über `renderTag`), damit die
  Umbruch-Verträge #562/#564 gelten.
- Playbook-Liste bleibt unberührt (W6=b: Tags unter md ausgeblendet).

## Schritte

1. [x] Patch `pr-b2-lists.patch` auf origin/main angewendet (3 Seiten).
2. [x] Je Seite ein Verdrahtungstest („+2“, Rest `hidden md:contents`,
   Klick → `aria-expanded=true`); Rot-Probe: 3 rot ohne Seitenänderung.
3. [x] Messung im echten Stack (Chromium, Seed mit 12 Tags), vorher = Baum
   aus origin/main, nachher = Arbeitsbaum.
4. [x] Changelog-Fragment.

## Messung (390 px, erste Karte)

| Liste | vorher | nachher |
|---|---|---|
| Personas | 352 px | 234 px |
| Resources | 382 px | 264 px |
| Tools | 332 px | 214 px |

320 px: Personas 478 → 270, Resources 496 → 318, Tools 422 → 244. Kein
seitlicher Überlauf (320/390, auch aufgeklappt). Knopf 36 × 44 px, Klick
bleibt auf der Liste, `aria-expanded=true`.
