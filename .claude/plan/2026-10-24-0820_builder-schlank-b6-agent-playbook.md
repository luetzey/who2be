# Builder schlank B6 — Teilabruf statt Teilen (Karte t_a4b4b9f8)

Neuer Zuschnitt: PM-Entscheidung 2026-10-24 (Option b) nach M1-Messung
(`builder-schlank-2026-10-nachher.md` §1.4, §3.3, §5.2). Die 25-KB-Grenze
entfällt; der erste Zuschnitt unten ist verworfen (Commit 1e2ffbc1 im
Branch, Inhalte per Folgecommit auf main-Stand zurückgesetzt).

## Umgesetzt (Option b)
1. Profil-Laderegel `bp-p-output-load`: über der Warnschwelle
   (res-conv-h-laengen-budgets; Budgetzahlen leben nur in den Konventionen)
   erst outline, dann block_ids; geladene Konventions-Abschnitte nicht erneut holen.
2. Fall-Triage: `d7-h-wegweiser` + fertiger block_ids-Aufruf (Rahmen + ein Weg,
   Weg B + d7-h-a5).
3. Agent-PB tool_policy nur Feldbedeutung; Exklusiv-Fakten in res-conv-h-policy/-memory.
4. PB Persona lädt res-conv-h-sprache.
Nicht: Bündeln der 8 Lade-Sätze (16 Sidecars, sprengt Dateibudget 8).

## Messung DE (b6_prozedur.py, Methodik prozedur.py, gegen origin/main)
| Bau | vorher | nachher | Diff |
|---|---:|---:|---:|
| Nur Persona | 13037 | 14283 | +1246 (Sprache-Abschnitt) |
| Agent bauen, minimal | 18609 | 17345 | −1264 (−6,8 %) |
| Agent bauen, typisch | 43890 | 43872 | −18; mit Nicht-erneut-holen −1509 |
| Fall-Triage ganz | 16894 | 17393 | +499 |
| Fall-Triage Weg A / B / C | 16894 | 11481 / 12017 / 10536 | −32 / −29 / −38 % |
| Pflege, Feedback, External Tool | gleich | | 0 |
| Konsistenz | 14128 | 14179 | +51 |
| Profil | 3241 | 3460 | +219 |

## Verworfener erster Zuschnitt (Historie)

# Builder schlank B6: Agent-Playbook entschlacken, Agenten-Bau ≤ 25 KB (K6)

Kanban: t_a4b4b9f8 (Eltern t_e8518965 / PR #1073, gemergt cb1c6547). Grundlage:
Recherche `builder-schlank-2026-10.md` K6, Owner-Entscheidung 2026-10-22
(15–25 KB je Bau), ADR-0063 (Playbook 1 000 / 1 500 Wörter).

## Ziel (messbar)

- Agenten-Bau (Persona-Playbook + Agent-Playbook + deren Standard-Abschnitte
  der Konventionen) DE und EN ≤ 25 KB Klartext, gemessen wie im B3-Review
  (`blocks_plain_text`, `section_blocks`). Vorher DE 31 646 B, EN 30 488 B.
- Auch mit dem Bedarfs-Abschnitt „Templates verfassen“ ≤ 25 KB.
- Alle Verbote und Pflichten erhalten (abgehakte Liste im PR-Text).
- `BUILDER_CONTENT_VERSION` 22 → 23, Sync-Test mit Stempel-Literal 22 (Rot-Probe).

## Analyse Agent-Playbook (DE, Bytes Klartext)

| Abschnitt | B | Art |
|---|---:|---|
| Zweck + Konventionen | 612 | Ablauf |
| Template waehlen oder verfassen | 792 | Nachschlagen (Template-Schreibweg) |
| Placeholder-Authoring | 2 219 | Nachschlagen (nur beim Verfassen) |
| Modus erkennen | 656 | Dublette der Modus-Abschnitte |
| Create (4 Phasen) | 2 995 | Ablauf |
| Update / Copy / Deaktivieren | 1 846 | Ablauf |
| tool_policy verstehen | 2 730 | Nachschlagen, ~60 % doppelt zu res-conv-h-policy/-memory |
| Aktivierbarkeit | 512 | Nachschlagen |
| Fallen / Anti-Patterns / Notes | 2 175 | teils doppelt zu den Phasen |

## Entscheidung (Muster)

Nachschlagewissen in Konventions-Abschnitte, nicht in ein Composite-Playbook:
B3 hat den Abschnitts-Abruf per Anker eingeführt, ein Composite würde Katalog
und Trigger ändern (W3: höchstes Befolgungs-Risiko). Kompaktere Alternative
(nur kürzen, nichts verschieben) reicht nicht für ≤ 25 KB, ohne Regeln zu
streichen.

- Neu `res-conv-h-templates` (DE/EN, Ebene 2): Template-Schreibweg +
  Platzhalter-Regeln + Beispiel. Lädt das Playbook nur, wenn keine bestehende
  Template passt.
- Neu `res-conv-h-agent-policy` (DE/EN, Ebene 3 unter `res-conv-h-policy`)?
  Nein: die nicht doppelten Policy-Fakten (Default lesen/nicht schreiben,
  An/Aus-Scopes, memory-Stufen read_only/off) wandern als Sätze in die
  bestehenden Abschnitte policy/memory, die der Agent-Bau ohnehin lädt.
- Standard-Anker Agent: `res-conv-h-policy`, `res-conv-h-memory`
  (`res-conv-h-managed` und `res-conv-h-templates` nur bei Bedarf, genannt im
  Konventions-Absatz).
- Playbook: Modus-Liste als ein Satz, Phasen bleiben, Aktivierbarkeit in einen
  Absatz, Anti-Patterns ohne Wiederholung der Phasen, Notes in den Ablauf.

## Schritte

1. Vorher messen (erledigt, s. o.).
2. Sidecars per Skript umbauen (Format roundtrip-identisch), DE und EN mit
   identischen Block-IDs; Resource um `res-conv-h-templates` ergänzen.
3. `BUILDER_CONTENT_VERSION` 23 + Kommentar; Changelog-Fragment.
4. Tests: Anker-Erwartung Agent, tools-overview-/Beispiel-Tests auf den
   Resource-Abschnitt, Sync v23 (Literal 22), alte Sync-Erwartung
   `pb-agent-*-placeholder` angepasst.
5. DoD aus CONTRIBUTING, nachher messen, PR mit Tabelle und Pflichtenliste.

## Ergebnis (Klartext-Bytes, gemessen wie B3-Review)

| Agenten-Bau | vorher | nachher | + Bedarfs-Abschnitt templates |
|---|---:|---:|---:|
| DE | 31 646 | 22 703 | 24 986 |
| EN | 30 488 | 22 089 | 24 295 |

Agent-Playbook allein: DE 14 689 → 5 763 B (1 838 → 730 Wörter), EN 13 941 →
5 587 B. Test `test_agent_build_stays_within_owner_budget` haelt ≤ 25 KB inkl.
Template-Abschnitt und ≤ 1 000 Wörter (Rot-Probe mit altem Playbook: 34 776 B).

## Nicht-Ziele

Andere Playbooks (Persona-Playbook bleibt, obwohl es mitgemessen wird),
persona-ref-Resolver, Trigger/Namen/Beschreibung des Agent-Playbooks.
