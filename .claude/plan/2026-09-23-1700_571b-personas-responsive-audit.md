# #571 W3 Personas: Responsive-Audit — Hälfte B (die acht kleinen Dateien)

Karte: `t_64ba46c1` · Issue: [#571](https://github.com/luetzey/who2be/issues/571)
· Schwesterkarte: Hälfte A (PR #609, die fünf großen Dateien)

## Auftrag

Responsive-Audit von acht Dateien der Domäne `features/personas` gegen die
sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4.
Die fünf großen Dateien der Domäne (`PersonaModesEditor`,
`PersonaDetailPage`, `PersonaPlaybooksCard`, `PersonaProfileFields`,
`PersonaProfileEditor`) gehören zur Schwesterkarte und sind hier **nicht**
angefasst.

### Hit-Target-Norm — Herkunft der Zahl

Verbindlich ist §11: **Floor ≥ 32 px**, 40 px Regelfall, `size="sm"` (36 px)
ausdrücklich zulässig. Die 40 px, auf die dieses Paket ein Hit-Target hebt,
kommen aus **AK 3 des Issues** — nicht aus der Norm. Code-Kommentare,
Testnamen und Changelog-Fragment formulieren das entsprechend.

## Messmethode

Nicht am Klassennamen abgelesen, sondern am gebauten CSS gemessen:

1. Ein Wegwerf-Vitest-Testfile rendert die acht Dateien mit echtem
   `cn()`/`tailwind-merge` (langer, trennstellenfreier Persona-, Modus-,
   Playbook- und Skill-Name) und schreibt das resultierende Markup als HTML.
2. Ein Playwright-Chromium-Lauf lädt jedes Markup bei 320 / 375 / 768 px gegen
   `dist/assets/index-*.css` aus dem eigenen `npm run build` und meldet
   Seiten-Scroll, Eigen-Overflow (nur bei `overflow-x: visible`) und die Höhe
   jedes interaktiven Elements.
3. Beide Hilfsdateien sind nach der Messung gelöscht — sie sind nicht Teil des
   Diffs.

## Befund je Datei (alle acht geprüft)

| Datei | Befund | Maßnahme |
|---|---|---|
| `components/PersonaEditorForm.tsx` (149) | **Defekt.** Der Modi-Editor sitzt in zwei geschachtelten Polsterungen (`CardContent p-6` + Disclosure-Body `px-4`). Bei 320 px blieben dem Editor **268 px** — derselbe Editor im Modi-Tab der Detailseite hat **318 px**. Die Summary-Zeile selbst läuft nicht über (gemessen, kein Overflow). | Beide Polsterungen unterhalb `sm` verschmälert (`px-3 sm:px-6` bzw. `px-2 sm:px-4`). Ergebnis: **292 px** bei 320 px; ab `sm` unverändert (768 px: 716 px wie zuvor). |
| `components/PlaybookLinkItem.tsx` (105) | **Defekt gegen AK 3.** Die Aktion war 36 px hoch (`size="sm"`). Nach §11 zulässig, aber AK 3 nennt diese Zeile ausdrücklich und setzt 40 px. Der Texteinlauf ist erfüllt (`min-w-0 flex-wrap`, gemessen: kein Overflow, Zeile bricht um, 82 px hoch bei langem Namen). | `className="h-10 md:h-9"` am Button. Gemessen: 40 px bei 320/375 px, 36 px ab `md` (768 px) — die Verdichtung bleibt. |
| `pages/PersonasPage.tsx` (180) | **Kein Defekt.** Mit doppelt langem Namen, langem Tag und dreifacher Beschreibung: kein Seiten-Scroll (doc == client == 320), kein einziges Element mit Eigen-Overflow. Die Filter-Chips messen 32 px — über dem Floor aus §11 und Bestand geteilter Primitives. | keine |
| `components/PersonaSkillsEditor.tsx` (135) | **Kein Defekt.** Die `justify-between`-Kopfzeile (`:69`) passt auch mit langem Skill-Namen vollständig: der Zeilentitel ist ein kurzes „Skill N", der lange Name steht im Feld darunter, nicht in der Kopfzeile (gemessen 320 px: Label 37 px, Zeile 286/286 — kein Umbruchbedarf). Aktionen 36 px — nach §11 zulässig, von keinem Akzeptanzkriterium adressiert. | keine |
| `components/PersonaSkillsTable.tsx` (58) | **Kein Defekt.** `w-1/3` ist eine Prozentbreite, die mitskaliert. Der horizontale Scroll liegt im `Table`-Primitive (`overflow-x: auto`, gemessen) — nach AK 1 ausdrücklich zulässig, kein Seiten-Scroll. Bei 320 px je 238 px pro Spalte, Zellinhalt ohne Eigen-Overflow. Weiche 3 des Issues greift damit nicht (keine gemessene Unlesbarkeit). | keine |
| `components/PersonaModesPanel.tsx` (47) | **Kein Defekt.** `min-w-0` sitzt richtig, kein Seiten-Scroll. Der Panel-Inhalt hat bei 320 px 318 px — das ist die Referenzbreite, gegen die der Editor-Fund oben gemessen wurde. | keine |
| `pages/PersonaNewPage.tsx` (62) | **Kein Defekt.** Zurück-Link 36 px (§11: für Zurück-Links ausdrücklich zulässig), Submit-Leiste bricht nicht, kein Seiten-Scroll. Profitiert von der Card-Polsterung aus dem Fund oben. | keine |
| `components/SkillsComingSoon.tsx` (45) | **Kein Defekt.** Beide Varianten (Box + `compact`) ohne Overflow auf allen drei Breiten; kein interaktives Element. | keine |

## Gemeldet statt repariert

`PersonaModesEditor.tsx:274`/`:275` — die Modus-Kopfzeile trägt bei 320 px
einen Eigen-Overflow (78 px Inhalt in 43–49 px Box, `flex min-w-0 items-center
gap-2` ohne `flex-wrap`). Das ist **Weiche 1 des Issues** und liegt in der
Schwesterkarte (Hälfte A, PR #609 — offen, nicht gemergt). Kein Seiten-Scroll,
also kein Blocker für dieses Paket. Nicht angefasst, um eine Kollision der
beiden PRs zu vermeiden.

Kein Primitive unter `components/ui/` oder `components/data/` angefasst.

## Verifikation

- Test-first: beide neuen Assertions waren vor der Änderung rot
  (`expected 'p-6 pt-6' to contain 'px-3'`, `expected 'inline-flex …' to
  contain 'h-10'`), danach grün.
- Nachmessung gegen den **neuen** Build bestätigt die Zahlen in der Tabelle.
- Grid-Gate aus AK 6 liefert keine Zeile.
- Web-DoD-Kette aus CONTRIBUTING.md unter Node 22 (`.nvmrc`).
