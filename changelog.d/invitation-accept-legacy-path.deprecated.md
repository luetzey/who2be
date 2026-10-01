- `POST /v1/invitations/{token}/accept` (Token im Pfad) ist veraltet und wird
  nach dem 2026-12-31 entfernt.

  Die Route funktioniert bis dahin unverändert, damit bereits verschickte
  Einladungslinks gültig bleiben. Antworten tragen einen `Sunset`-Header
  (RFC 8594) und `Link: </v1/invitations/accept>; rel="successor-version"`;
  die OpenAPI-Spec führt die Route als `deprecated`.
