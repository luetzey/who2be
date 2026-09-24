- Die drei Mobile-/Tablet-Playwright-Profile (`mobile-iphone-13`,
  `tablet-ipad-gen-7`, `mobile-320`) sind vom meldenden Uebergangszustand zum
  **harten CI-Gate** geworden. Ein Layout-Fehler auf Phone- oder Tablet-Breite
  blockiert damit den Pull Request, statt nur im Job-Log zu stehen.

  Der Job `e2e-mobile` haengt dafuer an drei Stellen am Aggregat-Job
  `all-green`, die nur zusammen wirken: er steht in dessen `needs`-Liste, hat
  im Auswertungs-Step eine eigene Pruefzeile, und sein `continue-on-error`
  ist entfernt. Fehlt eine der drei, sieht das Gate vollstaendig aus und setzt
  nichts durch. Das Ruleset von `main` bleibt unveraendert — `all-green` ist
  weiterhin der einzige Required Check.

- `scripts/ci/test_all_green_matrix.py` bewacht jetzt auch die dritte dieser
  Stellen: ein Job, der in `all-green.needs` steht und gleichzeitig
  `continue-on-error: true` fuehrt, wird als Befund gemeldet. GitHub meldet
  einen solchen Job als `success`, auch wenn seine Steps fallen — der
  Aggregat-Job prueft dann einen Wert, der nie `failure` werden kann.
