- Die Org-Löschung (`DELETE /v1/organizations/{organization_id}`) antwortet
  Nicht-Mitgliedern jetzt wie bei einer unbekannten Organisation: `404` mit
  `reason: organization_not_found` und identischem Body (ADR-0036 „Kein
  Existenz-Orakel"). Erst für Mitglieder folgen `400`
  (`personal_organization_undeletable`) und `403`
  (`organization_owner_required`).
