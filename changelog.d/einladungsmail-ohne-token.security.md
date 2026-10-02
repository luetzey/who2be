- Die Einladungsmail enthält keinen Einladungs-Token mehr.

  Der Link in der Mail meldet den Eingeladenen an und führt auf die Seite
  `/invitations`; dort stehen die offenen Einladungen an die Adresse des
  Kontos, angenommen wird per Klick. Der Token steht damit weder im Mail-Link
  noch in den Benutzer-Metadaten des Kontos. Er gilt nur noch für den Link,
  den ein Admin selbst weitergibt.

  `GOTRUE_MAILER_URLPATHS_INVITE` steht in den Produktions-Compose-Dateien
  (Hetzner, Dokploy) jetzt auf `/auth/v1/verify`. Mit dem bisherigen Wert
  `/invitations` zeigte der Link in der Einladungsmail auf eine Seite, die es
  unter der Auth-Domain nicht gibt. Wer die Compose-Datei selbst pflegt, muss
  den Wert nachziehen.
