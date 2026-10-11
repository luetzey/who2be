- On-Prem-Bootstrap: Der erste Login des Bootstrap-Admins
  (`WHO2BE_BOOTSTRAP_ADMIN_EMAIL`) landet jetzt in der beim ersten Boot
  geseedeten Organisation und wird dort Owner bzw. Workspace-Admin. Bisher
  bekam der Login eine eigene, leere Personal-Org, und niemand verwaltete die
  Bootstrap-Org. Übernommen wird nur mit in GoTrue bestätigter E-Mail-Adresse;
  ohne die Variable und in der Cloud ändert sich nichts. Die Übernahme steht
  im Audit-Log (`org.bootstrap_claimed`, Migration 0107), und parallele
  Erst-Logins erzeugen keine zusätzliche Org mehr.
