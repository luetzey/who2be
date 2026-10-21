- Hilfe-Bereich im Web (Onboarding P4): `/w/:workspaceId/help` mit Suche,
  Abschnitt „Tutorials“ (Fortschritt, Starten / Fortsetzen / Neu starten) und
  „Nachschlagen“, Artikelseite `/help/:slug` (Navigation, „Auf dieser Seite“,
  „Für Agenten kopieren“) und Tutorial-Seite `/help/tutorials/:id`; Kurzlink
  `/help/…` leitet in den Standard-Workspace. Inhalte sind Markdown-Dateien je
  Sprache unter `apps/web/src/help/` (Loader per `import.meta.glob`,
  Frontmatter-Schema, ADR-0058-Dialekt), dargestellt mit `markdown-to-jsx`
  (MIT) ohne Raw-HTML und mit Link-Allowlist. Ein Inhaltstest prüft Schema,
  DE/EN-Parität, Anker und Links; ein Python-Test prüft die Tutorial-Texte
  gegen den Katalog (ADR-0060). Erstes Tutorial: „Erste Schritte“.
