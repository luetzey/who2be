# Lernschleife C5a-3 (Web): Tastaturkürzel in „Zur Freigabe“

Status: aktiv · Karte t_7f8018f6 · Basis origin/main 753aa8c1 (#800, #808 gemergt)
Spec: gedaechtnisverwaltung-design-spec-2026-10.md §5.2 „Tastatur“, §14, §15, §13.2
(`decideIndividually`); Belegung „unverändert aus Spec S1“ =
lernschleife-design-spec-2026-09-28.md S1 „Tastatur“.

## Outcome
Auf `/memory?tab=approval` bedient man die Warteschlange am Desktop per
j/k/x/a/r/e/h, `?` öffnet eine Hilfe (DE/EN) mit Schalter zum Abschalten.

## Belegung (aus der Spec, nicht aus der Karte)
| Taste | Wirkung | Quelle |
|---|---|---|
| j / k | nächste / vorige Zeile | S1 |
| x | auswählen (Obergrenze 100, Hinweis wie Checkbox) | S1, §5.2 Auswahl |
| a | freigeben; bei Zurückgehaltenen, Vorschlägen (und Lernvorschlägen) nicht, Ansage „Einzeln entscheiden“ | S1 + §5.2 |
| r | ablehnen (öffnet den vorhandenen Dialog) | S1 |
| e | bearbeiten (klappt auf, Fokus ins Faktfeld) | S1 |
| h | **Verlauf** (öffnet das Detail-Sheet) | S1 — Karte nannte „zurückgehalten/Grund“, die Spec sagt Verlauf |
| ? | Hilfe | S1 |

Abweichung Karte ↔ Spec bei `h`: Spec gewinnt (Karte: „gegen die Spec prüfen“);
als Kommentar an @pm gemeldet, kein Block.

## Entscheidungen
- WCAG 2.1.4 doppelt: Kürzel hören nur auf Tasten, deren Fokus in der Liste
  liegt (Listener am Listen-Container), und sind in der Hilfe abschaltbar
  (localStorage `who2be.memory.queueShortcuts`).
- Wirkungslos in Eingabefeldern (input außer Checkbox, textarea, select,
  contenteditable), in Dialogen und mit Strg/Alt/Meta. `Esc` im Faktfeld
  springt zurück auf die Zeile.
- Unter `md` weder Kürzel noch Hilfe-Knopf (§14).
- Eine Regel für Stapelfähigkeit (`isBatchable`: nicht zurückgehalten, kein
  `lesson`) speist Checkbox **und** `x`/`a` — keine zweite Kopie.
- Aktionen laufen über die vorhandenen Knöpfe der Zeile (gleicher Codepfad
  wie Maus); zugeklappte Zeilen werden dazu aufgeklappt.
- Ansage „Einzeln entscheiden“ über den vorhandenen Toast (`role=status`).
- Hilfe-Knopf „? Tastatur“ sitzt über der Liste in `ApprovalQueue` (nicht in
  der Filterzeile der Seite), um `MemoryPage.tsx` nicht anzufassen.

## Dateien (8 inkl. Plan)
1. .claude/plan/2026-10-04-0445_lernschleife-c5a3-tastaturkuerzel.md
2. apps/web/src/features/memory/hooks/useQueueShortcuts.ts (neu: Regeln + Hook;
   als .ts statt Komponente, sonst react-refresh-Warnungen über Baseline)
3. apps/web/src/features/memory/components/ApprovalQueue.tsx (+ ShortcutsHelp)
4. apps/web/src/components/memory/MemoryRow.tsx (data-Marker, Fokusziele)
5. apps/web/src/features/memory/pages/MemoryPage.test.tsx
6. apps/web/src/i18n/locales/de.json
7. apps/web/src/i18n/locales/en.json
8. changelog.d/t-7f8018f6-memory-queue-shortcuts.added.md

## Verifikation
- Tests je Kürzel + Rot-Proben: „a auf Lernvorschlag“ (isBatchable ohne
  lesson-Prüfung → rot), „Kürzel im Suchfeld/Faktfeld wirkungslos“
  (Eingabe-Guard entfernt → rot).
- Web-DoD unter Node 22 (CONTRIBUTING §DoD): lint, tsc -b, i18n:check,
  test:coverage, build, license:check. CI all-green.

## Schritte
- [x] Code + i18n
- [x] Tests (13 neue, je Kürzel) + Rot-Proben: `isBatchable` ohne lesson-Prüfung →
      „a gibt nie einen Lernvorschlag frei“ rot; Eingabe-Guard entfernt →
      „wirkt nicht im Suchfeld/Faktfeld“ rot; Listener am document statt an der
      Liste → derselbe Test rot. Alle zurückgesetzt.
- [x] Changelog-Fragment
- [x] Web-DoD Node 22.23.3: lint 0 Fehler (90 Warnungen = Baseline), tsc -b,
      i18n:check, test:coverage 247 Dateien / 1933 Tests grün inkl. Gate, build,
      license:check; changelog_fragments check, check_code_refs 0 error
- [ ] Push, PR, CI
