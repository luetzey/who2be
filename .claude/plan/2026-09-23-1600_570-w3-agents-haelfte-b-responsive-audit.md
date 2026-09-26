# #570 W3 `features/agents` — Hälfte B: Responsive-Audit der sechs kleinen Dateien

Karte `t_2c96b506`, Schwesterkarte Hälfte A = `t_bf48ee1a` (PR #608).
Branch `who2be/t_2c96b506-570-w3-agents-haelfte-b-responsive-audit`, rebased auf
`origin/main` @ `c558860d`.

## Scope (exakt sechs Dateien)

| Datei | Z. | Ist-Befund laut #570 |
|---|---|---|
| `apps/web/src/features/agents/components/AgentHierarchyView.tsx` | 179 | `:95` `px-2 py-1.5 text-sm` ≈ 32 px Zeilenhöhe |
| `apps/web/src/features/agents/pages/AgentDetailPage.tsx` | 132 | kein Klassen-Befund; Kopfbereich zu prüfen |
| `apps/web/src/features/agents/components/CopyPromptButton.tsx` | 102 | kein Klassen-Befund; Hit-Target zu prüfen |
| `apps/web/src/features/agents/components/DeleteAgentButton.tsx` | 92 | Dialog erbt W2-Default (erfüllt); Hit-Target + Dialogtexte |
| `apps/web/src/features/agents/components/AgentConnectorSection.tsx` | 89 | `:54`/`:70` `flex items-center gap-2` ohne `flex-wrap` |
| `apps/web/src/features/agents/components/DuplicateAgentButton.tsx` | 65 | kein Klassen-Befund; Hit-Target zu prüfen |

Tabu (Hälfte A / andere Karten): `AgentsPage`, `AgentEditorForm`,
`AgentMemorySection`, `AgentTokensSection`, alle Primitives unter
`components/ui/` und `components/data/`.

## Norm-Lage (wichtig für Formulierungen)

`docs/frontend/design-language.md` §11 ist die **einzige** Quelle des
Hit-Target-Floors: **≥ 32 px verbindlich**, 40 px (`size="default"`) Regelfall,
44 px mobile Präferenz, `size="sm"` (36 px) ausdrücklich zulässig. Die 40 px,
die dieses Paket anhebt, stammen aus **Akzeptanzkriterium 4 des Issues #570**
(„Hit-Targets unterhalb `md` ≥ 40 px"), nicht aus der Norm. Beide hier
angehobenen Stellen lagen **auf oder über** dem Floor — es wurde also keine
Norm-Unterschreitung behoben, sondern der Regelfall unterhalb `md` hergestellt.

## Methode

Gemessen gegen das **gebaute** Stylesheet (`dist/assets/index-X7XKexBJ.css`,
280 680 Bytes) in Chromium/Playwright bei 320 px, Gegenprobe 768 px. Die
Klassenlisten wurden als **Ergebnis von `tailwind-merge`** aufgebaut, nicht als
Quell-Konkatenation; die Primitive-Basisklassen (`Button`-cva, `Input`, `Card`,
`Container`, `Stack`, `DialogContent`) sind wörtlich aus dem Repo übernommen.
Überlauf-Kriterium doppelt: `child.right > parent.contentRight` **und**
`scrollWidth > clientWidth` — abgeschnittener Text erzeugt keinen Body-Scroll,
ist aber §4.4 Punkt 5. Die Messharnesse
(`apps/web/scripts/measure-570b.mjs`, `scan-570b.mjs`) waren Einmal-Werkzeuge
und sind nicht Teil des Commits.

## Messwerte bei 320 px (Gegenprobe 768 px)

### Hit-Targets im Detail-Header

| Element | vorher | nachher | 768 px nachher |
|---|---|---|---|
| Kopieren (primary, `size="default"`) | 112 × 40 | unverändert | 112 × 40 |
| Kopieren-Dropdown-Trigger | **33 × 40** | **40 × 40** | 33 × 40 (zurück) |
| Duplizieren | 128 × 40 | unverändert | 128 × 40 |
| Löschen | 108,9 × 40 | unverändert | 108,9 × 40 |
| Zurück-Link (`size="sm"`) | 164,8 × 36 | unverändert | 164,8 × 36 |
| Playbook-Zeile (Baumknoten) | **238 × 32** | **238 × 40** | 670 × 32 (zurück) |

Der Zurück-Link bleibt bei 36 px: §11 lässt `size="sm"` für Zurück-Links
ausdrücklich zu, und AK 4 nennt ihn nicht.

### Connector-Felder

| Zeile | vorher | nachher | 768 px nachher |
|---|---|---|---|
| Server-URL: Zeile | 238 × 40 | 238 × 84 (gestapelt) | 670 × 40 (Zeile) |
| Server-URL: Eingabefeld | **94,9 px breit, Inhalt 521 px** | **238 px** | 526,9 px |
| Connector-Name: Eingabefeld | **77,3 px breit, Inhalt 412 px** | **238 px** | 509,3 px |
| Kopieren-Button | 135,1 × 36 | 238 × 36 (voll breit) | 135,1 × 36 |

Die Felder bleiben auch nach dem Fix `scrollWidth > clientWidth` — das ist bei
einem Read-only-`<input>` für eine 521 px lange URL erwartbar und kein Defekt:
das Feld ist scrollbar und `onFocus` selektiert den vollständigen Wert. Von
95 px auf 238 px verdreifacht sich der sichtbare Anteil.

### Nicht-Funde, gemessen

- **`DeleteAgentButton` Dialog:** 288 × 278 px bei 320 px Viewport, also
  innerhalb der Fensterbreite mit 16 px Rand links/rechts, und in sich
  scrollend — der W2-Primitive-Default trägt, ohne eigene Caps an der
  Aufrufstelle (AK 5 bestätigt). Die beiden Footer-Buttons stehen bei 320 px
  gestapelt und voll breit (238 × 40), ab `sm` nebeneinander (101,7 × 40).
- **`DeleteAgentButton` / `DuplicateAgentButton` Trigger:** 108,9 × 40 bzw.
  128 × 40 px — `size="default"`, erfüllen AK 4 ohne Änderung.
- **`AgentDetailPage`:** keine eigene Layout-Klasse mit Defekt. Die
  Aktionsleiste (`flex flex-wrap`) umbricht bei 320 px korrekt auf 288 × 88 px
  und läuft nicht über die `Container`-Innenkante (Überlauf 0 px). Die
  Status-Capsule (`AgentStatusBadge`, `:38`) sitzt in der umbrechenden
  Badge-Zeile und ist unkritisch.
- **`AgentHierarchyView` `PrimaryRow`:** `min-w-0 flex-1` + `truncate` am
  Namens-Link tragen bereits — 150 px breit, kein Überlauf. Der Link kürzt
  kontrolliert, was AK 2 ausdrücklich zulässt. Die Klassenwahl bleibt wörtlich
  das Muster aus `AgentHierarchyView.tsx:64`/`:98` (Vorentscheidung 1 des
  Issues); keine zweite Variante, kein Pattern Drift.
- **`grid-cols-*`:** die Domäne führt keins — das Gate aus AK 7 liefert
  weiterhin keine Zeile.

## Befund je Datei (AK 8: keine ungeprüfte Datei)

| Datei | Ergebnis |
|---|---|
| `AgentHierarchyView.tsx` | **Fund behoben** — Playbook-Zeile 32 → 40 px unterhalb `md` (`min-h-10 md:min-h-0`). `PrimaryRow` geprüft, kein Defekt. |
| `AgentDetailPage.tsx` | **geprüft, kein Defekt im Scope** — ein Primitive-Fund gemeldet (siehe unten). |
| `CopyPromptButton.tsx` | **Fund behoben** — Dropdown-Trigger 33 → 40 px breit unterhalb `md` (`w-10 md:w-auto`). |
| `DeleteAgentButton.tsx` | **geprüft, kein Defekt** — Trigger 108,9 × 40 px, Dialog 288 px innerhalb 320 px, Footer stapelt. |
| `AgentConnectorSection.tsx` | **Fund behoben** — beide Feldzeilen stapeln unterhalb `md`, Eingabefeld 95/77 → 238 px. |
| `DuplicateAgentButton.tsx` | **geprüft, kein Defekt** — 128 × 40 px. |

## Primitive-Fund — gemeldet, nicht repariert

**`components/data/DetailHeader.tsx:60` — H1 ohne `min-w-0`.**
Gemessen bei 320 px: die H1 ist 289 px breit und läuft **39,6 px** über die
`Container`-Innenkante; der Body scrollt um **24 px**. `break-words` steht seit
PR #606 an der H1, greift hier aber nicht: `overflow-wrap: break-word`
beeinflusst die `min-content`-Breite eines Flex-Kindes **nicht**, und die H1
ist mit `min-width: auto` ein Flex-Kind der Badge-Zeile — ihre Mindestbreite
bleibt die Breite des längsten Worts („Wettbewerbsbeobachtung" bei `text-2xl`).
Gegenprobe: `min-w-0` an der H1 bringt den Body-Scroll auf **0** und die H1 auf
249,5 × 96 px (drei Zeilen statt zwei); `min-w-0` an der umschließenden
Badge-Zeile allein wirkt **nicht**.

Der Fund sitzt unter `components/data/` und trifft jede Detail-Seite aller
dreizehn Domänen — laut Karte wird er gemeldet, nicht hier repariert. Er ist
**nicht** identisch mit den drei Funden aus Hälfte A (Folgekarte `t_9a9d5c66`:
`tabs.tsx`, `EntityCard`-Titel-Link, `checkbox`/`label`/`RadioGroupItem`);
dieser vierte kommt hinzu.

## Test-first

Drei neue Testfälle, vor der Änderung rot gesehen
(`3 failed | 11 passed`), nach der Änderung grün:

- `AgentHierarchyView.test.tsx` — `min-h-10` / `md:min-h-0` an beiden
  Playbook-Zeilen.
- `CopyPromptButton.test.tsx` — `w-10` / `md:w-auto` am Dropdown-Trigger.
- `AgentConnectorSection.test.tsx` — `flex-col` / `md:flex-row` /
  `md:items-center` an beiden Feldzeilen.

jsdom hat kein Layout: die Tests sind Klassen-Verträge, die Layout-Aussage
selbst steht oben gemessen.

## Verifikation

Web-Block der Definition of Done aus `CONTRIBUTING.md`, Node 22.23.2 (CI-Stand).
Ergebnisse siehe Übergabe-Bericht der Karte.
