# Backlog-Aufbereitungslauf 26 — luetzey/who2be

**Datum:** 2026-09-20 · **Basis:** `main` @ `69bfeda` · **Vorlauf:** Lauf 25 (2026-09-19, `fd53b01`)
**Playbook:** Issue-Refinement (290b0c4f) · **Norm:** Agent-ready Arbeitspaket (73a86231)

## Auftrag

1. Jedes offene Issue gegen die Norm "Agent-ready Arbeitspaket" pruefen.
   Belegtes selbst entscheiden und mit Beleg ins Issue; Urteilsfragen als
   Kommentar mit drei Optionen + Empfehlung, Issue auf `needs-decision`.
2. Warteschlange (`backlog-queue`, #442) neu ordnen: harte Abhaengigkeit >
   Owner-Vorgabe > Fundament vor Flaeche > Inventar vor Zuschnitt > bei
   Gleichstand das kleinere. Dazu Wellen (datei-disjunkt + stack-getrennt).
3. Bericht in drei Bloecken: selbst erledigt / braucht Owner-Antwort /
   Reihenfolge + Wellen.

## Ausgangslage (gelesen, nicht angenommen)

17 offene Issues. Davon:

- **Neu am 2026-09-19, nie durch Refinement:** #535 (Tracking Cloud-Haertung)
  mit Kindern #536-#540, dazu #541 (Backup) und #542 (Rechnung, `human-only`).
- **Bestand:** #520, #517 (`agent-ready`), #499, #428, #431, #435, #442,
  #454, #338.
- Lauf 25 (2026-09-19) hat die acht neuen Issues als Kommentar an #442
  vermerkt, aber **nicht** in den Body eingetragen — Begruendung dort:
  Body-Kapazitaet.
- `human-only` → Lauf endet dort (Playbook Schritt 1): #542, #454, #338.

## Leitfund dieses Laufs

**`main` hat sich bewegt — erstmals seit Lauf 17.** `fd53b01` → `69bfeda`,
20 Commits, 27 Dateien, **+120 Zeilen in `.github/workflows/ci.yml`**.

Konsequenz: die acht neuen Issues sind auf `8411173` gemessen, das Queue-Issue
auf `fd53b01`. **Jede zitierte `ci.yml`-Zeilennummer in jedem Issue und in
#442 ist damit unbelegt**, bis sie neu gemessen ist (Regel 16 + Regel 43 +
Vorschlag Regel 58 aus Lauf 24: "die Zeiger wandern").

Das ist kein Nebenbefund: die Verifikations-Bloecke sind das kritischste
Pflichtfeld der Norm, und ein Zeiger auf die falsche Zeile ist genau der
Fall, vor dem das Anti-Pattern "Verifikations-Kommandos erfinden" warnt.

## Zweiter Fund: die Kapazitaets-Blockade loest sich durch das Playbook selbst

Lauf 22-25 fuehren "was weicht aus diesem Body?" als **Owner-Urteil**, weil
Verdichten Verlust waere: 22 von 28 Historien-Eintraegen existieren nur im
Body. Lauf 25 schliesst daraus: "Lauf 26 kann diesen Body nicht mehr
aktualisieren" (23 Zeichen Reserve nach dem Lauf-25-Edit).

**Nachgemessen: 65.178 von 65.536 Zeichen, 358 frei — die Rechnung haelt.**

Aber die Praemisse der Frage haelt nicht mehr, sobald Schritt 5 des
Refinement-Playbooks angewandt wird: er verlangt ohnehin, den bisherigen Body
**woertlich als Kommentar zu archivieren, BEVOR** er ersetzt wird. Nach dieser
Archivierung ist Verdichten kein Verlust, sondern ein Umzug — und genau das
ist Schritt 1 von Option B'.

Damit ist die Blockade **belegt aufloesbar, ohne die Owner-Frage zu
praejudizieren**: das Archiv entfernt nichts und verbraucht keine der drei
Optionen. Was weiterhin Urteil bleibt, ist die Dauerform (A/B'/C) — die geht
als Frage an den Owner.

Historien-Block gemessen: **8.916 Zeichen** — das ist der Verdichtungsraum.

## Arbeitspakete (Sub-Agents, datei-disjunkt, alle read-only)

| WP | Inhalt | Modell | Begruendung |
|---|---|---|---|
| WP-1 | Repo-Fakten neu messen auf `69bfeda`: alle `ci.yml`-Jobzeilen, Web-Gates (lint/tsc -b/test:coverage), Python-Suite inkl. `collected`, GoTrue-Pins, Docker-Daemon | sonnet | mechanisch, Kommandos stehen fest |
| WP-2 | Norm-Pruefung + Zeiger-Verifikation #536, #537, #538 (Backend-Cluster) | sonnet | Lesen + grep gegen benannte Dateien |
| WP-3 | Norm-Pruefung + Zeiger-Verifikation #539, #540, #541 (Infra-Cluster) | sonnet | dito |
| WP-4 | Norm-Pruefung Bestand: #520, #517, #499 — halten die Angaben auf `69bfeda`? | sonnet | Nachmessung bekannter Zahlen |
| WP-5 | Tracking-Issues #428, #431, #435, #535 — Ist-Zustand gegen Body (Regel 22) | sonnet | Zaehlen + abgleichen |

Alle Sub-Agents: **read-only**, kein git-Schreibbefehl, kein Branch, kein
Issue-Write (Regel 30/45, Playbook-Anti-Pattern "Code anfassen").
Die Triage (entscheidbar vs. needs-decision) bleibt beim Orchestrator.

## Danach (Orchestrator)

- Konsolidieren: welche Issue-Bodys brauchen eine Korrektur, welche Weiche
  ist belegt, welche braucht Urteil.
- Body-Korrekturen: Original vorher als Kommentar archivieren (Schritt 5).
- #442 neu ordnen. **Kapazitaets-Warnung beachten:** der Body stand in Lauf 24
  bei 65.178 von 65.536 Zeichen — 358 frei. Ersetzen, nicht anhaengen.
- Bericht in den drei geforderten Bloecken.

## Was dieser Lauf NICHT tut

- Kein Code, kein Branch, kein PR im Produktivcode (Refinement-Playbook).
- Kein `agent-ready` ohne einzeln abgehakte Pflichtfelder.
- Keine Weiche entscheiden, die Urteil braucht (Produktzahlen der Tarife).
- Kein Zuschnitt von `size/M` (Regel 7 — das waere Projekt-Blueprint).
