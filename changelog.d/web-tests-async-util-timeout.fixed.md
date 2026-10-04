- Web-Tests: `findBy*` und `waitFor` warten zentral bis zu 3 s statt mit dem
  Testing-Library-Default von 1 s (`configure({ asyncUtilTimeout: 3000 })` in
  `apps/web/src/test/setup.ts`). Unter fremder CPU-Last rissen jsdom-Render und
  Mock-Antwort diese 1 s immer wieder (zuletzt ResourceDetailPage S11), obwohl
  die Assertion stimmte. Grüne Tests werden nicht langsamer, rote warten
  höchstens 2 s länger; gezielt gesetzte Timeouts einzelner Tests bleiben.
