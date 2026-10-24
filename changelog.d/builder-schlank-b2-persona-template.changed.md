- Builder-Persona und Builder-Template sind schlanker (Builder schlank B2,
  `BUILDER_CONTENT_VERSION` 20 → 21). Das Profil zählt unter „Erlaubt“ keine
  Werkzeuge mehr auf, sondern beschreibt in drei Sätzen, was der Builder darf.
  Der Modi-Absatz im Profil entfällt, weil `get_persona` die Modi ohnehin
  liefert. Die vier Phasen stehen nur noch im Output-Stil, der Architekt-Modus
  verweist darauf. Alle Verbote und die Feedback-Regel bleiben. Der Text, den
  `get_persona` für den Builder liefert, schrumpft auf Deutsch von 8 608 auf
  6 056 Bytes, das Profil von 664 auf 420 Wörter. Das Builder-Template hat
  keinen Werkzeug-Block mehr (doppelt zu `tools/list`) und lädt die Persona per
  `persona-ref` statt das Profil einzubetten. Der gerenderte Prompt schrumpft
  so von 32 746 auf 8 291 Bytes. Builder-Lite bleibt unverändert.
  Bestands-Workspaces erhalten die Fassung über den Builder-Sync.
