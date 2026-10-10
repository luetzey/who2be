- Betreiber der Instanz: Die neue Variable `WHO2BE_OPERATORS` (kommaseparierte
  User-UUIDs) legt fest, wer Betriebsdaten wie die Hintergrund-Routinen des
  Workers sehen darf (ADR-0057 §7, Nachtrag 2026-10-10). Sie gilt in Cloud und
  On-Prem. Leer oder nicht gesetzt heißt: niemand. API-Tokens sind nie
  Betreiber. Alle drei Compose-Stacks reichen die Variable an `api` durch, und
  `deploy/hetzner/.env.example` bietet sie an. Die Override-Allowlist
  `WHO2BE_BILLING_OVERRIDE_OPERATORS` bleibt unverändert und eine eigene Liste;
  sie nutzt jetzt denselben Parser.
