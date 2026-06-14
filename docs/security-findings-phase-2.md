# Security-Review — Phase 2 (Tenancy + Status + Resources + Multi-User-RBAC)

> Phase-1-Review (MS-3 H3 — Auth/SQL/CORS/Rate-Limit/MCP) liegt in
> [`security-findings.md`](./security-findings.md).

- Datum: 2026-05-29
- Methodik: `security-reviewer`-Subagent (read-only). Acht Themen-Bereiche
  laut Plan §Cross-cutting Security
  (`.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`).
- Scope-Begrenzung: kein Penetrationstest gegen Live-Instanz, keine A11y/Lint/
  Test-Fixture-Pruefung, kein Dependency-CVE-Scan. Frontend nur an den im
  Auftrag genannten Render-Stellen geprueft.
- Aufbau analog `docs/security-findings.md`.

## Zusammenfassung

8 Bereiche geprueft: urspruenglich **6 PASS, 2 REVIEW, 0 FAIL**; die beiden
REVIEW-Bereiche sind inzwischen geschlossen (Stand 2026-06-14, siehe
Findings-Tabelle). Drei Findings (F-Phase2-01, F-Phase2-02, F-Phase2-03) —
alle inzwischen **Closed**, keine Critical.
Cross-Workspace-Isolation, Status-Promotion-RBAC, Invite-Token-Hashing
und Single-Use, BlockNote-XSS-Profil, API-Token-Snapshot-Verhalten,
Last-Admin-Invariante und die JWT-Validation sind sauber.
Loecher beim Rate-Limit auf Member-Mutationen (PATCH/DELETE) und auf
PUT `persona_playbooks`/PATCH `workspaces`. `persona_playbook.list_linked`
filtert nicht explizit auf `workspace_id` (Defense-in-Depth, kein
realer Leak — Composite-FK + vorheriger Membership-Check decken ab).

## Findings-Tabelle

| ID            | Severity | Bereich            | Titel                                                          | Status |
| ------------- | -------- | ------------------ | -------------------------------------------------------------- | ------ |
| F-Phase2-01   | Medium   | Rate-Limit         | Fehlende `@limiter.limit(write_limit)` auf Member/Link-Mutating | Closed |
| F-Phase2-02   | Low      | Cross-Workspace    | `list_linked` ohne expliziten `workspace_id`-Filter (Defense)  | Closed |
| F-Phase2-03   | Low      | Cross-Workspace    | `workspace_repository.fetch/update_name` ohne `workspace_id`-Re-Bind | Closed |

## 1. Cross-Workspace-Read — CLOSED (war REVIEW)

Geprueft: alle `repositories/*.py`. Persona, Playbook, Resource, Token,
Invitation und Member-Reads tragen durchgaengig `WHERE workspace_id = $X`.
Composite-FKs (`persona_playbook`, `playbook_resource_link`) erzwingen
DB-seitig die Workspace-Bindung, der `set_links`-Pfad prueft zusaetzlich
in der Transaktion mit `FOR UPDATE`. Status-History bekommt mangels eigener
`workspace_id`-Spalte einen Subquery-Filter ueber das Aggregat.

Belege fuer den Pass:
- `apps/api/src/who2be_api/repositories/persona_repository.py:160-200, 281-310`
- `apps/api/src/who2be_api/repositories/playbook_repository.py:161-217, 288-317`
- `apps/api/src/who2be_api/repositories/resource_repository.py:142-181, 248-277`
- `apps/api/src/who2be_api/repositories/token_repository.py:82-130`
- `apps/api/src/who2be_api/repositories/invitation_repository.py:83-91, 124-132`
- `apps/api/src/who2be_api/repositories/workspace_member_repository.py:43-100`
- `apps/api/src/who2be_api/repositories/dashboard_repository.py:24-62`
- `apps/api/src/who2be_api/repositories/persona_playbook_repository.py:97-138`
- `apps/api/src/who2be_api/repositories/playbook_resource_link_repository.py:99-110, 134-181`

### F-Phase2-02 — `list_linked` ohne expliziten `workspace_id`-Filter (Low, Review)

- **Bereich:** `apps/api/src/who2be_api/repositories/persona_playbook_repository.py:66-95`
- **Beschreibung:** `list_linked(persona_id, …)` filtert nur ueber `pp.persona_id`
  und joint dann auf `playbook`. Workspace-Sicherung kommt allein aus dem
  vorgelagerten `persona_belongs_to`-Check in
  `services/persona_playbook_service.py:30`. Composite-FK aus 0014 stellt
  ausserdem sicher, dass alle `pp`-Rows mit der Persona im selben Workspace
  liegen — kein realer Leak.
