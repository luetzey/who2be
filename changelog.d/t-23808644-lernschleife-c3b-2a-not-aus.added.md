- Gedaechtnis: Not-Aus fuer automatisch aktivierte Eintraege auf der
  Service-Ebene (ADR-0053 6.4.1, Paket C3b-2a). Aktive, unbestaetigte Eintraege
  mit einem Ereignis `auto_activated` im gewaehlten Zeitraum gehen zurueck nach
  `pending` und bekommen je Eintrag das Ereignis `auto_revoked`. Geloescht wird
  nichts, und ein Rollback auf dieses Ereignis stellt den vorherigen Stand her.

  Eine Vorschau (`dry_run`) nennt die Anzahl und hoechstens fuenf sichtbare
  Eintraege. Ohne Vorschau ist die bestaetigte Anzahl Pflicht. Weicht sie ab,
  antwortet der Server mit 409 `memory_batch_count_mismatch` (`params={count}`)
  und aendert nichts. Die Ruecknahme ist atomar: alle oder keiner.

  Die Ruecknahme verlangt die Rolle `editor`. Das Nutzergedaechtnis anderer
  Personen schliesst nur `admin` ein (`include_other_users`); er sieht davon
  nur die Anzahl (`hidden_count`), nie Inhalt oder ID. Der REST-Endpunkt
  `POST /memories/revoke-auto` folgt mit C3b-2b.
