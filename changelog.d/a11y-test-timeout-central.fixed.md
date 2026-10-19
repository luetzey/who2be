- Web-Tests: Jeder Test, der axe über den Helfer `@/test/a11y` laufen lässt,
  bekommt jetzt zentral 15 s Timeout — auch außerhalb von `*.a11y.test.tsx`.
  Bisher liefen 43 solcher axe-Tests in gewöhnlichen `*.test.tsx` mit dem
  5-s-Default von Vitest und rissen ihn unter CI-Last (main rot, #975). Der
  Helfer setzt das Timeout per `vi.setConfig` für die importierende Datei;
  Dateien ohne axe behalten 5 s. Wert und Messung stehen an einer Stelle
  (`src/test/a11y-timeout.ts`), ein Wächtertest verlangt, dass jede
  axe-Testdatei den Helfer nutzt. axe-Regeln und Testmenge bleiben unverändert.
