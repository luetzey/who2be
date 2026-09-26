- **Verhaltensaenderung:** Der Text von WorkArea-Artifacts zaehlt in der Cloud
  jetzt in die Speicher-Quota — Bestandsnutzer haben damit effektiv weniger
  Platz als vorher.

  Bisher zaehlte die Speichergrenze nur die abgelegten Dateien
  (`wa_blob.size_bytes`); Artifact-Text fiel unter kein Kontingent. Jetzt gilt
  ein Limit fuer alles: Artifact-Text zaehlt wie eine Datei, es gibt kein
  zweites Kontingent fuer Artifacts. Gezaehlt werden Bytes (UTF-8), nicht
  Zeichen; bei `append` der Zuwachs, und ein Loeschen oder ein schrumpfender
  Patch gibt Platz wieder frei. Vorhandene Artifacts zaehlen ab dem Deploy mit
  (Backfill in Migration 0087).

  Durchgesetzt an allen Schreibpfaden, die Speicher entstehen lassen:
  `POST /work-areas/{id}/artifacts`, `POST /artifacts`,
  `POST /wa-artifacts/{id}/append`, `PATCH /wa-artifacts/{id}`,
  `POST /wa-tables/{id}/save-result` und den beiden Ingest-Routen. Wer durch die
  Neuzaehlung ueber seiner Grenze liegt, verliert nichts und wird nicht
  ausgesperrt: Lesen, Exportieren, Herunterladen und Loeschen bleiben offen —
  Loeschen ist der Weg zurueck unter die Grenze. Abgewiesen werden nur NEUE
  Schreibzugriffe (`402`, `reason: storage_quota_exceeded`, Grenze und
  Verbrauch in `params`). On-Prem und OSS bleiben unbegrenzt.
