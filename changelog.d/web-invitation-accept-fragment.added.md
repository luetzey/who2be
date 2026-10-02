- Die Web-App nimmt geteilte Einladungslinks über das URL-Fragment an
  (`/invitations/accept#token=…`) und schickt den Token im Body an
  `POST /v1/invitations/accept`.

  Der Token steht damit in keinem Request-Pfad und keiner Query mehr; die
  Seite entfernt das Fragment nach dem Lesen aus der Adresszeile und trägt den
  Token über Login und Passwort-Setzen im `sessionStorage` statt in `?next=`.
  Bereits verschickte Links der Form `/invitations/<token>/accept` funktionieren
  weiter und nehmen ebenfalls per Body an. Fehlt dem Konto eine (bestätigte)
  E-Mail-Adresse, zeigt die Seite dafür eine eigene Meldung in Deutsch und
  Englisch.
