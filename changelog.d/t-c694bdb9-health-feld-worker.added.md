- Health: `GET /v1/health` liefert das Feld `worker` (ADR-0057 §7). Es steht
  auf `ok`, solange der jüngste Worker-Heartbeat höchstens fünf Minuten alt
  ist, auf `stale`, wenn er älter ist, und auf `unknown`, wenn es keinen
  Heartbeat gibt, die Datenbank nicht erreichbar ist oder die Abfrage länger
  als 1,5 Sekunden braucht (etwa bei einem Lock auf `worker_heartbeat`). Das
  Feld ist ein Dead-Man-Signal ohne UI. `status` bleibt `ok` und die Antwort
  200, auch wenn der Worker steht.
