- Neuer Endpunkt `GET /v1/invitations/pending`: listet die offenen Einladungen
  für die E-Mail-Adresse des eingeloggten Kontos über alle Workspaces, mit
  Workspace-Name und Rolle, ohne Einladungs-Token. Gelistet werden nur nicht
  angenommene, nicht widerrufene und nicht abgelaufene Einladungen; die
  Groß-/Kleinschreibung der Adresse spielt keine Rolle. Der Endpunkt verlangt
  eine bestätigte Konto-Adresse: ohne E-Mail im Login antwortet er mit 403
  `invitation_email_required`, ohne Bestätigung mit 403
  `invitation_email_unconfirmed`. Nur für angemeldete Personen, nicht für
  API-Tokens.
