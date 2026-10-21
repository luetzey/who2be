- Die Web-App kann Fehler an einen Sentry-kompatiblen Tracker melden (zum
  Beispiel ein selbst gehostetes GlitchTip). Das Fehler-Tracking ist aus,
  solange `WHO2BE_SENTRY_DSN` am Web-Container leer ist; dann wird das SDK
  nicht geladen und es gibt keinen Netzwerk-Aufruf. Der DSN wird nur zur
  Laufzeit über `/config.js` gelesen. Optional: `WHO2BE_SENTRY_ENVIRONMENT`
  (Default `production`) und `WHO2BE_SENTRY_RELEASE`.

  Gemeldet werden Render-Fehler aus der Routen-Fehlergrenze sowie unbehandelte
  Fehler. Events enthalten keine personenbezogenen Daten: keinen Nutzer, keine
  Cookies, Header, Bodies, Query-Strings oder URL-Fragment-Parameter und kein
  Session-Replay; `w2b_`-Tokens, JWTs, Bearer-Werte und E-Mail-Adressen werden
  maskiert.
  Damit der Browser senden darf, muss die CSP `connect-src` die Tracker-Domain
  erlauben; das folgt in einem eigenen Infra-Schritt.

- Für lesbare Stacktraces erzeugt der Web-Bau jetzt Source-Maps, aber
  versteckt (ohne Verweis im ausgelieferten JavaScript). Sie werden vor dem
  Ausliefern gelöscht; der Bau bricht ab, wenn doch eine `.map`-Datei im Image
  landet. Der Upload der Source-Maps zum Tracker ist noch nicht enthalten und
  folgt in einem eigenen Infra-Schritt. Das Image baut weiterhin ohne BuildKit.
