- Gedaechtnis: neuer Filter `auto` fuer `GET /memories`, `GET /memories/counts`
  und die Stapel-Auswahl per Filter (`POST /memories/batch`). `auto=true`
  liefert nur Eintraege, die die Freigabematrix automatisch aktiviert hat
  (Ereignis `auto_activated`), unabhaengig vom heutigen Status; von Hand
  freigegebene Eintraege zaehlen nicht. `auto=false` liefert das Gegenstueck.
  Grundlage der S4-Kennzahl „automatisch freigegeben · davon bestaetigt“.
