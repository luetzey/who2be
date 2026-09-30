- „Feedback geben“ und „Problem melden“ öffnen auf dem Telefon (unterhalb
  `md`, < 768px) eine eigene Seite statt eines Dialogs (Mobil-Spec W4=b).

  Im Dialog steckte die Notiz bei 320px in einem doppelten Scrollbereich:
  der Dialog scrollte 1,38-fach, die Textarea darin noch einmal 2,53-fach
  (gemessen mit einer langen Notiz). Auf der eigenen Seite scrollt nur noch
  die Seite; das Textfeld ist 288 statt 238px breit.

  Die neuen Routen heißen `/w/:workspaceId/feedback/give/:entityType/:entityId`
  (Bezugsversion als `?version=`) und `/w/:workspaceId/feedback/report`.
  „Zurück“, „Abbrechen“ und erfolgreiches Absenden führen einen Schritt in
  der History zurück, also auf die Ausgangsseite samt Query (etwa `?tab=`),
  genau wie der Browser-Zurück-Knopf; die Bestätigung erscheint dort als
  Toast. Bei einem Direktaufruf ohne Herkunft ersetzt sich die Seite durch
  die Element-Detailseite bzw. die Feedback-Übersicht. Ab `md` bleibt der
  Dialog unverändert. Das Formular ist für Dialog und Seite dieselbe
  Komponente.
