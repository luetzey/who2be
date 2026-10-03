- Gedaechtnis: Sammelaktionen und Loeschen des Nutzergedaechtnisses einer
  Person auf der Service-Ebene (ADR-0053 6.4.1, Paket C3c-2a). Ein Stapel gibt
  frei, lehnt ab, bestaetigt oder loescht. Die Auswahl ist entweder eine Liste
  von hoechstens 100 IDs oder ein Filter wie in der Gedaechtnis-Liste. Im
  Filter-Modus muss die bestaetigte Anzahl (`expected_count`) mitkommen. Weicht
  die Trefferzahl ab, aendert sich nichts und der Grund ist
  `memory_batch_count_mismatch`.

  Jeder Eintrag durchlaeuft dieselbe Pruefung wie die Einzelaktion. Ein Fehler
  bricht den Stapel nicht ab, sondern steht im Ergebnis dieses Eintrags.
  Zurueckgehaltene Eintraege werden nur einzeln freigegeben; im Stapel ergeben
  sie den neuen Grund `memory_held`. Das Nutzergedaechtnis anderer Personen ist
  je Eintrag `memory_not_found`, auch fuer `admin`.

  Ein `admin` kann das gesamte Nutzergedaechtnis einer Person im Workspace
  loeschen. Er sieht dabei nur die Anzahl, nie den Inhalt; das Audit-Log
  bekommt eine inhaltsfreie Zeile `memory.user_purged`. Die REST-Endpunkte
  `POST /memories/batch` und `DELETE /members/{user_id}/memories` folgen mit
  C3c-2b.
- Gedaechtnis: Die Freigabe eines Lernvorschlags (`lesson`) endet jetzt mit 409
  `memory_transition_invalid` statt mit einem Serverfehler.
