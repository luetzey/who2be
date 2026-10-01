- Dashboard, Mitgliederliste und `/v1/me` zeigen E-Mail-Adressen und
  Anzeigenamen jetzt auch dann, wenn die API als Laufzeitrolle `who2be_app`
  verbindet. Bisher endete das Dashboard dort mit einem Serverfehler, und
  Mitgliederliste und Personal-Organisation blieben ohne E-Mail.

  Profile liest die App nur noch über die neue Datenbankfunktion
  `w2b_user_profiles` (Migration 0090). Sie gibt Profile ausschließlich für
  Mitglieder des aktuellen Workspaces und seiner Organisation sowie für den
  Aufrufer selbst zurück. Die Laufzeitrolle bekommt keinen Zugriff auf das
  Auth-Schema.
