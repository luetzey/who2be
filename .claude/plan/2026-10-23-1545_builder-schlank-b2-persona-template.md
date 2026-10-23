# Builder schlank B2: Builder-Persona straffen + Werkzeug-Block aus dem Builder-Template

Kanban: t_f6b45d89 (Eltern t_547b7bfd). Grundlage: Recherche
`builder-schlank-2026-10.md` §5.4 K5/K7, Owner-Entscheidung 2026-10-22 (W2, W3 b, W5 a).

## Ziel (messbar)

- Inhalts-Startlast Builder (Profil-Text + Modi-Text, wie `get_persona` sie
  rendert) DE von 8 391 B auf <= 6 144 B; Profil <= 600 Woerter (Warnschwelle),
  jeder Modus <= 250 Woerter.
- Gerendertes Builder-Template (`/rendered`) ohne `tools-overview`, Profil per
  `persona-ref` statt `persona-field:profile`; keine offenen Platzhalter.
- Builder-Lite unveraendert.

## Schritte

1. Vorher messen (Skript im Scratch: `persona_content_text` + `/rendered`). Erledigt.
2. Persona-Profil DE/EN: „Erlaubt“ auf drei Faehigkeits-Saetze; Vier-Phasen nur
   im Output-Stil (Auskunft ohne Phasen dorthin verschoben); Abschnitt „Modi“
   im Profil entfaellt (doppelt zur Modi-Sektion von `get_persona`);
   Beziehungs-Denken ohne Pflege-Verweis (steht im Kurator-Modus); Verboten
   gestrafft, alle sechs Punkte bleiben.
3. Modi DE/EN: Architekt ohne Phasen-Wiederholung; Kurator/Berater gestrafft,
   Anti-Patterns vollstaendig.
4. Template DE/EN: `ab-h6`/`ab-p7` (Werkzeuge) raus, `ab-p2` auf `persona-ref`.
5. `BUILDER_CONTENT_VERSION` 20 -> 21 + Kommentar; Changelog-Fragment.
6. Tests: Budget-Test (Bytes/Woerter), Template-Pills-Test, Sync-Test v21
   (Stempel-Literal 20, Rot-Probe ohne Bump).
7. DoD: ruff, format, mypy, pytest mit Coverage.
8. Nachher messen, PR mit Vorher/Nachher-Tabelle, Checkliste tragender Regeln,
   Mutationsliste.

## Nicht-Ziele

Playbooks (B3), Fach-Templates, Lite-Template, Resolver-Texte (persona-ref
rendert nur Deutsch, wie heute schon memory/tools-overview).
