- Gedaechtnis (Web): das Detail-Sheet loest einen Deep-Link `?entry=<id>`
  ueber den Einzelabruf `GET /memories/{memory_id}` auf statt ueber
  seitenweise Listenabrufe. Nur `404 memory_not_found` zeigt „Diesen Eintrag
  gibt es nicht mehr oder du darfst ihn nicht sehen“; ein Netz- oder
  Serverfehler erscheint als Fehlermeldung mit „Erneut versuchen“ und wird
  nicht mehr als fehlender Eintrag ausgegeben.
