- Die DSGVO-Auskunft (`GET /v1/gdpr/export`) enthält im Block `account` jetzt
  auch dann E-Mail-Adresse, Registrierungs- und letzten Anmeldezeitpunkt, wenn
  die API als Laufzeitrolle `who2be_app` verbindet. Bisher blieben die Felder
  dort leer. Ebenso meldet `/v1/me` das Feld `has_password` dort korrekt.

  Beides liest die App über die neue Datenbankfunktion `w2b_self_account()`
  (Migration 0093). Sie liefert ausschließlich die Kontodaten des Aufrufers
  selbst und vom Passwort nur, ob eines gesetzt ist. Die Laufzeitrolle bekommt
  weiterhin keinen Zugriff auf das Auth-Schema.
