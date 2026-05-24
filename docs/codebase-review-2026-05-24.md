# Codebase-Review — Who2Be (Stand 2026-05-24)

- **Branch:** `claude/pensive-euler-UAAsq` (HEAD `2f3e83e`)
- **Reviewer:** Coder (Read-only-Pass auf MS-1-Abschluss)
- **Plan:** `/root/.claude/plans/bitte-berpr-fe-die-komplette-quiet-parnas.md`
- **Lifebeleg:**
  - Python: `uv run ruff check .` clean · `uv run mypy .` clean · `pytest -q` **72 passed, 6 skipped** (Integration-Marker skippt ohne DB).
  - Web: `npm run lint` clean · `npx tsc --noEmit` clean · `npm test` **19 passed (10 files)**.
  - CI (`.github/workflows/ci.yml`) bleibt gegen Postgres-Service gruen.

## 1 — Executive Summary

MS-1 (Web-UI minimal-funktional) ist code-seitig konsistent zur Roadmap.
Architektur bleibt sauber geschichtet, ADR 0001-0006 sind eingehalten, alle
sicherheitsrelevanten Pfade sind in Tiefe abgesichert (asyncpg-Param-Bindung,
Composite-FK + `FOR UPDATE`, SHA-256-Hash, JWT lokal HS256 mit `require:
[exp, sub]`).

**Ein P0-Finding blockt den Local-Smoke:** Die FastAPI-App haengt **keine
CORS-Middleware** ein, obwohl `cors_origin` in den Settings vorgesehen ist
(`apps/api/src/who2be_api/main.py:8-19` vs. `apps/api/src/who2be_api/core/config.py:21`).
Im Browser wird jeder Cross-Origin-Call von `http://localhost:5173` →
`http://localhost:8000` an `OPTIONS`-Preflights scheitern. Tests bleiben
gruen, weil sie ueber httpx-ASGI laufen, nicht ueber den Browser. **Fix
vor W6-Smoke noetig.**

Daneben drei P1-Punkte (UI-Feedback-Luecken, Hook-Duplizitaet, ungetestete
Module) und drei P2-Punkte (Polish/Backlog). Keine Hochrisiko-Findings
auf der Security-Achse jenseits des CORS-Themas.

## 2 — MS-1-Abnahme-Matrix

| Task | Acceptance laut Roadmap | Status | Beleg | Restrisiko |
|------|-------------------------|--------|-------|------------|
| W1 — Auth-Bridge | API-Calls aus Web tragen gueltigen Bearer, Override-Logik | **Done** | `apps/web/src/auth/useAuthToken.ts:8-15`, `apps/web/src/auth/AuthTokenProvider.tsx`, 4/4 useAuthToken-Tests | Override-Token nicht persistent — bewusst (W1-Plan) |
| W2 — Tokens-Page | Liste + Create (Klartext einmal) + Revoke | **Done** | `apps/web/src/pages/SettingsTokensPage.tsx`, 2 Vitest-Cases | Revoke-Fehler wird auf `createError`-State geschrieben — Anzeige nur, wenn vorher kein Fehler stand (P2) |
| W3 — Persona-Editor + Versionen | Create + PUT mit Version-Bump + Versionsliste | **Done** | `apps/web/src/pages/PersonaNewPage.tsx`, `PersonaDetailPage.tsx`, Create- + Version-Bump-Test | Save-Button ohne `disabled`-State waehrend laufendem PUT (P1) |
| W4 — Playbook-Editor + Versionen | analog W3 + Tag/Trigger | **Done** | `apps/web/src/pages/PlaybookNewPage.tsx`, `PlaybookDetailPage.tsx`, Version-Bump-Test | Save-Button ohne `disabled` (P1); PlaybooksPage selbst ohne Test (P1) |
| W5 — Persona↔Playbook-Linking-Hook | Hook + PUT-Body-Contract | **Done** | `apps/web/src/hooks/usePersonaPlaybooks.ts`, PUT-Contract-Test in PersonaDetailPage.test | — |
| W6 — Local-Smoke-Doc | `docs/local-smoke.md` + manuelle Abnahme | **Doku da, Abnahme offen** | `docs/local-smoke.md` (eingecheckt), Checkboxen leer | **CORS-P0 muss vor Abnahme fixed sein**, sonst scheitern alle Web-Schritte |

MS-1 ist **abnahmebereit, sobald CORS-Middleware aktiv ist und der User
die Local-Smoke-Checklist gruen abhakt**.

## 3 — Findings

### P0 — Blocker

