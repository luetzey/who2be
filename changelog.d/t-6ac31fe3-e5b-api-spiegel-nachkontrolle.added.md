- Web: API-Client für Reviews (Protokolle) und Änderungen (ADR-0053, Paket
  E5b). Neue Methoden `listSessions` (Filter `agent_id`, `case_id`, `due`,
  Seiten per Cursor), `getSession` (Review mit eingebetteten Änderungen) und
  `getFollowUp` (Kennzahlen der Nachkontrolle als Rohzahlen) samt Typen. Dazu
  eine reine Funktion für die Nachkontrolle: Zustand einer Änderung aus ihrem
  jüngsten Ereignis, Datum der Nachkontrolle (Änderung, sonst Review), fällig
  im lokalen Kalendertag (auch „fällig, Änderung noch nicht aktiv“) und
  „seit n Tagen“. Noch ohne sichtbare Oberfläche.
