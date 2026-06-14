# Notion-Entkopplung des Repos (Public-Prep)

**Stand:** 2026-06-14 0832 · **Branch:** `claude/exciting-fermi-d0imfe`
**Entscheidung (User):** Vollständig (untrack `.claude/plan/`, kein
History-Rewrite) + Coder-Bootstrap lokal in gitignored `CLAUDE.local.md`
erhalten.

## Ziel

Der öffentliche Repo enthält keine Notion-IDs/-URLs mehr und ist nicht von
privaten Notion-Artefakten abhängig (selbsttragende Repo-Docs). Der persönliche
Coder-Workflow (Notion-Bootstrap) läuft lokal weiter.

## Arbeitspakete

- [x] **WP-1 — `CLAUDE.local.md` (gitignored) angelegt** mit dem Coder-Bootstrap.
  `.gitignore` ergänzt (CLAUDE.local.md + .claude/plan/). ✅
- [x] **WP-2 — CLAUDE.md entkoppelt:** Bootstrap-Block entfernt;
  Frontend-Standards-Sektion ohne Notion-URL/ID, Datei selbst verbindlich. ✅
- [x] **WP-3 — `.claude/plan/` untracked** (88 Dateien, lokal erhalten). ✅
- [x] **WP-4 — Doku/​Code neutralisiert (meaning-erhaltend):** CLAUDE.md,
  frontend/architecture+design-language, architecture, compliance/README,
  ADR-0031/0033/0035, config.py, licensing/__init__, workspace_repository,
  migration 0047. ✅ **User-Entscheidung: Stopp nach Kern-Entkopplung** —
  `.claude/plan/`-Text-Pointer (38 Dateien) + Notion-Analogien bleiben bewusst.
  - `docs/frontend/architecture.md:8-9` — Notion-Playbook-ID raus.
  - `docs/frontend/design-language.md:10,467` — „Notion-Playbook gewinnt" →
    Datei selbst verbindlich.
  - `docs/architecture.md:3,25,415` — Notion-Projekt-/PROJ-Verweise neutral.
  - `docs/compliance/README.md:13,28` — „Notion-Composite" → „interner Standard".
  - `docs/adr/0033` — „Notion-Atomic" → neutral.
  - Code-Kommentare: `core/config.py:85`, `licensing/__init__.py:3`,
    `repositories/workspace_repository.py:294` — „Notion-Vault" → „intern".
- [ ] **WP-5 — Verifikation:** ruff/mypy/pytest (nur Kommentare/Docstrings
  betroffen, aber gegenprüfen). `git ls-files | xargs grep notion` → nur noch
  harmlose Produkt-Treffer (`playbook_id`-API-Feld) + Platzhalter.
- [ ] **WP-6 — Branch auf main bringen** (PR #211 gemerged), Commit + Push +
  Draft-PR.

## Bewusst NICHT

- History-Rewrite (User-Entscheidung; IDs gewähren ohne Auth keinen Zugriff).
- `.claude/project.example.json` bleibt (nur Platzhalter, dokumentiert die
  lokale Datei-Konvention; keine echten IDs).
- Produkt-`playbook_id` (Who2Be-MCP-API-Feld) in mcp-claude-code.md + Models-Tests
  — kein Notion, bleibt.

## Notes

2026-06-14 0832 — V1.0 Initial. Diese Plan-Datei wird mit WP-3 selbst untracked
(landet im gitignored `.claude/plan/`), bleibt aber lokal als Living-Doc.
