- Gesprächsprotokolle und Maßnahmen sind in Datenexport und Kontolöschung
  eingebunden (ADR-0053, Paket E2a-2). Der DSGVO-Export enthält je Workspace
  `feedback_sessions`: jedes Protokoll mit seinen Fällen und Maßnahmen, jede
  Maßnahme mit ihren Fällen und ihrem Verlauf. Ab der Rolle `editor` sind das
  alle Protokolle des Workspace, darunter nur die, an denen die Person
  beteiligt war (eingereicht, Teilnehmer, abweichende Meinung oder Akteur an
  einer Maßnahme); `export_manifest.feedback_sessions` sagt, welche Regel
  galt. Die Kontolöschung anonymisiert in fremden Workspaces den
  einreichenden Menschen, menschliche Einträge in Teilnehmern und
  abweichenden Meinungen sowie menschliche Akteure im Maßnahmen-Verlauf. VVT
  und Löschkonzept sind ergänzt.
