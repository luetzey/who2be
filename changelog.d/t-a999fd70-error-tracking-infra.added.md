- Die Compose-Stacks (Hetzner, Dokploy, lokal) reichen das Fehler-Tracking
  jetzt an API, MCP-Server und Web-App durch: `SENTRY_DSN_API`,
  `SENTRY_DSN_MCP`, `SENTRY_DSN_WEB` und `SENTRY_ENVIRONMENT`, alle mit leerem
  Default. Ohne Wert bleibt das Fehler-Tracking aus. Tracing wird nicht
  durchgereicht.

  Neu im Caddy-Stack ist `ERROR_TRACKER_ORIGIN`. Ist der Wert gesetzt, kommt
  die Origin des Trackers in `connect-src` der Web-App, damit der Browser
  Fehler-Events senden darf. Ohne Wert bleibt die CSP Byte für Byte gleich.
  Im Dokploy-Stack trägt man die Origin in die Traefik-Middleware ein
  (RUNBOOK §Dokploy-Stack). Einrichtung und Prüfung stehen im RUNBOOK unter
  „Fehler-Tracking an Prod anschliessen“.
