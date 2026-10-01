- Eine Team-Einladung lässt sich nur noch mit einem Login annehmen, der eine
  E-Mail-Adresse trägt, und diese Adresse muss zur Einladung passen. Fehlt die
  Adresse, antwortet `POST /v1/invitations/{token}/accept` mit 403 und dem
  Grund `invitation_email_required`. Die Einladung bleibt dabei offen. Bisher
  wurde der Abgleich nur geprüft, wenn eine Adresse vorhanden war.