#### F1: Keine CORS-Middleware in der FastAPI-App
- **Achse:** Security / Korrektheit / Local-Smoke
- **Datei:** `apps/api/src/who2be_api/main.py:8-19`
- **Beobachtung:** `app = FastAPI(...)` mountet `tokens`, `personas`,
  `playbooks`, `persona_playbooks` — aber **keine `CORSMiddleware`**.
  `Settings.cors_origin` (Default `"http://localhost:5173"`) ist in
  `core/config.py:21` definiert, wird aber nirgends gelesen.
- **Wirkung:** Browser-`OPTIONS`-Preflight fuer alle Mutating-Calls und
  fuer `Authorization`-Header gegen `localhost:8000` schlaegt ohne
  `Access-Control-Allow-*`-Header fehl. Web-Tests (Vitest/httpx) decken
  das nicht ab — sie reden direkt mit der ASGI-App und kennen kein CORS.
  Im Local-Smoke (W6 Schritte 3-4) erscheint im Browser "Failed to fetch".
- **Empfehlung:** `from fastapi.middleware.cors import CORSMiddleware` +
  `app.add_middleware(CORSMiddleware, allow_origins=[get_settings().cors_origin], allow_methods=["*"], allow_headers=["*"], allow_credentials=False)`
  vor `include_router`-Aufrufen. `cors_origin` ggf. zu Liste/CSV
  erweitern (`cors_origins: list[str]`), damit Hetzner-Subdomain in MS-2 dazukommt.
- **Aufwand:** S (≤ 30 Min inkl. Integrationstest).

### P1 — Wichtig vor MS-2

#### F2: Save-Button ohne `disabled`-State in den beiden Detail-Pages
- **Achse:** Code-Quality / UX
- **Dateien:**
  - `apps/web/src/pages/PersonaDetailPage.tsx:79-88` (Save-Button)
  - `apps/web/src/pages/PlaybookDetailPage.tsx:104-134` (Save-Button)
- **Beobachtung:** `handleSave` ruft `await api.updatePersona/Playbook`,
  aber es gibt keinen `saving`-State und kein `disabled={saving}` am
  Button. Mehrfach-Klicks → mehrfache PUTs → mehrfache neue Versionen.
  `PersonaNewPage`, `PlaybookNewPage`, `LoginPage` und `SettingsTokensPage`
  haben das Pattern korrekt (z.B. `apps/web/src/pages/PersonaNewPage.tsx`).
- **Empfehlung:** `const [saving, setSaving] = useState(false)`,
  `setSaving(true)` vor `await`, `setSaving(false)` im `finally`,
  `disabled={saving}` am Button.
- **Aufwand:** S (15 Min, 2 Dateien + 2 Test-Cases).

#### F3: Drei List-Hooks fast identisch — `useListData<T>`-Extraktion
- **Achse:** Code-Quality
- **Dateien:**
  - `apps/web/src/hooks/usePersonas.ts:1-36`
  - `apps/web/src/hooks/usePlaybooks.ts:1-36`
  - `apps/web/src/hooks/useTokens.ts:1-36`
- **Beobachtung:** 30 von 36 Zeilen sind 1:1 identisch. Nur der
  API-Call (`api.listPersonas` / `listPlaybooks` / `listTokens`) und der
  State-Key wechseln. Repo-CLAUDE.md sagt: "Drei aehnliche Zeilen besser
  als verfruehte Abstraktion" — drei **vollstaendig identische Hooks**
  ueberschreiten aber den Schwellwert.
- **Empfehlung:** Generischer Hook `useListData<T>(loader: () => Promise<T[]>)`
  unter `hooks/useListData.ts`; die drei bestehenden Hooks shrinken zu
  1-Zeiler-Aufrufen. Tests fuer den generischen Hook + Konsumenten bleiben.
- **Aufwand:** M (1-1.5h inkl. Tests).

#### F4: Test-Luecken — usePersonas/Playbooks/Tokens + PlaybooksPage
- **Achse:** Test-Coverage
- **Beobachtung:** Page-Tests (PersonasPage/PlaybookDetailPage/…) decken
  die Hooks indirekt ab, aber die generische Load-Fehler-Bahn (Network
  down → `error`-State) hat keinen Unit-Test. `apps/web/src/pages/PlaybooksPage.tsx`
  hat als einzige protected Page **gar keinen Test** (Filter-Logik via
  `useMemo` ist ungetestet).
