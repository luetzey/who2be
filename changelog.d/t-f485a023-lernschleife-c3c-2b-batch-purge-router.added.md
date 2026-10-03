- Gedaechtnis: REST-Endpunkte `POST /memories/batch` und
  `DELETE /members/{user_id}/memories` (ADR-0053 6.4.1, Paket C3c-2b).
  `POST /memories/batch` fuehrt `approve`, `reject`, `confirm` oder `delete`
  fuer bis zu 100 `ids` aus, alternativ fuer einen `filter` wie bei
  `GET /memories` mit Pflichtfeld `expected_count`. Weicht die Trefferzahl
  ab, antwortet der Server mit 409 `memory_batch_count_mismatch` und aendert
  nichts. Je Eintrag gilt dieselbe Pruefung wie bei der Einzelaktion; die
  Antwort ist `{results: [{id, ok, reason?, params?}]}`, Teilerfolg ist
  moeglich. Zurueckgehaltene Eintraege lassen sich im Stapel nicht freigeben
  (`memory_held`). Fremdes Nutzergedaechtnis ist je Eintrag
  `memory_not_found`, auch fuer `admin`. Nennt ein `viewer`
  Agentengedaechtnis, wird der ganze Aufruf mit 403 abgelehnt.

  `DELETE /members/{user_id}/memories` loescht das gesamte Nutzergedaechtnis
  einer Person im Workspace, nur `admin`. Die Antwort ist `{deleted: n}` ohne
  Inhalt oder IDs; `audit_log` erhaelt eine inhaltsfreie Zeile
  `memory.user_purged`. Die Person muss kein Mitglied mehr sein, eine
  unbekannte Person ergibt `{deleted: 0}`.
