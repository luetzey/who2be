- API und MCP-Server können Fehler an einen Sentry-kompatiblen Tracker melden
  (zum Beispiel ein selbst gehostetes GlitchTip). Das Fehler-Tracking ist aus,
  solange `SENTRY_DSN` nicht gesetzt ist; dann wird das SDK nie initialisiert
  und macht keinen Netzwerk-Aufruf.

  Mit DSN enthalten Events keine personenbezogenen Daten: keine IP, keine
  Cookies, keinen Nutzer, keine Request-Bodies, Query-Strings, Header oder
  Stack-Variablen und keine MCP-Werkzeug-Argumente oder -Ergebnisse.
  `w2b_`-Tokens, JWTs, Bearer-Werte und E-Mail-Adressen werden in Meldungen
  und Breadcrumbs maskiert. Optional: `SENTRY_ENVIRONMENT` (Default
  `production`), `SENTRY_RELEASE` (Default `<dienst>@<version>`),
  `SENTRY_TRACES_SAMPLE_RATE` (Default `0`).
