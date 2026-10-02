- Dokploy-Compose reicht `GOTRUE_SMTP_*` jetzt optional an den `auth`-Dienst
  durch (leere Defaults, `GOTRUE_SMTP_PORT` mit Default `587`). Eine
  öffentlich erreichbare On-Prem-Instanz setzt `GOTRUE_MAILER_AUTOCONFIRM=false`
  und SMTP allein über die Dokploy-Environment; ohne Angaben läuft der Stack
  wie bisher ohne Mailversand.

  Das Dokploy-Cloud-Overlay setzt `GOTRUE_MAILER_AUTOCONFIRM` per Default auf
  `false` — in der Cloud ist Mailversand Pflicht (Override auf `true` nur für
  einen Solo-Smoke). `docs/cloud-erstinbetriebnahme.md` führt den SMTP-Zugang
  entsprechend als Vorbereitungspunkt.
