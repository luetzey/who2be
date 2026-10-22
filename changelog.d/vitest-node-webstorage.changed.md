- Web-Tests: Die Vitest-Worker starten jetzt mit `--no-experimental-webstorage`
  (`test.execArgv`). Das ist eine Härtung für Node 25+ oder einen
  versehentlich falschen `node` im PATH: Dort ist Node-eigenes Web Storage
  aktiv, und Vitest 4 filtert jsdoms `window.localStorage` weg (vitest#8757).
  Auf dem gepinnten Node 22 ändert das Flag nichts. `CONTRIBUTING.md` nennt
  dazu die Selbstprüfung `npm exec -- node -v`.