- **Empfehlung:** 1 Test fuer `useListData` (Loading → Error-Pfad),
  1 Test fuer PlaybooksPage (Render + Tag-Filter). Mit F3 zusammen
  angehen.
- **Aufwand:** S (40 Min).

### P2 — Polish / Backlog

#### F5: API-Fehlermeldungen aus dem Backend gehen im Web verloren
- **Achse:** UX / Code-Quality
- **Datei:** `apps/web/src/api/client.ts:39-41`
- **Beobachtung:** Backend liefert auf `HTTPException(detail=...)` einen
  JSON-Body `{"detail": "Persona nicht gefunden."}`, das Web wirft aber
  `new ApiError(status, "Who2Be-API-Fehler (${status}).")` und verwirft
  `detail`. Folge: alle Fehlermeldungen sehen gleich aus, der User
  weiss nicht warum `404`/`401` kam.
- **Empfehlung:** Body lesen, wenn `content-type: application/json`, und
  `detail` als Message verwenden — sonst Fallback auf das aktuelle
  Generic.
- **Aufwand:** S (20 Min, ein Test-Case).

#### F6: `cors_origin` als einzelner String wird MS-2 sprengen
- **Achse:** Konfiguration
- **Datei:** `apps/api/src/who2be_api/core/config.py:21`
- **Beobachtung:** Im Cloud-Setup gibt es mindestens zwei zulaessige
  Origins (z.B. `https://app.<domain>` und ggf. Preview-Deployments).
  `cors_origin: str` zwingt zu einer Wildcard oder zu unsauberem Parsing.
- **Empfehlung:** Beim CORS-Fix (F1) gleich `cors_origins: list[str] = ["http://localhost:5173"]`
  schneiden — pydantic-settings parst CSV automatisch (`CORS_ORIGINS=a,b`).
- **Aufwand:** S, mit F1 buendeln.

#### F7: Revoke-Fehler in SettingsTokensPage landet auf `createError`-State
- **Achse:** UX
- **Datei:** `apps/web/src/pages/SettingsTokensPage.tsx` (handleRevoke)
- **Beobachtung:** Wenn `DELETE /v1/tokens/:id` fehlschlaegt, wird der
  Fehler in einem fuer Create-Fehler reservierten State angezeigt —
  inkonsistent.
- **Empfehlung:** Eigener `revokeError`-State oder gemeinsamer
  `pageError`-State. Niedrige Prioritaet — Revoke laufen heute selten in
  Fehler.
- **Aufwand:** S.

## 4 — Security-Pass auf MS-1-Niveau

Kein vollstaendiger `security-reviewer`-Pass — der ist explizit MS-3 H3
vorbehalten (siehe `.claude/plan/2026-05-24_who2be-mvp-roadmap.md` §MS-3).
Was im Read-Through aufgefallen ist:

| Pfad | Befund |
|------|--------|
| JWT-Verify (`core/security.py:48-68`) | HS256, `require=["exp","sub"]`, `verify_aud=False` (Supabase liefert mehrere Audiences). `sub` wird strikt zu `UUID` geparst, Fehler → 401. **OK.** |
| Token-Hashing (`core/security.py:30-37`) | `secrets.token_urlsafe(32)` (256 bit Entropy) + SHA-256 Hexdigest. Ohne Salt — fuer Hochentropie-Random-Tokens akzeptabel (kein Rainbow-Risiko). **OK fuer MVP.** Hand-Off-Note: H3 entscheidet, ob HMAC-mit-Server-Key besser passt. |
| SQL-Param-Bindung | Alle Statements parametrisiert. Auch `ANY($2::uuid[])` in `persona_playbook_repository.py:84-87` korrekt. `_escape_like` in `playbook_repository.py:25-27` maskiert LIKE-Wildcards. **OK.** |
| Owner-Isolation | Composite-Key `(owner_id, id)` in Migrations + WHERE-Klauseln in jedem Repo-Statement + `FOR UPDATE`-Lock vor `set_links` (`persona_playbook_repository.py:74-79`). **Defense-in-Depth korrekt.** |
| Pool-Bootstrap (`security.py:96-108`) | Pool wird **nach** Credential-Check geholt — fehlende Creds geben 401, fehlende DB 503. Korrekt. |
| MCP-Token-Forward (`apps/mcp/src/who2be_mcp/client.py:36, 47-61`) | Bearer-Header gesetzt, 401/404/5xx → `ToolError`. URL-Detail nur ins Log, nicht zum Agenten. **OK.** |
| CORS | **Siehe F1 — P0.** |
| Input-Validierung | Pydantic an allen Router-Boundaries (alle Routes haben `data: PersonaCreate`/`PersonaUpdate`/…). **OK.** |
| Token-Anzeige im Web (`SettingsTokensPage`) | Klartext-Token genau einmal im UI-Banner, kein localStorage-Persist. **OK.** |
| Web-Override-Token | Nur Memory (`AuthTokenProvider`, `useState`), kein Persist — konsistent mit Konvention. **OK.** |

