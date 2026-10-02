- Neuer Endpunkt `POST /v1/invitations/pending/{invitation_id}/accept`: nimmt
  eine Einladung an die E-Mail-Adresse des eingeloggten Kontos per Klick an,
  ohne Einladungs-Token. Die ID stammt aus `GET /v1/invitations/pending`. Es
  gilt dieselbe Bestätigungsprüfung wie dort: ohne E-Mail im Login 403
  `invitation_email_required`, ohne bestätigte Konto-Adresse 403
  `invitation_email_unconfirmed`. Eine Einladung an eine andere Adresse
  beantwortet der Endpunkt wie eine unbekannte ID mit 404
  `invitation_not_found`. Bereits angenommene, widerrufene oder abgelaufene
  Einladungen ergeben 410 `invitation_no_longer_valid`, wie beim geteilten
  Link. Nur für angemeldete Personen, nicht für API-Tokens.