- **Risiko:** Wenn ein kuenftiger Caller `list_linked` direkt nutzt und den
  Membership-Check vergisst, leakt das Querverknuepfungen. Defense-in-Depth
  fehlt.
- **Empfehlung:** Signatur auf `list_linked(workspace_id, persona_id, …)`
  ziehen und SQL um `AND pp.workspace_id = $X` ergaenzen (analog
  `playbook_resource_link_repository`).
- **Fix (2026-06-14):** `list_linked` traegt jetzt `workspace_id` als ersten
  Parameter, das SQL filtert `WHERE pp.persona_id = $1 AND pp.workspace_id = $2`.
  Beide Service-Call-Sites reichen `ctx.workspace_id` durch; Regressionstest
  `test_list_links_scopes_lookup_to_context_workspace`. **Status: Closed.**

### F-Phase2-03 — `workspace_repository.fetch/update_name` ohne Re-Bind (Low, Review)

- **Bereich:** `apps/api/src/who2be_api/repositories/workspace_repository.py:54-91`,
  `apps/api/src/who2be_api/routers/workspaces.py:35-47`
- **Beschreibung:** `fetch(workspace_id)` und `update_name(workspace_id, name)`
  arbeiten auf reiner ID, ohne Membership-Filter. Im Router wird die
  Berechtigung durch `get_current_workspace` durchgesetzt (Pfad-Parameter ==
  Repo-Argument), sodass es keinen Cross-WS-Leak gibt. Trotzdem Defense-in-
  Depth schwach.
- **Empfehlung:** Bei `PATCH /workspaces/{workspace_id}` zusaetzlich
  `require_role(ctx, admin)` setzen (Name-Aenderung ist heute auch fuer
  `viewer`/`editor` offen) und in den SQL-Queries den `workspace_id` aus dem
  Member-Kontext re-binden.
- **Fix (Track C / bestaetigt 2026-06-14):** `routers/workspaces.py::update_workspace`
  gatet mit `require_role(ctx, WorkspaceRole.admin)`; der `workspace_id` aus dem
  Pfad ist via `get_current_workspace` an den Member-/Token-Kontext gebunden und
  zugleich der PK der `workspace`-Zeile — `fetch`/`update_name` schluesseln genau
  darauf, ein separater Re-Bind ist ohne eigene Spalte gegenstandslos.
  **Status: Closed.**

## 2. Status-Promotion / Rolle-Drift — PASS

Geprueft: `services/version_status.py` + `core/security.py::require_role`.

- `required_role_for_transition` (`apps/api/src/who2be_api/services/version_status.py:70-82`):
  Promote-to-Active und Active→Inactive verlangen `admin`, alles andere `editor`.
- Gate-Reihenfolge in `_transition`
  (`apps/api/src/who2be_api/services/version_status.py:163-167`): erst
  `validate_transition` (409 bei unzulaessigem Ziel), dann
  `require_role(ctx, …)` (403). Korrekt — der Role-Check kommt nicht zu
  frueh ("404-vor-403"-Fall) und nicht zu spaet (Promote-Pfad wird vorher
  nicht ausgefuehrt).
- API-Token-Pfad nutzt die gepinnte Snapshot-Rolle aus `api_token.role`
  (`core/security.py:80-95, 249-265`) — kein Re-Lookup gegen
  `workspace_member` im Token-Pfad, JWT-Pfad bekommt die effektive Rolle aus
  `workspace_member` (`core/security.py:274-289`). Trennung sauber.

## 3. Invite-Token-Replay — PASS

Geprueft: `repositories/invitation_repository.py` + `services/invitation_service.py`.

- Klartext nie persistiert — nur `hash_token(plaintext)` geht in die DB
  (`apps/api/src/who2be_api/services/invitation_service.py:36-49`).
  Klartext einmalig im 201-Body und per `send_invitation_email` raus.
- `accept` ist single-use und transaktional
  (`apps/api/src/who2be_api/repositories/invitation_repository.py:93-122`):
  `SELECT … FOR UPDATE` haelt die Zeile, der Zustand wird auf
  `accepted_at IS NULL AND revoked_at IS NULL AND expires_at > now()`
  geprueft, danach `INSERT … ON CONFLICT … DO NOTHING` + `UPDATE … SET
  accepted_at = now()` — alles in einer Transaktion.
