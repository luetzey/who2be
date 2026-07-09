# LLM-Optimierung: Notion-Standards → Repo-Markdown (`docs/standards/`)

**Stand:** 2026-06-14 0947 · **Branch:** `claude/exciting-fermi-d0imfe`
**Scope (User):** Option B — governing Standards aus Notion als self-contained
Markdown materialisieren + kanonische LLM-Einstiegsschicht. De-Dup: wo
ADRs/Skills es abdecken → verlinken statt kopieren.

## Ziel

Ein LLM (jedes Tool) versteht das Projekt aus dem Repo allein, folgt einer
„single source" pro Standard und hat eine klare Arbeitsmethode → weniger Drift,
sauberer Code.

## Notion-Quellen (identifiziert)

- Coding-Standards (Composite): `367be537-2ab8-8193-8a8a-ccf264e66209`
  - Clean-Code-Style: `367be537-2ab8-818d-9864-fb1468f4a75b`
  - Test-Strategie & QA: `367be537-2ab8-81f9-9dd2-eeff15b35422`
  - Repo-Memory-Standards: `37cbe537-2ab8-81ff-9401-f8c81a4930b2`
  - Architektur-Standards + Design-Prinzipien (IDs via Composite)
- Security-Standards: `367be537-2ab8-81d9-bf14-e274fbde54c4`
  - Security-Infra-Standards: `376be537-2ab8-8107-a045-f88d4396ca28`
- Code-Task-Flow (Methode): `367be537-2ab8-817d-9124-e04211e23c59`
- Frontend-Standards: `36cbe537-2ab8-81db-a042-fe2bdf4eea1d`
- Compliance-Standards (DE/SaaS): `376be537-2ab8-8150-a55d-e6906c200ae2`
  (Inhalt weitgehend in `docs/compliance/` → primär verlinken)

## Ziel-Struktur

```
AGENTS.md                         # tool-agnostischer Einstieg; CLAUDE.md verweist drauf
docs/standards/
  README.md                       # Index: welche Regel wo
  engineering-method.md           # de-personalisiert aus Code-Task-Flow
  coding-standards.md             # Clean-Code + Architektur + Design-Prinzipien (+ Skill/ADR-Links)
  testing-standards.md            # Test-Strategie & QA / TDD / Pyramide (+ ADR-0041, ex-0032)
  security-standards.md           # Zero-Trust/fail-closed/Auth/Infra (+ Security-Findings/ADRs)
  frontend-standards.md           # konsolidiert design-language + react-skill
  compliance-standards.md         # Pointer auf docs/compliance + Kurzfassung
```

## Arbeitspakete

- [x] **WP-1** Notion-Kern-Standards gefetcht (Composite, Code-Task-Flow,
  Clean-Code, Test-Strategie, Architektur, Design-Prinzipien, Security,
  OSS-License, Git, Repo-Memory). ✅
- [x] **WP-2** `docs/standards/` geschrieben: README, engineering-method,
  coding-, testing-, security-, frontend-, compliance-standards. ✅
- [x] **WP-2b** (Bonus) `.claude/context/` Projekt-Gedächtnis materialisiert
  (PROJECT/ARCHITECTURE/DECISIONS/STATE) — Repo-Memory-Standards = Anti-Drift-Kern. ✅
- [x] **WP-3** `AGENTS.md` (Root) + CLAUDE.md-Pointer auf docs/standards/ +
  .claude/context/. ✅
- [x] **WP-4** Verifikation: Links lösen auf, keine Notion-IDs/URLs in neuen
  Dateien (de-personalisiert). ✅
- [ ] **WP-5** Commit + Push + Draft-PR.

## Prinzipien

- **De-personalisieren:** Coder-/Notion-/Agent-OS-Spezifika raus; nur die
  projektneutrale Engineering-Regel bleibt.
- **Single Source:** jede Regel an genau einem Ort; sonst verlinken.
- **Kein Notion-Zwang:** Repo muss ohne Notion vollständig verständlich sein.

## Notes

2026-06-14 0947 — V1.0 Initial nach Scope-Entscheidung B.
