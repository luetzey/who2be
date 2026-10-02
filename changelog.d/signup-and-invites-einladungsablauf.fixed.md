- `docs/signup-and-invites.md` beschreibt den Einladungsablauf wieder so, wie
  er läuft: Einladungsmail ohne Token mit Annahme auf der Seite
  `/invitations`, geteilter Link mit dem Token nur im URL-Fragment
  (`/invitations/accept#token=…`).

  Die Seite nannte noch den abgelösten Link mit Token im Pfad
  (`/invitations/{token}/accept?via=magic`), auch als Fallback ohne SMTP. Neu
  dokumentiert ist außerdem, dass GoTrue an eine bereits bestätigte Adresse
  keine Einladungsmail schickt; registrierte Nutzer erreicht verlässlich nur
  der geteilte Link.