- Mapping auf HTTP: `gone` → 410, `not_found` → 404, `accepted` → 200
  (`apps/api/src/who2be_api/services/invitation_service.py:62-81`).
- Wer den Klartext-Hash erraet, verliert: 256 Bit Entropie, Hash-Lookup
  geht durch denselben SHA-256-Pfad wie API-Token (`hash_token` aus
  `core/security.py:59-61`).

## 4. BlockNote-XSS — PASS

Geprueft: `apps/web/src/features/resources/components/ResourceEditor.tsx`
und alle Stellen, die Resource-Content rendern.

- Kein `dangerouslySetInnerHTML` im gesamten `apps/web/src/`-Tree (Grep
  liefert keine Treffer; die im `node_modules`-Stack gefundenen Vorkommen
  liegen ausserhalb des Reviews).
- `ResourceEditor` rendert ueber `BlockNoteView` mit
  `editor.document as unknown as ResourceBlock[]` — ProseMirror-basierte
  Render-Pipeline, keine Roh-HTML-Einschleusung. Konform ADR-0022.
- `LinkedBlocksList`
  (`apps/web/src/features/playbooks/components/LinkedBlocksList.tsx:22-26`)
  rendert den vom Backend gelieferten `preview` als JSX-Textknoten — React
  escaped automatisch. Die Backend-Vorschau zieht ueber `block_plain_text`
  (`apps/api/src/who2be_api/repositories/playbook_resource_link_repository.py:25-51`)
  nur die `text`-Felder, keinen Style/HTML-Anteil — doppelte Defense.
- "Insel"-Ausnahme aus ADR-0022 ist auf den BlockNote-Renderer beschraenkt
  und akzeptiert.

## 5. API-Token-Snapshot-Verhalten — PASS

Geprueft: `core/security.py` + `repositories/token_repository.py`.

- Snapshot-Rolle wird beim Insert konsumiert
  (`apps/api/src/who2be_api/repositories/token_repository.py:62-80`) und
  bleibt bestehen — `fetch_auth_by_hash` filtert nur auf `revoked_at IS NULL`
  (`token_repository.py:109-121`).
- `get_current_workspace` liest `token_role` aus `CurrentPrincipal`
  (`core/security.py:255-265`), **nicht** aus `workspace_member`. Damit
  ueberlebt der Token einen User-Downgrade — bewusste Spec (ADR-0023,
  Plan §2.3-B).
- Revoke-Pfad: `revoked_at IS NOT NULL` faellt aus `fetch_auth_by_hash`
  heraus (`token_repository.py:113`), `resolve_principal` raised 401
  (`core/security.py:179-183`). `touch_last_used` schreibt selbst nur, wenn
  `revoked_at IS NULL` (`token_repository.py:132-137`) — kein Last-Used-
  Update auf widerrufene Tokens.
- Token-Workspace-Pin in `get_current_workspace`
  (`core/security.py:249-258`): Path != Token-WS → 403. Cross-WS-Token-Reuse
  ist damit geschlossen.

## 6. Last-Admin-Invariante — PASS

Geprueft: `repositories/workspace_member_repository.py:51-100`.

- `update_role`: nur wenn `current == "admin"` und Ziel-Rolle != admin,
  laeuft der `_last_admin`-Check. `count(*) WHERE role='admin'` mit Sperre
  ueber `SELECT … FOR UPDATE` auf der Member-Zeile (Zeile 56-60). Wirft
  `LastAdminError`.
- `remove`: analoge Logik (`workspace_member_repository.py:75-92`).
- Sperre auf der Quell-Member-Row reicht *nicht* aus, um zwei
  *parallel* downgrade-Versuche auf verschiedenen Members zu serialisieren;
  asyncpg-Default-Isolation (READ COMMITTED) liesse beide Selects gleichzeitig
  `admin_count=2` lesen. Der Count `<= 1` plus die Transaktion fangen den
  Self-Downgrade aber sicher ab; bei Parallel-Drop von zwei *verschiedenen*
  Admins koennte die Invariante gerissen werden.
- **Empfehlung (kein Finding, Anmerkung):** Wenn das in Praxis vorkommt, ein
  Advisory-Lock pro `workspace_id` vor dem Count anlegen. Aktuell
  Annahme-konform — vermerkt.
- **Umgesetzt (bestaetigt 2026-06-14):** `PgWorkspaceMemberRepository` haelt vor
  `update_role`/`remove` ein `pg_advisory_xact_lock(hashtext('ws_admins:'||
  workspace_id))` (`workspace_member_repository.py::_lock_workspace_admins`).
  Damit serialisieren parallele Admin-Downgrades/Removals desselben Workspaces
  auch unter READ COMMITTED — die Last-Admin-Invariante ist jetzt race-fest.

