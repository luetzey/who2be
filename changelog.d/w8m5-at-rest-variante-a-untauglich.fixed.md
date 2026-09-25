- RUNBOOK: Die Behauptung, Hetzner verschlüssele Cloud Volumes serverseitig
  at-Rest, ist entfernt — sie war falsch. Hetzners eigene TOMs führen
  „Encryption of Data (at rest)" als *Client’s responsibility*; „Variante A"
  ist damit kein gangbarer Weg und steht nur noch als ausdrückliche Warnung
  im Dokument. Gültig ist allein selbst verwaltetes LUKS auf dem Host.

  Die Verschlüsselung hat jetzt einen eigenen Provisioning-Schritt (3b) vor
  dem ersten `docker compose up`, statt als Nebensatz beim Box-Anlegen zu
  stehen — danach ist sie nur mit Downtime und Restore-Risiko nachholbar.
  Nachgezogen in `deploy/hetzner/README.md` und
  `docs/cloud-hosting-owner-guide.md`.

  Ebenfalls richtiggestellt: Die Hetzner-Cloud-Firewall ist keine Alternative
  zu `ufw`, sondern die wirksame Ebene. Docker leitet Pakete an
  veröffentlichte Container-Ports in der `nat`-Tabelle um, bevor sie die von
  `ufw` genutzte `INPUT`-Kette erreichen; die `ufw`-Regel greift dort nicht.
