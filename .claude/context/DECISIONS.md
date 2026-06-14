# DECISIONS — Warum so (append-only)

Tragende **Architektur**-Entscheidungen leben als ADR unter
[`../../docs/adr/`](../../docs/adr/) — das ist die kanonische Quelle (0001–0035).
Diese Datei hält **leichtere, session-übergreifende** Entscheidungen, die keinen
eigenen ADR rechtfertigen. Append-only: nie umschreiben; eine Revision bekommt
einen neuen Eintrag mit Verweis.

## 2026-06-14 — LLM-Standards als Repo-Markdown (`docs/standards/`)
- **Entscheidung:** Die stehenden Engineering-Standards (zuvor extern) werden als
  self-contained Markdown unter `docs/standards/` materialisiert; `AGENTS.md` als
  tool-agnostischer Einstieg; `.claude/context/` als Projekt-Gedächtnis.
- **Begründung:** Repo muss ohne externe Quelle vollständig LLM-verständlich sein
  (Anti-Drift). Single-Source: wo ADR/Skill existiert, wird verlinkt statt kopiert.
- **Verworfen:** nur indexieren ohne Materialisieren (Standards blieben verstreut);
  Enforcement-Tooling (zu viel Pflege-Overhead jetzt).

## 2026-06-14 — Repo von externem Agent-Workspace entkoppelt
- **Entscheidung:** Persönlicher Agent-Bootstrap aus `CLAUDE.md` → gitignored
  `CLAUDE.local.md`; öffentliche Docs selbsttragend. `.claude/plan/` bleibt
  öffentlich (Referenz-IDs gewähren ohne Auth keinen Zugriff).
- **Begründung:** Public-Switch-Vorbereitung; öffentliche Datei soll nicht auf
  eine private Quelle als Autorität verweisen.

## 2026-06-14 — Kein History-Rewrite für den Public-Switch
- **Entscheidung:** Bestehende Commits/IDs bleiben in der History.
- **Begründung:** IDs/E-Mail gewähren ohne Auth keinen Zugriff; Rewrite-Risiko
  überwiegt den Nutzen.

_Bei Wachstum: älteste Einträge zu Einzeilern komprimieren (Titel + Entscheidung
bleiben)._
