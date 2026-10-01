- Die Datenbankfunktion für die eigenen Kontodaten (`w2b_self_account()`)
  gibt jetzt zusätzlich an, ob die E-Mail-Adresse des Kontos bestätigt ist
  (`email_confirmed`, Migration 0094). Das ist die Grundlage dafür, offene
  Team-Einladungen nach dem Login anzuzeigen, ohne dass der Einladungslink
  einen Token tragen muss. Der Zeitpunkt der Bestätigung verlässt die Funktion
  nicht, nur der Wahrheitswert.
