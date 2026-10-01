- Einladungen lassen sich per `POST /v1/invitations/accept` mit dem Token im
  Request-Body annehmen (`{"token": "..."}`).

  Der Token steht damit nicht mehr im URL-Pfad und so auch nicht in
  Access-Logs zwischen Browser und API. Es gelten dieselben Prüfungen wie
  bisher: angemeldetes Konto mit Email-Adresse, die zur Einladung passt;
  einmalig nutzbar (danach 410), unbekannter Token 404, fehlender Token 422.
