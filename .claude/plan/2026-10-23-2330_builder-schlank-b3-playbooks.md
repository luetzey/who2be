# Builder schlank B3: Playbooks entdoppeln + Konventionen abschnittsweise laden

Kanban: t_e8518965 (Eltern t_f6b45d89, t_7dbe0608). Grundlage: Recherche
`builder-schlank-2026-10.md` §5.4 K1–K4, Owner-Entscheidung 2026-10-22 (W3 b),
PM-Entscheidungen 2026-10-22 (tools-overview, Pflichtgliederung) und 2026-10-23
(Weg A als Vorkarte t_7dbe0608 / PR #1071).

## Ziel (messbar)

- Alle acht Builder-Playbooks, DE und EN: kein Feedback-Absatz (K1), „Tools &
  Operations“/„Werkzeuge“ wird „Fallen“ mit nur nicht offensichtlichen Fallen
  (K2), „Zweck“ ein Satz (K3).
- K4: jedes Playbook enthaelt genau einen Aufruf
  `fetch_resource(resource_id, block_ids=[...])` mit 2–4 Ueberschriften-Ankern
  der Agent-Bau-Konventionen; jeder Anker existiert (Test, Rot-Probe).
- Keine Trigger, Namen, Tags oder Beschreibungen geaendert.
- Typischer Bau DE statt 27–33 KB etwa 12–16 KB Prozedur (gemessen im PR-Text).

## Schritte

1. Vorher messen (Bytes JSON/Text/Woerter je Playbook). Erledigt.
2. Sidecars per Skript umbauen (Block-Operationen, Format roundtrip-identisch),
   DE und EN mit identischen Block-IDs.
3. Agent-Playbook: tools-overview standardmaessig nicht ins Template, Beispiel
   ohne tools-overview, memory-Hinweis angepasst.
4. Playbook-Playbook: Bauanleitung ohne Pflichtabschnitte Zweck/Tools, nur
   „Fallen“, wenn es welche gibt.
5. `BUILDER_CONTENT_VERSION` 21 -> 22 + Kommentar; Changelog-Fragment.
6. Tests: Anker-Test (Rot-Probe), K1/K4-Test, Agent-/Playbook-Lehre, Sync v22
   (Stempel-Literal 21), Erwartungen im Sync-Test angepasst.
7. DoD aus CONTRIBUTING.
8. Nachher messen, PR mit Tabelle und Mutationsliste.

## Nicht-Ziele

Playbooks teilen (K6), Fach-Templates, Resolver-Sprache von persona-ref
(offen, eigene Karte durch den PM), Konventions-Resource selbst.

## Abhaengigkeit

K4 wirkt erst mit PR #1071 (fetch_resource schneidet Ueberschriften-Anker auf
ihren Abschnitt). Merge-Reihenfolge: #1071 vor diesem PR.
