- Der Web-Client setzt IDs und andere Werte nur noch als einzelnes, kodiertes
  Pfadsegment in API-Pfade ein (Schutz gegen Client-Side Path Traversal).

  Ein Wert aus URL oder Daten, der kein Segment sein kann (leer, `.`, `..`,
  `/`, `\`, `?`, `#`), wird ohne Netzabruf als 404 abgelehnt; zuvor konnte
  z. B. `?entry=..%2F..%2Fx` einen authentifizierten Abruf auf einen
  beliebigen `/v1`-Pfad ausloesen. Query-Parameter laufen durchgaengig ueber
  `URLSearchParams` (Leerzeichen werden dabei `+` statt `%20`).
