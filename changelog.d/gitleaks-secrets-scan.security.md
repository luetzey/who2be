- Jeder PR und jeder Push auf `main` wird jetzt mit Gitleaks auf
  Zugangsdaten geprueft.

  Der neue CI-Job `secrets` scannt jeden Commit des PRs bzw. des Pushes, haengt
  an keinem Pfadfilter (ein Geheimnis in Doku ist genauso oeffentlich) und
  laeuft auch auf Dependabot-PRs. Er steht in `all-green` mit eigener
  Erwartung. Gitleaks 8.30.1 (MIT) wird als Binary mit gepruefter SHA256
  geladen; das Log nennt Fundstellen, nie den Wert. Ausnahmen stehen in
  `.gitleaks.toml` nur als exakte, begruendete Platzhalter-Werte. Ein
  einmaliger Scan der gesamten Historie ergab mit dieser Konfiguration
  0 Funde.
