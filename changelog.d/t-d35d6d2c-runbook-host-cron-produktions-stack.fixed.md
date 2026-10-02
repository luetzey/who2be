- Die Host-Cron-Zeilen für Backup und `who2be-purge` im Hetzner-Runbook
  sprechen jetzt den Produktions-Stack an.

  Bisher standen dort nackte Aufrufe der Form
  `cd /opt/who2be && docker compose run --rm api who2be-purge` bzw.
  `docker compose --profile backup run --rm backup`. Ohne `-f` liest
  `docker compose` in `/opt/who2be` die Root-`docker-compose.yml`, also den
  lokalen Dev-Stack. Der Purge lief so nicht gegen die Produktions-DB, und der
  Backup-Cron brach mit „no such service“ ab, weil die Root-Compose keinen Dienst
  `backup` kennt. Die Zeilen tragen jetzt dieselben `-f`- und
  `--env-file`-Argumente wie `deploy/hetzner/scripts/deploy.sh`. Es gibt je eine
  Zeile für On-Prem und für Cloud mit Overlay; der Purge läuft mit `--no-deps`.
  Dazu kommen das Anlegen der Log-Datei unter `/var/log` und eine Verifikation.
  Erstlauf, Alarmweg-Test, Diagnose und der Handauslöser nutzen dieselbe Form.
  Checklistenpunkt 7b deckt jetzt alle drei Host-Crons ab und erkennt eine
  nackte Zeile. Der Kommentar in `backup.sh` und der Kommentar am Dienst
  `backup` im Hetzner-Compose sind nachgezogen.

  **Betreiber:** Wer die alten Zeilen schon eingetragen hat, ersetzt sie durch
  die Zeile seiner Edition aus `deploy/hetzner/RUNBOOK.md`.
