- Die Web-App hat eine Seite `/invitations`: Nach dem Login zeigt sie die offenen
  Einladungen an die E-Mail-Adresse des eigenen Kontos (Workspace und Rolle) und
  nimmt eine Einladung per Klick an.

  Die Seite ist das Ziel des Links aus der Einladungsmail. Sie nutzt
  `GET /v1/invitations/pending` und `POST /v1/invitations/pending/{id}/accept`;
  kein Request trägt dabei einen Einladungs-Token. Ohne Anmeldung führt der
  Login zurück auf `/invitations`, ein per Einladung neu angelegtes Konto setzt
  zuerst ein Passwort. Ist die E-Mail-Adresse des Kontos noch nicht bestätigt,
  sagt die Seite das in Deutsch und Englisch, statt eine leere Liste zu zeigen.
