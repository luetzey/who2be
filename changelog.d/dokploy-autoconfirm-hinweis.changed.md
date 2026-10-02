- Dokploy-Compose und Doku nennen jetzt, wofür der Default
  `GOTRUE_MAILER_AUTOCONFIRM=true` gedacht ist: On-Prem-Betrieb ohne
  Mailversand, lokal oder im vertrauenswürdigen Netz.

  Mit Autoconfirm gilt eine registrierte Adresse ohne Besitznachweis als
  bestätigt, und die offenen Einladungen hängen an dieser Adresse. Eine
  öffentlich erreichbare Instanz braucht `false` und echten SMTP
  (`docs/signup-and-invites.md`, Abschnitt „Self-Hosting ohne Mailversand";
  `docs/oauth-e2e-dokploy.md`, Schritt 3).
