- Eine zweite Einladung an dieselbe Adresse im selben Workspace endet nicht mehr
  in einem 500. Ist die bestehende Einladung noch offen und gültig, antwortet
  `POST /v1/workspaces/{ws}/invitations` mit 409 und dem neuen Fehlergrund
  `invitation_already_pending`. Ist sie bereits abgelaufen, aber vom Purge noch
  nicht geschwärzt, gelingt die Neueinladung (201): die alte Zeile wird in
  derselben Transaktion mit dem Purge-Marker geschwärzt, `revoked_at` bleibt
  unberührt.
