- Punkt am „?“-Menü (Onboarding P5b, Spec §5.4): Gibt es einen Eintrag „Was ist
  neu“ nach `news_seen_at` des Kontos (ohne Wert: nach der Kontoanlage und
  höchstens 14 Tage alt), zeigt das Menü einen Punkt, und der Screenreader-Name
  des Knopfs nennt die neuen Einträge. Beim Öffnen der Seite „Was ist neu“ wird
  `PATCH /v1/me/news-seen` einmal aufgerufen und danach `/v1/me` neu geladen;
  dann verschwindet der Punkt. Die Daten kommen aus demselben Loader wie die
  Seite (`apps/web/src/help/news/`).
