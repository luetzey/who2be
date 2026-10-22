- Web-Tests: Die Definition of Done läuft lokal unter Node 22 wieder ohne
  `NODE_OPTIONS` grün. Node 22.23.x schaltet wie Node 25+ das Node-eigene Web
  Storage ein, und Vitest 4 filtert dann jsdoms `window.localStorage` weg
  (vitest#8757): `npm run test:coverage` endete lokal mit 583 roten Tests in 58
  Dateien, während die CI auf einer älteren 22er-Patchversion grün blieb. Die
  Vitest-Konfiguration startet ihre Worker jetzt mit
  `--no-experimental-webstorage` (`test.execArgv`), lokal und in der CI gleich;
  `CONTRIBUTING.md` beschreibt den Stand.
