- Die Links in den Mails für Registrierung, E-Mail-Wechsel und
  Passwort-Zurücksetzen führen wieder in die Web-App.

  GoTrue setzt den Link aus `API_EXTERNAL_URL` (`https://supabase.<DOMAIN>`)
  und dem jeweiligen `GOTRUE_MAILER_URLPATHS_*` zusammen, nicht aus
  `SITE_URL`. Unter dieser Adresse beantwortet GoTrue nur `/auth/v1/*`; die
  bisherigen Werte `/auth/callback` und `/onboarding/set-password` liefen dort
  in ein 404. `CONFIRMATION`, `EMAIL_CHANGE` und `RECOVERY` stehen jetzt wie
  `INVITE` auf `/auth/v1/verify`. GoTrue prüft dort den Link und leitet mit
  angemeldeter Sitzung auf die Web-Seite weiter, die der Aufruf als Ziel
  mitgegeben hat (`/auth/callback`, `/onboarding/set-password`,
  `/invitations`), ohne Ziel auf `SITE_URL`.

  Betroffen sind `deploy/hetzner/supabase/docker-compose.yml`,
  `deploy/dokploy/docker-compose.yml` und das lokale Cloud-Overlay
  `docker-compose.cloud.yml`; die vier Werte sind in allen drei Dateien gleich.
  Wer die Compose-Datei selbst pflegt, muss die Werte nachziehen.
