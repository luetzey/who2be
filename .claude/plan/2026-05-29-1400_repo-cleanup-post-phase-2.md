# Plan: Repo-Cleanup nach Phase-2-Closeout

**Status:** ✅ Done — siehe PR mit Conventional-Commit
`chore(repo): post-Phase-2-Cleanup`. F1–F5, F7–F9 umgesetzt. F6 (`.env.example`)
entfiel, weil die Keys bereits durch PR #51 ergänzt waren.

- Datum: 2026-05-29
- Branch: `claude/confident-archimedes-JR0G5`
- Vorlage: Post-Phase-2-Inventur (siehe Findings unten)

## Context

Phase 2 ist komplett gemerged (PR #38–#52), Closeout-PR #53 ist durch. Vor dem
Public-Switch und vor Aufnahme der nächsten Code-Arbeit (Security-Quick-Wins,
License-Setup, MCP-Write-Tools) ist eine Aufräum-Runde fällig: veraltete Endpoint-
Doku, ein paar Dead-Code-Reste, drift in Plan-Status-Markern und ein lokaler
Branch-Friedhof.

## Findings (Inventur 2026-05-29 13:50)

1. **`docs/architecture.md` Endpoint-Tabelle veraltet.** Zeilen 261–275+ listen
   `/v1/personas`, `/v1/playbooks`, `/v1/tokens` ohne Workspace-Prefix. Phase-2.1a
   hat das hart auf `/v1/workspaces/{ws_id}/...` umgestellt. Resources, Dashboard,
   Members, Invitations fehlen in der Tabelle komplett.

2. **`apps/api/src/who2be_api/main.py:4` Docstring** sagt `Auth (\`/v1/tokens\`)` —
   stimmt seit 2.1a nicht mehr.

3. **`apps/api/tests/test_cors.py`** macht Preflight-Probe gegen `/v1/personas` —
   semantisch tot, läuft nur grün weil Starlette OPTIONS catch-all liefert. Auf
   eine echte Route umstellen (`/v1/me` als Top-Level).

4. **Dead-Code in `apps/api/src/who2be_api/core/security.py`:** Dataclass
   `TokenAuth` (Zeilen 72–77) ist unused — einziger Import nirgends, die echte
   Shape ist `TokenAuthRow` im Repo. Entfernen.

5. **Lokaler Branch-Friedhof:** `claude/determined-shannon-B3Ppm` (PR #51 gemerged)
   liegt noch lokal. Löschen.

6. **`.env.example`** trägt die zwei neuen Keys aus 2.3-B nicht: `SUPABASE_SERVICE_KEY`
   (GoTrue-Invite-API) und `WEB_BASE_URL` (Accept-Link-Basis).

7. **Plan-Status-Drift:** 34 ältere Plan-Files (MVP / Phase 1 / Frontend-Phasen 6/7/8)
   haben keinen `✅ Done`-Marker, obwohl die Arbeit längst gemerged ist. Die drei
   wirklich aktiven Plans (License-Setup, Public-Switch, Enterprise-License) bleiben
   ohne Marker.

8. **`docs/local-smoke.md`** deckt nur den MVP-Flow ab. Plan §Verifikation pro Phase
   verlangt einen End-to-End-Smoke mit Org → Workspace → Persona-Draft → Promote →
   Resource → Block-Link → Invite. Auf Phase-2-Stand bringen.

9. **`docs/security-findings.md`** (Phase 1) und `docs/security-findings-phase-2.md`
   (Phase 2) stehen nebeneinander ohne Cross-Link. Index am Anfang beider Files
   ergänzen.

## Scope

### IN

- F1: `docs/architecture.md` Endpoint-Tabelle auf Phase-2-Stand bringen
  (Workspace-Prefix, Resources, Dashboard, Members, Invitations).
- F2: `main.py` Docstring korrigieren.
- F3: `test_cors.py` Preflight-Pfade auf `/v1/me` umstellen.
- F4: `TokenAuth` Dead-Code entfernen.
- F5: Lokaler Branch `claude/determined-shannon-B3Ppm` löschen.
- F6: `.env.example` um `SUPABASE_SERVICE_KEY` + `WEB_BASE_URL` ergänzen.
- F7: Sammel-Edit der 34 alten Plan-Files — Status-Marker `✅ Done`
  (oder `🗄 Archiviert — implementiert in <PR>`) flippen. Pragmatisch ohne
  exakte PR-Refs für die alten — nur "abgeschlossen, siehe Master-Roadmap".
- F8: `docs/local-smoke.md` um Phase-2-Smoke-Sektion erweitern.
- F9: Cross-Link zwischen den zwei Security-Findings-Files.

### OUT

- Security-Findings F-Phase2-01..03 fixen — eigener Code-PR, gehört nicht in den
  Cleanup.
- CSP/Header-Pass (F-12) — gehört zum Public-Switch-Plan.
- Inhalte der drei aktiven Backlog-Plans bewerten — bleibt für deren Bearbeitung.
- `docs/codebase-review-2026-05-24.md` umschreiben — historisches Doc, lass es liegen.

## Verifikation

- `uv run ruff check .` clean
- `uv run mypy .` clean (TokenAuth-Removal darf keine Re-Imports brechen)
- `uv run pytest -q` grün (CORS-Tests grün, kein anderes Test bricht durch
  TokenAuth-Removal)
- `git diff` zeigt nur die im Scope gelisteten Files
- Web-Stack nicht angefasst → `npm`-Gates nicht nötig

## Deliverable

Ein PR `docs/repo-cleanup-post-phase-2`. Conventional-Commit:
`chore(repo): post-Phase-2-Cleanup — docs, dead code, env, plan-marker`.
