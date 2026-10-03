- Gedaechtnis: neuer Einzelabruf `GET /memories/{memory_id}` liefert einen
  Eintrag, ohne dass der Aufrufer den Besitzer (Agent oder Person) kennen muss
  — fuer Deep-Links ins Detail-Sheet (`?entry=<id>`). Sichtbarkeit wie
  `GET /memories`: eigenes Nutzergedaechtnis ab `viewer`, Agentengedaechtnis ab
  `editor`. Fremdes Nutzergedaechtnis (auch fuer `admin`), Agentengedaechtnis
  fuer `viewer` und Eintraege anderer Workspaces sind `404 memory_not_found`,
  nicht von einer unbekannten ID zu unterscheiden (ADR-0053 6.4.1).
