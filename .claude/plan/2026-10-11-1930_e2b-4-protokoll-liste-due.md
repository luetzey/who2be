# E2b-4: Protokoll-Liste — due-Filter und Zeilenzaehler (QE2)

Karte t_5a9b471c. Status: umgesetzt, PR #942 offen (Review-Runde 2: Testluecken M8/M13 geschlossen).

## Ziel
`GET /feedback-sessions` liefert `due=true` und je Zeile `case_count`,
`measure_count`, `next_follow_up_at`, `due_measure_count`, `superseded_by_id`
(Modell `SessionListItem`).

## Schritte
1. Repository: Faellig-Regel als SQL-Bausteine (`_MEASURE_FOLLOW_UP_SQL`,
   `_MEASURE_OPEN_SQL`, `_MEASURE_LAST_EVENT_JOIN`) — eine Quelle fuer
   `count_due_measures`, `lock_measure` und `list_sessions`.
2. `list_sessions(today, due)` -> `SessionListItem`, Zaehler per LATERAL-Aggregat
   in derselben Abfrage (kein N+1), `due` als WHERE auf dem Aggregat (Cursor bleibt).
3. Service: `today`-Injektion wie `MeasureService` (`_today_utc`), `due` durchreichen.
4. Router: Query `due: bool = False`, Rueckgabe `list[SessionListItem]`.
5. Tests: Service (gestern/heute/morgen, Endzustand, Zaehler, Mandant, Cursor),
   Router (due, Felder, Cursor).
6. openapi.json + Surface-Golden regenerieren, Changelog-Fragment.
7. Review-Runde 1: Endzustand nach Zwischen-Events (activated -> reviewed,
   draft_linked -> withdrawn) und zwei Korrekturen (juengste gewinnt) im
   Service-Test; nur Tests, Produktivcode unveraendert.

## Festlegungen
- `next_follow_up_at` = fruehestes Nachschau-Datum (Massnahme, sonst Protokoll)
  der offenen Massnahmen; None, wenn keine offen ist.
- `superseded_by_id` = juengstes Protokoll mit `supersedes_id = id`.
