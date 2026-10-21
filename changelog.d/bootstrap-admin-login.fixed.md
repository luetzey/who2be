- On-Prem-Bootstrap: Der erste Login des Bootstrap-Admins
  (`WHO2BE_BOOTSTRAP_ADMIN_EMAIL`) landet jetzt in der beim ersten Boot
  geseedeten Organisation und wird dort Owner bzw. Workspace-Admin. Bisher
  bekam der Login eine eigene, leere Personal-Org, und niemand verwaltete die
  Bootstrap-Org. Übernommen wird nur mit in GoTrue bestätigter E-Mail-Adresse
  und nur, wenn `GOTRUE_MAILER_AUTOCONFIRM=false` oder
  `GOTRUE_DISABLE_SIGNUP=true` gesetzt ist; die API liest dafür dieselben
  Variablen (Compose reicht sie an `api` durch). Sonst bekommt der Login wie
  bisher eine eigene Org, und das API-Log nennt beide Variablen in einem WARN.
  Ohne die Variable und in der Cloud ändert sich nichts. Die Übernahme steht
  im Audit-Log (`org.bootstrap_claimed`, Migration 0107), und parallele
  Erst-Logins erzeugen keine zusätzliche Org mehr.