## 7. JWT-Validation — PASS

Geprueft: `apps/api/src/who2be_api/core/security.py:139-170`.

- `audience="authenticated"` plus `_JWT_ALLOWED_ROLES = {"authenticated"}`
  (`core/security.py:38-39, 158-161`) → `service_role` und andere
  Supabase-Rollen werden nicht als Owner akzeptiert.
- `issuer = supabase_url/auth/v1` (`core/security.py:44-52, 145, 152`) —
  optional, leer bei Dev. Geprueft, wenn gesetzt.
- `require=["exp","sub","aud"]` (`core/security.py:153`) erzwingt die
  Pflichtfelder.
- `sub` wird auf UUID gemappt, Fehler → 401 (`core/security.py:162-168`).

Direkt verglichen mit F-03 aus `docs/security-findings.md` — alle
dortigen Patches bestehen weiter.

## 8. Rate-Limit auf Mutating-Endpoints — CLOSED (war FAIL/REVIEW)

Geprueft: alle `routers/*.py`. Erfasst (PASS):
- `routers/personas.py:64, 77, 103` (POST/PUT/Transition)
- `routers/playbooks.py:66, 79, 105`
- `routers/resources.py:62, 75, 101`
- `routers/tokens.py:30` (POST)
- `routers/invitations.py:53, 74` (POST + Accept)
- `routers/organizations.py:49, 64`
- `routers/playbook_resources.py:47` (PUT)

### F-Phase2-01 — Mutationen ohne `write_limit` (Medium, Closed)

- **Bereiche:**
  - `apps/api/src/who2be_api/routers/members.py:40-45` — `PATCH /members/{user_id}` (Rolle-Aenderung)
  - `apps/api/src/who2be_api/routers/members.py:48-51` — `DELETE /members/{user_id}` (Mitglied entfernen)
  - `apps/api/src/who2be_api/routers/persona_playbooks.py:43-50` — `PUT /personas/{persona_id}/playbooks`
  - `apps/api/src/who2be_api/routers/workspaces.py:42-47` — `PATCH /v1/workspaces/{workspace_id}`
  - `apps/api/src/who2be_api/routers/invitations.py:67-70` — `DELETE /invitations/{invitation_id}` (Revoke)
  - `apps/api/src/who2be_api/routers/tokens.py:51-53` — `DELETE /tokens/{token_id}` (Revoke)
- **Beschreibung:** Diese Endpunkte mutieren Persistenz, sind aber nicht im
  Rate-Limiter-Bucket. Auftrag verlangt explizit Limit auf Invitation-Create
  (vorhanden), Member-Update (fehlt), Token-Create (vorhanden) und Transition
  (vorhanden). Zusaetzlich fallen revoke-Pfade und der Link-Setter auf.
- **Risiko:** Authentifizierter Aufrufer (z. B. kompromittierter editor-Token
  in einem Multi-User-WS) kann unbegrenzt Members aktualisieren / Links
  ueberschreiben — DB-Pressure und Audit-Log-Spam. Bei Membership-Mutationen
  ist das ausserdem ein Anti-Brute-Brick gegen "Wer ist admin?"-Probes via
  403-Timing.
- **Empfehlung:** `@limiter.limit(write_limit)` + `request: Request`-Parameter
  auf den oben aufgelisteten Handlern ergaenzen (analog Muster in
  `routers/tokens.py:29-34`).
- **Fix (2026-06-03, Branch `feat/security-findings-prelaunch`):** `@limiter.limit(write_limit)`
  + `request: Request` auf allen gelisteten Handlern ergaenzt — `members.py`
  (`update_member_role`, `remove_member`), `persona_playbooks.py`
  (`set_persona_playbooks`), `playbook_composition.py` (`set_playbook_composes`),
  `workspaces.py` (`update_workspace`, `delete_workspace`), `invitations.py`
  (`revoke_invitation`) und `tokens.py` (`revoke_token`). `playbook_resources.py`
  (`set_resource_links`) und `resource_composition.py` (`set_sub_resources`)
  trugen das Limit bereits. Regressionstest:
  `apps/api/tests/test_rate_limit_mutations.py` belegt pro Endpunkt den 429
  nach Limit-Ueberschreitung (parametriert, skippt ohne DB wie die uebrigen
  Integrationstests). **Status: Closed.**