**Hand-Off an MS-3 H3 (security-reviewer):** Pfad-Fokus auf
Rate-Limiting (existiert nicht — laut Plan H1 vorgesehen), strukturierte
Logs (H2), zusaetzlich Server-side-Audit der `set_links`-Race-Conditions
unter Concurrency. CORS dann bereits durch F1 erledigt.

## 5 — Architektur-Konformitaet (ADR 0001-0006)

| ADR | Thema | Konform? | Beleg |
|-----|-------|----------|-------|
| 0001 | Modularer Monolith — API ist einziger DB-Owner | **Ja** | `apps/mcp` redet ausschliesslich ueber `apps/mcp/src/who2be_mcp/client.py` HTTP; keine DB-Imports in MCP-Code. |
| 0002 | Schichten Router → Service → Repository | **Ja** | Pro Domaene genau eine Datei je Schicht; keine Router-Datei importiert `repositories/*` direkt (Validation per Grep), `repositories/*` taucht in Routern nur als FastAPI-Dependency auf, um den Service zu bauen. |
| 0003 | raw asyncpg + nummerierte SQL-Migrationen | **Ja** | 4 Migrationen `0001..0004*.sql`, idempotenter Runner `core/migrations.py`; alle Queries asyncpg-parametrisiert. Kein ORM. |
| 0004 | Versionierung ueber History-Tabellen | **Ja** | `persona`/`persona_version` + `playbook`/`playbook_version`; `current_version`-Bump in Transaktion mit `FOR UPDATE` (`persona_repository.py:105-125`, `playbook_repository.py:126-147`). `persona_playbook` ist bewusst nur Aktuell-Stand. |
| 0005 | MCP-Server als HTTP-Adapter | **Ja** | `apps/mcp/src/who2be_mcp/client.py` ist duenn (98 Zeilen), keine Geschaeftslogik; Tools in `server.py` delegieren nur. |
| 0006 | Dual-Auth Supabase-JWT + `w2b_`-Token mit SHA-256 | **Ja** | `core/security.py:71-83` Dispatch per Prefix, lokal verifiziertes JWT, gehashter Token in DB. |

## 6 — Test-Coverage-Bild

| Paket | Cases | Skipped | Auffaelligkeiten |
|-------|-------|---------|------------------|
| `apps/api` | 44 Unit + Integration | 6 (Integration ohne DB) | Vollstaendige Service- und Repo-Coverage |
| `apps/mcp` | 14 | 0 | `httpx.MockTransport` deckt 401/404/5xx-Pfade ab |
| `packages/models` | 20 | 0 | — |
| `apps/web` | 19 (10 files) | 0 | **PlaybooksPage ohne Test (F4)**, generische List-Hooks ohne Test (F4) |

Gesamt: **97 grueene Cases**. Kein Test wegen Code-Aenderung kaputt.

## 7 — Naechste Schritte / Empfehlung

1. **Sofort (vor W6-Smoke-Abnahme):** F1 + F6 als **ein** kleiner
   Patch (`feat(api): enable CORS for the web origin`) — CORSMiddleware
   einhaengen, `cors_origin` → `cors_origins: list[str]`, 1
   Integrations-Test (`OPTIONS /v1/personas` → 200 mit ACAO-Header).
2. **Vor MS-1-Done-Switch in Notion:** F2 (Save-`disabled`-State) als
   Polish-PR — 15-30 Min, schliesst eine echte UX-Klippe. Optional
   buendeln mit F5 (Backend-`detail` durchreichen) — derselbe Code-Pfad.
3. **Parallel zu MS-2-Start:** F3 + F4 als `chore(web): extract
   useListData hook + cover PlaybooksPage` — Refactor mit
   Test-Erweiterung, blockt nichts.
4. **Bleibt fuer MS-3 H3:** Rate-Limiting (H1), strukturierte Logs (H2),
   Security-Review-Pass (H3) — wie geplant.

**MS-1-Done-Switch in Notion:** **noch nicht** — erst nach Fix von F1
und nach abgehakter Local-Smoke-Checklist (`docs/local-smoke.md` §5).
