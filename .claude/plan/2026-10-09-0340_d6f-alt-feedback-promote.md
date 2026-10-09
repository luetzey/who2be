# D6f — Alt-Feedback wird Fall (promote)

Karte t_91817c30, ADR-0053 D6f, Delta-Spec S6 + „Alt-Feedback-Anschluss“.

## Befund

- `promoteFeedback` steht schon in `api/client.ts` (D6e), `ReportCaseFlow` kennt den
  Ausgangspunkt `feedback` samt Absendeweg. client.ts und ReportCaseForm bleiben unberührt.
- Backend (`case_repository.promote_feedback`): jedes Triage-Ereignis, auch `in_progress`,
  ergibt 409 `feedback_not_promotable` („Nur ein offenes Feedback (noch nicht triagiert)“).

## Schritte

1. `FeedbackItemDetailPage.tsx`: `CaseFromOriginDialog` im Kasten „Status & Triage“ neben den
   Segmenten, nur editor/admin, nur `resolution === null`, nie bei `entity_type = system`.
   Zitat = Notiz (ohne Notiz: Signal-Label), Vorschlag `agent_id`. Nach Erfolg: Detail neu laden,
   Link „Zum Fall“ aus `created.id`, Fokus auf den Link.
2. Tests: Sichtbarkeit viewer/editor/admin, addressed/dismissed/in_progress, System; Erfolg; Fehler; axe.
3. de/en: `item.promote`, `item.promoteHelp` wörtlich. „Zum Fall“ = `learning:entries.action.toCase`.
4. Fragment `changelog.d/t-91817c30-feedback-promote.added.md`.
5. tsc, vitest, lint; Fotos + measure.json; PR.

## Abweichung (mit Beleg)

Spec: sichtbar, solange nicht `addressed`/`dismissed`. Server lehnt auch `in_progress` ab
(`case_repository.py`, `if found["resolution"] is not None: return NotPromotable`). Ein Knopf,
der garantiert 409 liefert, wäre ein Defekt → sichtbar nur bei offenem Feedback (`resolution === null`).
AK 1 bleibt erfüllt (bei addressed/dismissed nicht sichtbar). Im Handoff gemeldet.