## Akzeptanz / Ampel

**Gesamt-Ampel:** Grün. Keine Critical/High. **Alle Phase-2-Findings
geschlossen** (Stand 2026-06-14): F-Phase2-01 Rate-Limit (2026-06-03),
F-Phase2-02 `list_linked`-Filter (2026-06-14), F-Phase2-03 Role-Gate +
Re-Bind (Track C, bestaetigt), Last-Admin-Advisory-Lock (umgesetzt) sowie der
CSP/Header-Pass (F-12, 2026-06-03). Keine offenen Public-Switch-Blocker mehr
aus dieser Datei.

### TODO vor Public-Switch

1. **F-Phase2-01** — ✅ **erledigt (2026-06-03)**: `@limiter.limit(write_limit)`
   auf alle in §8 gelisteten Mutationen gezogen (`routers/members.py`,
   `routers/persona_playbooks.py`, `routers/playbook_composition.py`,
   `routers/workspaces.py`, `routers/invitations.py`-Revoke,
   `routers/tokens.py`-Revoke); Regressionstest
   `apps/api/tests/test_rate_limit_mutations.py`.
2. **F-Phase2-02** — ✅ **erledigt (2026-06-14)**: `list_linked` traegt jetzt
   `workspace_id` als ersten Parameter, SQL filtert
   `AND pp.workspace_id = $2`, beide Service-Call-Sites reichen
   `ctx.workspace_id` durch. Regressionstest
   `test_list_links_scopes_lookup_to_context_workspace`.
3. **F-Phase2-03** — ✅ **erledigt (Track C, bestaetigt 2026-06-14)**:
   `update_workspace` gatet `require_role(ctx, admin)`; der Pfad-`workspace_id`
   ist via `get_current_workspace` an den Kontext gebunden und zugleich PK der
   `workspace`-Zeile — separater Re-Bind gegenstandslos.
4. **Last-Admin (Anmerkung §6)** — ✅ **erledigt**: Advisory-Lock
   (`pg_advisory_xact_lock`) auf `workspace_id` vor dem `_last_admin`-Count in
   `update_role`/`remove` umgesetzt.
5. **CSP/Header-Pass (offen aus Phase 1, F-12)** — ✅ **erledigt (2026-06-03)**:
   `deploy/hetzner/Caddyfile` finalisiert (HSTS, X-Content-Type-Options,
   X-Frame-Options, Referrer-Policy, Permissions-Policy, Cross-Origin-Opener-
   Policy + per-Subdomain CSP mit `object-src 'none'`/`form-action`).
   `default-src 'self'` auf `app.<domain>` mit `style-src 'unsafe-inline'` fuer
   die BlockNote-Insel (ADR-0022). Smoke: `deploy/hetzner/tests/test_headers.sh`.
   Siehe `docs/security-findings.md` §F-12.

## Public-Tauglichkeits-Review (2026-06-02, FSL-/Public-Prep)

Im Rahmen der Public-Switch-Vorbereitung (Track L,
`.claude/plan/2026-06-02-1819_followups-rls-mollie-auth-fsl.md` §3.4) wurden die
offenen Findings dieser Datei (**F-Phase2-01**, **F-Phase2-02**,
**F-Phase2-03**) auf Public-Tauglichkeit geprueft.

**Befund:** Im Kern public-tauglich, keine Redaktion vorgenommen; **eine
Empfehlung fuer den spaeteren Flip.**

- Alle drei Findings sind Risiko-Klassifikation + Mitigation-Empfehlung — **kein
  PoC, kein Reproduce-Code, keine Secrets.** F-Phase2-02/03 sind reine
  Defense-in-Depth-Hinweise ohne realen Leak.
- **F-Phase2-01** benennt konkret die Endpunkte ohne `write_limit` und einen
  403-Timing-Probe-Gedanken. Das ist der einzige fuer einen Angreifer leicht
  verwertbare Detailgrad. Bewertung: **nicht redigieren, sondern schliessen** —
  der Finding ist als „TODO vor Public-Switch" (oben, Punkt 1) ohnehin
  blockierend; eine Kuerzung der Beschreibung wuerde nur Tracking-Wert kosten,
  solange das Repo privat ist.

Hinweis: Der tatsaechliche Public-Flip ist **nicht** Teil dieses Schritts (Repo
bleibt privat). Die obigen „TODO vor Public-Switch"-Punkte (insb. F-Phase2-01
Rate-Limits und der CSP/Header-Pass) bleiben Voraussetzung fuer den Flip.
