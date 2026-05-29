# Security-Review — Phase 2 (Tenancy + Status + Resources + Multi-User-RBAC)

- Datum: 2026-05-29
- Methodik: `security-reviewer`-Subagent (read-only). Acht Themen-Bereiche
  laut Plan §Cross-cutting Security
  (`.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`).
- Scope-Begrenzung: kein Penetrationstest gegen Live-Instanz, keine A11y/Lint/
  Test-Fixture-Pruefung, kein Dependency-CVE-Scan. Frontend nur an den im
  Auftrag genannten Render-Stellen geprueft.
- Aufbau analog `docs/security-findings.md`.

## Zusammenfassung

8 Bereiche geprueft: **6 PASS, 2 REVIEW, 0 FAIL**. Drei Findings
(F-Phase2-01, F-Phase2-02, F-Phase2-03) — alle Medium, keine Critical.
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
| F-Phase2-01   | Medium   | Rate-Limit         | Fehlende `@limiter.limit(write_limit)` auf Member/Link-Mutating | Open   |
| F-Phase2-02   | Low      | Cross-Workspace    | `list_linked` ohne expliziten `workspace_id`-Filter (Defense)  | Review |
| F-Phase2-03   | Low      | Cross-Workspace    | `workspace_repository.fetch/update_name` ohne `workspace_id`-Re-Bind | Review |

## 1. Cross-Workspace-Read — REVIEW

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

## 8. Rate-Limit auf Mutating-Endpoints — FAIL/REVIEW

Geprueft: alle `routers/*.py`. Erfasst (PASS):
- `routers/personas.py:64, 77, 103` (POST/PUT/Transition)
- `routers/playbooks.py:66, 79, 105`
- `routers/resources.py:62, 75, 101`
- `routers/tokens.py:30` (POST)
- `routers/invitations.py:53, 74` (POST + Accept)
- `routers/organizations.py:49, 64`
- `routers/playbook_resources.py:47` (PUT)

### F-Phase2-01 — Mutationen ohne `write_limit` (Medium, Open)

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

## Akzeptanz / Ampel

**Gesamt-Ampel:** Gelb. Keine Critical/High, aber drei offene Findings
(1× Medium Rate-Limit, 2× Low Defense-in-Depth) plus die Last-Admin-Race-
Anmerkung sollen vor dem Public-Switch adressiert werden.

### TODO vor Public-Switch

1. **F-Phase2-01** — `@limiter.limit(write_limit)` auf alle in §8 gelisteten
   Mutationen ziehen (`routers/members.py`, `routers/persona_playbooks.py`,
   `routers/workspaces.py`, `routers/invitations.py`-Revoke,
   `routers/tokens.py`-Revoke).
2. **F-Phase2-02** — `list_linked` um `workspace_id`-Filter ergaenzen
   (Defense-in-Depth gegen kuenftige Service-Refactors).
3. **F-Phase2-03** — `workspace_repository.update_name` mit `require_role(ctx,
   admin)` im Router gaten und im SQL den `workspace_id` re-binden.
4. **Last-Admin (Anmerkung §6)** — Advisory-Lock auf `workspace_id` vor dem
   `_last_admin`-Count erwaegen, falls Parallel-Downgrades realistisch werden.
5. **CSP/Header-Pass (offen aus Phase 1, F-12)** — Caddyfile-Header-Snippet
   muss vor Public-Switch greifen; bei Multi-User-Frontend mit BlockNote ist
   `default-src 'self'` Pflicht (Insel laesst keinen Inline-Style/Script
   stehen, ADR-0022).
