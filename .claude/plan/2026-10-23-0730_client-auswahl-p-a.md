# Client-Auswahl P-A: Claude (Web, App, Handy), Raster, Hermes Agent, gemeinsame Anleitung

Karte t_87ec1e7f · Spec `client-auswahl-design-2026-10.md` (Karte t_eb9ad00c) §0–§6, Paket P-A, ohne ChatGPT.

Basis: origin/main + PR #1048 (connect-claude, t_4bc2d5d1) + PR #1057 (Agent-Seite mobil, t_84aef25e), beide freigegeben, nicht gemergt. Der Branch fuehrt beide per Merge-Commit mit; nach deren Merge faellt der Diff auf P-A zusammen.

## Completion-Condition

- Auswahl: 5 Kacheln in der Reihenfolge Claude (Web, App, Handy) · Claude Code · Cursor oder VS Code · Hermes Agent · Etwas anderes; Raster `grid-cols-2 md:grid-cols-3`.
- Untertitel `connect.lead.<client>` unter dem Raster, Schritte verweisen per `aria-describedby`.
- Hermes: Befehl `hermes mcp add <slug> --url <url> --auth oauth` als einzige Brand-Aktion, Kopieren startet das Warten; Hinweise Profil und Headless.
- „Klappt es nicht?“ zeigt je Client auf die passende Hilfe-Stelle.
- Begruessung: Chips aus `CONNECT_CLIENTS` ohne claude; Erfolgsname auch fuer hermes.
- Eine gemeinsame Anleitung (`ConnectGuide`, `CopyField`, `WaitingBlock`) fuer Baustein und Dialog; der Dialog bricht Text nicht mehr mit `break-all`.
- Hilfe: `#hermes` und `#steckbriefe` in connect-other-clients, Saetze in connect-claude und claude-free, News Hermes; DE/EN parallel.
- Web-DoD gruen, Paritaetstest Tutorial↔Katalog und helpContent.test unveraendert gruen, Rot-Probe ohne `--auth oauth` rot, Fotos 320/390/1280.

## Entscheidungen

- Ablageort der gemeinsamen Komponente: `src/components/connect/ConnectGuide.tsx` statt `features/agents/components/` (Spec §3 „z. B.“). Grund: Die ESLint-Regel verbietet Cross-Feature-Importe aus `features/help` nach `features/agents/components/*` und verlangt geteilte Teile unter `@/components`.
- Hervorhebung in Schritten ohne `<Trans>`: das Repo nutzt `<Trans>` nirgends; `/reload-mcp` und der Profil-Befehl werden ueber einen Platzhalter `{{cmd}}` als `<code>` eingesetzt (Muster wie ReviewPreparePage `LINK_MARK`).
- Werkzeugauswahl-Halbsatz in Hermes-Schritt 2 entfaellt (Karte: offen bis PM-Durchlauf, Spec §7.2).
- `hermes mcp add` wird nicht ausgefuehrt (Karte).

## Schritte

1. installLinks: `hermes`, Reihenfolge, `hermesCommand`, `CONNECT_HELP_PATHS`.
2. ConnectGuide (neu) aus AgentConnectorSection herausloesen, Hermes-Zweig, Untertitel, Steckbrief-Link.
3. AgentConnectorSection: Raster, Claude-Kachel zweiteilig, gemeinsame Anleitung, Hilfe-Link je Client.
4. WelcomeDialog: Chips, gemeinsame Anleitung, Erfolgsname.
5. i18n DE/EN.
6. Tests (Baustein, Dialog, hermesCommand, Rot-Probe).
7. Hilfe-Markdown DE/EN + News, Changelog-Fragment.
8. DoD, Fotos, PR.

## Stand (2026-10-23)

Schritte 1–7 erledigt. Web-DoD grün: lint (0 Fehler), tsc, test:coverage mit 280 Dateien und 2787 Tests, Skip-Gate 0, build, license:check, i18n:check. Python-Paritätstest und changelog check grün. Zwei Rot-Proben (ohne `--auth oauth`; CopyField immer `break-all`) waren jeweils rot und sind zurückgesetzt. Fotos liegen in `.shots/t_87ec1e7f/` (nicht committet), Breiten 1280/390/320, je hell und dunkel; measure ohne Überlauf.

Nachgezogen nach den Fotos: Befehlsfeld in Monospace wie im Mockup. Kurze Inline-Befehle (`/reload-mcp`) brechen nicht mehr mitten im Wort.

Bekannt und hingenommen: Bei 320 px sind die zwei Kacheln der ersten Zeile 52–54 px hoch, die übrigen 44 px. „Claude (Web, App, Handy)“ ist zweizeilig, und das Raster gleicht nur die Höhe innerhalb einer Zeile an (`items-stretch` je Zeile).

## Auf Zuruf angenommen

- Keine. (Werkzeugauswahl-Frage bewusst offen, siehe oben.)
