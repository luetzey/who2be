- Die Hintergrundjobs `who2be-purge` und `who2be-memory-expire` haben jetzt
  eine Anleitung für Dokploy.

  Bisher standen beide nur als Host-Crontab im Hetzner-Runbook. Eine Instanz
  aus `deploy/dokploy/docker-compose.yml` hat keine solche Crontab, dort lief
  also weder der DSGVO-Purge noch der Verfall unbestätigter
  Gedächtnis-Einträge nach 30 Tagen (ADR-0053 3.1.3).
  `docs/cloud-erstinbetriebnahme.md` beschreibt jetzt im Abschnitt
  „Hintergrundjobs auf Dokploy einplanen“ je Job einen Dokploy-Schedule im
  Dienst `api`, mit Befehl, Zeitplan (03:30 bzw. 03:45 UTC wie auf Hetzner),
  Log-Ort, Verifikation nach dem ersten Lauf und Rückweg. Belegt ist das mit
  der Dokploy-Doku „Schedule Jobs“ und dem Dokploy-Quelltext. Die
  Inbetriebnahme-Checkliste hat dafür den Punkt 10b. Hetzner-Runbook und
  `docs/oauth-e2e-dokploy.md` verweisen auf den neuen Abschnitt.

  **Betreiber einer Dokploy-Instanz:** beide Schedules einmalig anlegen, sonst
  laufen die Jobs nicht.
