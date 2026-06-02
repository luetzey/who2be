# Security Policy

## Reporting a Vulnerability

Bitte melde Sicherheitslücken **nicht** über öffentliche GitHub-Issues,
Pull-Requests oder Diskussionen.

Sobald das Repository öffentlich ist, nutze die **GitHub Private Security
Advisories** (Tab „Security" → „Report a vulnerability") für eine vertrauliche
Meldung. Solange das Repository privat ist, melde direkt per E-Mail an
<luetzey@gmail.com>.

Bitte gib in deiner Meldung möglichst an:

- betroffene Komponente (`apps/api`, `apps/mcp`, `apps/web`, `packages/models`,
  Deployment/Infra) und Version/Commit,
- eine Beschreibung der Schwachstelle und ihrer Auswirkung,
- Schritte zur Reproduktion (sofern möglich),
- ggf. einen Vorschlag zur Behebung.

## Disclosure Policy

- Wir bestätigen den Eingang einer Meldung in der Regel innerhalb von
  **3 Werktagen**.
- Wir arbeiten an einer Behebung und koordinieren die Veröffentlichung mit dir.
- Es gilt eine **Coordinated-Disclosure-Frist von 90 Tagen** ab Eingang der
  Meldung: Nach Ablauf dieser Frist bzw. nach Bereitstellung eines Fixes (je
  nachdem, was früher eintritt) können Details öffentlich gemacht werden.
- Wir bitten darum, gefundene Schwachstellen bis zur abgestimmten
  Veröffentlichung nicht öffentlich zu teilen.

## Scope

Diese Policy gilt für den Code in diesem Repository (Backend-API, MCP-Server,
Web-UI, geteilte Models und die Deployment-Konfiguration). Schwachstellen in
Drittabhängigkeiten bitte zusätzlich beim jeweiligen Upstream-Projekt melden.
