- Betreiber können eine Organisation mit `who2be-org-transfer` vollständig exportieren und wieder importieren.

  `who2be-org-transfer export --org-id … --recipient … --output …` schreibt die
  Postgres-Zeilen, die SQLite-Dateien des Tabellen-Stores und die Blobs einer Org
  in ein tar-Archiv, das immer mit gpg verschlüsselt ist. Einen Klartext-Pfad gibt
  es nicht. `gpg -d … | who2be-org-transfer import` spielt das Archiv in eine
  leere oder fremde Instanz ein.

  Der Import ist fail-closed. Er bricht ohne Rückstände ab, wenn eine Prüfsumme
  nicht passt, der Migrationsstand abweicht, eine ID kollidiert, eine Zeile einem
  fremden Mandanten gehört oder ein Fremdschlüssel aus dem Archiv herauszeigt.
  Zugangsdaten (API-Tokens, OAuth-Codes und -Refresh-Tokens, Einladungen) liegen
  nie im Archiv. Entitlements werden exportiert, aber nicht importiert.

  Damit ist die Rückgabe nach Art. 28 Abs. 3 lit. g DSGVO ein Betreiber-Schritt
  (ADR-0055 §4.6, R6). Das Runtime-Image enthält dafür `gnupg`. Die Anleitung
  steht in `docs/org-export-import.md`.
