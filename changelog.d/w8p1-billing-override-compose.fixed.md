- Die Betreiber-Allowlist `WHO2BE_BILLING_OVERRIDE_OPERATORS` kommt jetzt im
  `api`-Container an, und die Cloud-Smoke-Anleitungen fuehren nicht mehr in
  einen garantierten 403.

  Die Variable stand in keinem der drei Cloud-Overlays unter
  `api.environment` — der Override-Endpoint ist fail-closed, also antwortete
  der als Default beworbene Weg „Pro ohne Mollie setzen" zwangslaeufig mit
  `403`, egal was in der `.env` stand. Alle drei Overlays (Hetzner, Root-Stack,
  Dokploy) reichen sie nun als
  `${WHO2BE_BILLING_OVERRIDE_OPERATORS:-}` durch (leerer Default, fail-closed
  bleibt), `deploy/hetzner/.env.example` erklaert Format und Wirkung, und ein
  daemonfreier Test haelt die Verdrahtung fest.

  `docs/cloud-prod-smoke.md` §4 Variante A und die RUNBOOK-Bring-up-Checkliste
  nennen jetzt die drei echten Vorbedingungen des Endpoints — Rolle `admin`,
  **Web-JWT mit `aal2`** (TOTP-Step-up vorab; API-Tokens `w2b_…` sind
  kategorisch ausgeschlossen) und den Eintrag in der Allowlist. Neu sind
  ausserdem drei knappe Smoke-Bloecke fuer die Tarif-Quoten Speicher (#536),
  Tokens (#538) und Workspaces (#576) mit erwartetem `402` und `reason`.
