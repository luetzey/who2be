- German interface texts now use real umlauts and ß instead of ae/oe/ue/ss
  substitutes, for example "Zurück zur Anmeldung", "Passwort ändern",
  "Straße und Hausnummer" and "Allgemeine Geschäftsbedingungen". The draft
  submit button now reads "Entwurf abschließen" instead of the mixed-language
  "Draft abschliessen". API error texts (`common.errors.*`) and slash-menu
  search aliases deliberately keep their ASCII spelling.

  The resource block picker's accessible labels now come from the locale
  files instead of hard-coded German, and the billing panel, tag suggestions
  and the persona profile example use real umlauts too. A new test fails as
  soon as `de.json` contains an umlaut substitute outside an allow list of
  words with a genuine "ae/oe/ue/ss" (such as "neue", "Steuer", "aktuell",
  "Passwort").
