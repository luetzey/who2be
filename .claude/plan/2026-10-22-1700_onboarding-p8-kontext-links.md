# Onboarding P8: Kontext-Links und Leerzustände (Kanban t_3fad0818)

Stand: main 0f07bdda. PM-Entscheidung 22.10.: ein PR, bis 13 Dateien, Linkstil underline auf
foreground/muted-foreground (nicht text-brand).

## Ziele (Spec §5.3 Kontext-Links, §7 `agents.page.empty`)

1. AgentsPage: Leerzustand mit neuem Text; Hinweis „Noch keine eigenen Agenten", wenn nur
   verwaltete Agenten (Builder, `is_managed`) da sind. Link editor+ → `/help/own-agent#mit-dem-builder`,
   viewer → `/help/workspaces#rollen`. Workspace-relativ über `wsPath`.
2. OAuthConsentPage: „Was passiert hier?" → öffentlicher Kurzlink `/help/connect-claude#schritte`,
   neuer Tab, `rel="noopener noreferrer"` (kein `?request=` im Referrer). Consent-Logik unverändert.
3. PersonaProfileFields: Footer der Profil-Sektion → `/help/persona#felder` (New-Page + Detail-Tab).
4. MemoryPage: Link in den Seitenkopf-Aktionen → `/help/memory`, editor- und viewer-Zweig.
5. CopyField: neuer Schalter `breakAll` für URLs und den Claude-Code-Befehl, sonst
   `break-words` (Test-Satz, Name; PM-Nit P6).

## Dateien (13)

AgentsPage.tsx, OAuthConsentPage.tsx, PersonaProfileFields.tsx, MemoryPage.tsx,
AgentConnectorSection.tsx, de.json, en.json, changelog.d/onboarding-context-links.added.md,
AgentsPage.test.tsx, OAuthConsentPage.test.tsx, PersonaProfileFields.test.tsx,
MemoryPage.test.tsx, PersonaEditorForm.test.tsx (braucht jetzt Router wegen Link).

## Verifikation

- Tests: exakter href je Link, Anker existiert in `helpIndex` (Inhaltstest je Testdatei), Rot-Proben.
- Web-DoD laut CONTRIBUTING (lint, tsc, test:coverage, i18n:check, build).
- Fotos 320/390/1280 hell/dunkel + measure.json unter `.shots/t_3fad0818/`.
