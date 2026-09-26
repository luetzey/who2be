- Agenten fordern Auto-Merge an, statt selbst zu mergen: nach freigegebenem
  Review aktiviert ein Agent GitHubs Auto-Merge per GraphQL-Mutation; gemergt
  wird erst, wenn der Required Check `all-green` grün ist.

  Die Absicherung verschiebt sich damit von der Kommandosperre auf drei Gates
  (Review freigegeben, `all-green` grün, Required Check aktiv). Alle
  merge-ausführenden Kommandos bleiben unverändert gesperrt.
  Verfahren, Fehlerbilder und Grenzen: `docs/auto-merge-agenten.md`.
