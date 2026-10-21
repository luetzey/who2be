- Web: Ein Review-Ergebnis hat jetzt eine eigene Seite am Agenten
  (`/w/<ws>/agents/<agent>/reviews/<id>`, ADR-0053 Phase E, Paket E5c). Sie zeigt
  Teilnehmende, Zusammenfassung, Entscheidungen, abweichende Meinungen,
  verknüpfte Rückmeldungen und die vereinbarten Änderungen mit Zustand und
  Nachkontrolle. Wurde ein Review-Ergebnis korrigiert, verlinken Vorgänger und
  Nachfolger aufeinander. Ein noch gültiges Ergebnis bietet einen Kopierblock
  „Korrektur einreichen“ für den Builder; er enthält nur IDs und Namen. Lesen ist
  ab `editor` erlaubt, ein `viewer` sieht dieselbe Meldung wie bei einem
  unbekannten Review.
