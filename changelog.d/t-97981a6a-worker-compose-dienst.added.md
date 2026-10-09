- Worker: Compose-Dienst `worker` in allen Deploy-Varianten (ADR-0057, Paket
  P3). Er läuft in lokal, Dokploy und Hetzner sowie in deren Cloud- und
  Image-Overlays mit demselben Image wie `api` und dem Befehl `who2be-worker`.
  Die Umgebung entspricht den bisherigen Purge-Läufen: Owner-Verbindung,
  BlobStore, Tabellen-Store-Volume und GoTrue-Service-Key in der Cloud. Der
  Healthcheck ist `who2be-worker check`. Mit `stop_grace_period: 65m` bricht
  Docker beim Stopp keinen laufenden Purge ab, dessen Timeout bei einer
  Stunde liegt.

  Es läuft genau ein Worker (ADR-0057 §10). `deploy/hetzner/scripts/deploy.sh`
  bricht nach dem `up` ab, wenn nicht genau ein `api`- und genau ein
  `worker`-Container läuft, und zieht das Worker-Image vorab mit. Ein
  Drift-Test schlägt fehl, wenn `worker` in einer Deploy-Compose fehlt,
  doppelt steht, skaliert wird oder ein anderes Image als `api` bekommt.
  Die Retention- und Verfalls-Zeitpläne außerhalb des Repos (Host-Crontab,
  Dokploy-Schedules) bleiben vorerst bestehen. Doppelte Läufe verhindert der
  Slot-Claim.
