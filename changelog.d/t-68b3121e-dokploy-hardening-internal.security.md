- Die API sperrt den internen Bereich `/v1/internal` selbst, und der
  Dokploy-Stack ist gehärtet wie der Hetzner-Stack.

  Vor dem Dokploy-Stack steht Traefik ohne Sperr-Regel für `/v1/internal`
  (ADR-0010); Anfragen von außen erreichten die App. Eine neue Middleware
  (`InternalAreaGuard`) antwortet dort jetzt mit `403` — in jeder Schreibweise
  (doppelte Schrägstriche, Groß/Klein, Prozent-Kodierung) und unabhängig vom
  Proxy davor. Durch kommt nur der direkte Zugriff aus dem Container-Netz ohne
  Proxy-Header. Alle Dienste des Dokploy-Stacks (Basis und Cloud-Overlay)
  tragen jetzt Log-Rotation, `no-new-privileges` und ein `mem_limit`;
  `test_compose_hardening.py` zählt das ab und prüft, dass kein Dienst einen
  Host-Port veröffentlicht. Betrieb und Prüfschritte: RUNBOOK §Dokploy-Stack.
