# Mobil P6b: Mitglieder als Liste, Auswahllisten ohne inneren Scroll

Karte t_17c08118 · Spec `/home/luetzey/recherche/mobile-spec-2026-09-29.md`
M9, M11 (W5=a), M6 (SubResourcePicker-Zeilen). Basis: origin/main 32a4dde2.
P6a-Teile #734/#735 gemergt; #736 (Tabellen-Wrapper) offen und freigegeben —
P6b haengt NICHT daran: unter md rendert MembersPage keine Tabelle mehr, ab md
bekommt die Tabelle das Muster automatisch, sobald #736 gemergt ist.

## Completion-Condition

- MembersPage bei 320/390/430 ohne horizontalen Seitenueberlauf und ohne
  inneren x-Scroller (vorher: Tabelle 121 von 393 px sichtbar bei 320).
- Unter md: Mitglieder als Liste — Name (E-Mail bzw. user_id) + Rolle sichtbar,
  Beitrittsdatum und Entfernen in einem Aufklappbereich (`aria-expanded`).
  Ab md: unveraenderte Tabelle.
- PersonaPlaybooksCard (Hinzufuegen-Liste) und SubResourcePicker (Verfuegbar):
  unter md kein `max-h`/`overflow`, 8 Treffer, Knopf
  `common:actions.showMoreCount` laedt je 8 weitere, Fokus auf den ersten
  neuen Eintrag, `aria-live=polite` mit `common:list.shownOfTotal`.
  Ab md: `max-h-72 overflow-auto` + `tabindex=0` + `role=region` + Name.
- SubResourcePicker: keine `truncate` mehr an Namen (Z. 180/221/338) —
  Namen brechen um (`wrap-anywhere`).
- Vitest mit Rot-Proben; Web-DoD (lint, tsc -b, i18n:check, test:coverage,
  build, license:check); E2E `scroll-guard.spec.ts` erweitert; CI gruen;
  Changelog-Fragment; <= 8 Dateien.

## Entscheidungen (aus Repo/Spec belegt)

- **Gemeinsamer Hook statt Doppelcode**: `useShowMore` in
  `src/hooks/useShowMore.ts` (8er-Schritte, Reset bei Suchwechsel, Fokus auf
  ersten neuen Eintrag, Live-Text). Beide Listen nutzen ihn; die Komponente
  wuerde sonst zweimal dieselbe Logik tragen (SSoT).
- **Breakpoint per `useIsMobile`** (bestehender Hook, `max-width: 767px`,
  bereits von AppShell/GiveFeedbackDialog genutzt), weil die Kuerzung auf
  8 Eintraege Logik ist (wie viele Elemente gerendert werden), nicht CSS.
  Ohne `matchMedia` (jsdom) liefert er `false` → Desktop-Pfad.
- **Mitglieder unter md als `<ul>` mit nativem `<details>`/`<summary>`?** Nein:
  Button mit `aria-expanded`/`aria-controls` wie ExpandableText (M2-Muster),
  damit die Rollen-Auswahl in der Kopfzeile nicht im `summary` liegt
  (interaktive Elemente in `summary` sind a11y-problematisch).
- **Rollen-Select bleibt in der Kopfzeile** (Prioritaetsfeld "Rolle" laut W5=a),
  E-Mail ist der Name (Prioritaetsfeld), "Beitritt" + Entfernen aufklappbar.
  Die Karte nennt "E-Mail/Beitritt aufklappbar"; E-Mail IST bei uns der Name
  (es gibt kein separates Namensfeld im `Member`-Typ) — daher steht sie oben,
  aufklappbar ist Beitritt + Entfernen-Aktion.
- **Tabellen-Name**: die Desktop-Tabelle bekommt `aria-labelledby` auf den
  CardTitle (Reviewer-Nit aus P6a) — erst wirksam mit #736 (`labelledBy`-Prop);
  bis dahin setzt P6b `aria-labelledby` nicht, um keinen Konflikt mit #736 zu
  erzeugen. → als Restpunkt im Handoff.

## Schritte

1. [x] Vorher-Messung auf origin/main (eigener Stack w2b17c, Ports 59xxx).
2. [x] `useShowMore` + Test.
3. [x] PersonaPlaybooksCard, SubResourcePicker (Liste + Namen).
4. [x] MembersPage Liste unter md.
5. [x] Tests mit Rot-Proben, E2E erweitern.
6. [x] Nachher-Messung, DoD, Changelog, PR.

## Abweichung vom Plan

- `aria-labelledby` an der Desktop-Tabelle bleibt Restpunkt (haengt an #736).
- Die Mobil-Liste ist per `aria-labelledby` an den CardTitle „Mitglieder“
  gebunden (eigene `useId`), die Tabelle ab md bleibt unveraendert.
- Seed fuer die Messung: Zusatz-Mitglieder direkt in der Wegwerf-DB, weil
  Einladungen MFA verlangen (Admin-Gate) — betrifft nur das Messskript.

## Messung (Chromium gegen den gebauten Stack, Seed: 3 Mitglieder, 20 Playbooks, 20 Resources mit langen Namen)

| Ansicht | Breite | Vorher | Nachher |
|---|---|---|---|
| Mitglieder | 320 | Tabelle im x-Scroller, 238 von 619 px sichtbar | Liste, 3 Eintraege, 238/238 px, kein Scroller; aufgeklappt hOverflow 0 |
| Mitglieder | 390 / 430 | x-Scroller 308/619 bzw. 348/619 | Liste ohne Scroller |
| Mitglieder | 1024 | Tabelle 686/686 | unveraendert Tabelle |
| Persona „Playbook hinzufuegen“ | 320/390/430 | `ul` max-h 288 px, overflow auto, 26 Eintraege, ohne Namen/tabindex | kein max-h; 8 Eintraege + „8 weitere anzeigen“; Klick → Fokus auf „Verknuepfen“ des 9., live „16 von 26 angezeigt“ |
| Persona | 1024 | Scroller ohne Name, ohne tabindex | Scroller `role=region`, Name „Playbook hinzufuegen“, tabindex 0 |
| Sub-Resources „Verfuegbar“ | 320/390/430 | `ul` max-h 288 px, 21 Eintraege, Namen `truncate` (14/5/4 gekuerzt) | kein max-h; 8 + „8 weitere anzeigen“; Fokus auf 9. Eintrag; live „16 von 21 angezeigt“; 0 gekuerzte Namen |
| Sub-Resources | 1024 | Scroller, 4 gekuerzte Namen | Scroller benannt + tabindex 0, 0 gekuerzte Namen |

Horizontaler Seitenueberlauf: ueberall 0, vorher wie nachher. Hell und dunkel
bei 390 px identisch.

## Verifikation

- Vitest gezielt: 5 Dateien, 61 Tests gruen. Rot-Probe: Komponenten auf
  origin/main zurueckgesetzt → 11 neue Tests rot, 46 alte gruen.
- Web-DoD: `npm run lint` 0 Fehler (88 Warnungen, identisch zu main);
  `tsc -b` ok; `test:coverage` 235 Dateien / 1643 Tests gruen, Coverage-Gate
  ok; Skip-Budget 0/0; `build` ok; `license:check` ok.
- i18n-Ratchet: `common.actions.showMoreCount` und `common.list.shownOfTotal`
  sind jetzt benutzt → aus `orphan-baseline.json` gestrichen.
- E2E `scroll-guard.spec.ts` „M9/M11“: gruen auf chromium, mobile-iphone-13,
  tablet-ipad-gen-7, mobile-320 (lokaler Stack).
- Python unveraendert → Python-DoD nicht betroffen.
