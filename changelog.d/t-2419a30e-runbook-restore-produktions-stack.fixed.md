- Restore, Tabellen-Store-Diagnose und SeaweedFS-Betrieb im Hetzner-Runbook
  sprechen jetzt den Produktions-Stack an.

  Dort standen noch nackte Aufrufe wie `docker compose exec db psql …`,
  `docker compose exec -T db pg_restore …` oder
  `docker compose exec api …`. Ohne `-f` liest `docker compose` in
  `/opt/who2be` die Root-`docker-compose.yml`, also den lokalen Dev-Stack.
  Restore und Diagnose trafen so den falschen Container oder gar keinen.
  Die Aufrufe auf `db` laufen jetzt über den Supabase-Stack
  (`-f deploy/hetzner/supabase/docker-compose.yml --env-file
  deploy/hetzner/supabase/.env`). Die Aufrufe auf `api`, `seaweedfs` und
  `blobstore-bootstrap` laufen über den App-Stack mit denselben `-f`- und
  `--env-file`-Argumenten wie `deploy/hetzner/scripts/deploy.sh`, für die
  Cloud-Edition mit Overlay. Die Abfragen nennen außerdem die richtige
  Produktions-Datenbank `postgres` statt `who2be`. Der Smoke nach dem Deploy
  listet den beendeten One-Shot `blobstore-bootstrap` jetzt mit `ps --all`.
  Erklärende Erwähnungen im Fließtext stehen in der Auslassungsform
  `docker compose … <befehl>`.
