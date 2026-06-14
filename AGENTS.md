# AGENTS.md — Einstieg für LLM-/Agent-gestützte Entwicklung

Tool-agnostischer Einstiegspunkt (Cursor, Copilot, Claude Code, …). Wer mit
einem LLM an Who2Be arbeitet, liest **zuerst hier** und folgt den Verweisen.

## In dieser Reihenfolge lesen

1. **[`CLAUDE.md`](CLAUDE.md)** — Repo-Fakten: Struktur, Befehle, Code-Style,
   Etikette, aktueller Stand. Die verbindliche repo-spezifische Quelle.
2. **[`docs/standards/`](docs/standards/)** — die stehenden Engineering-Standards
   (Architektur, Design, Coding, Testing, Security, Frontend, Compliance) +
   die **Arbeitsmethode** ([`engineering-method.md`](docs/standards/engineering-method.md)).
3. **[`.claude/context/`](.claude/context/)** — persistentes Projekt-Gedächtnis
   (PROJECT / ARCHITECTURE / DECISIONS / STATE) gegen Session-Drift. **Vor dem
   Planen lesen.**
4. **[`docs/architecture.md`](docs/architecture.md)** + **[`docs/adr/`](docs/adr/)**
   — Architektur-Blueprint und die Architecture Decision Records (das Warum).

## Vorrang-Regel (gegen Drift)

Bei Konflikt gewinnt **immer die spezifischere Ebene**:
`Code im Repo` › `CLAUDE.md` / Skills › `docs/standards/` (generisch).
Die Standards sind das *Warum/Wie* generisch; die repo-spezifische
Konkretisierung steht in `CLAUDE.md` und den Skills.

## Nicht verhandelbar

- **Plan-first** bei nicht-trivialer Arbeit (siehe `engineering-method.md`).
- **Single Source of Truth** pro Entscheidung — keine zweite, abweichende Kopie.
- **Definition of Done** vor jedem Push: `uv run ruff check . && uv run mypy . &&
  uv run pytest -q` (Python) · `npm run lint && npx tsc --noEmit && npm test &&
  npm run build` (in `apps/web/`).
- Bei Unklarheit / Design-Weiche: **nicht raten** — drei Optionen mit Trade-offs
  vorschlagen und rückfragen.
