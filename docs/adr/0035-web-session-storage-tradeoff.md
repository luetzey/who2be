# ADR-0035 — Web-Session im `sessionStorage` (akzeptiertes Rest-Risiko)

- Status: Abgeloest durch ADR-0052
- Datum: 2026-06-13
- Kontext: Repo-Review-Remediation — Plan
  `.claude/plan/2026-06-13-1512_repo-review-remediation.md` (Welle 1, QW-4).
  Interner Standard *Security-Standards* (Coding-Standards).
- Bezug: `apps/web/src/lib/supabase.ts`, `apps/web/src/auth/auth-token-context.ts`,
  ADR-0006 (Auth: Supabase-JWT + API-Token), F-12 (Security-Header/CSP in Caddy)

## Kontext

Der *Security-Standards*-Atomic benennt **„Auth-Tokens im Web-Storage — per XSS
abgreifbar"** als Anti-Pattern und schreibt vor: *„Tokens/Sessions in sicheren
Cookies (`httpOnly`/`Secure`/`SameSite`), nicht im Web-Storage."* Das Frontend
weicht hiervon bewusst ab:

- **API-Token (`w2b_…`)** liegen ausschliesslich **in-memory**
  (`auth-token-context.ts`, kein Storage) — konform.
- **Supabase-GoTrue-Session** (Access-/Refresh-Token) liegt im **`sessionStorage`**
  (`lib/supabase.ts`, eigener `sessionStorageAdapter`, `storageKey
  who2be.auth.session`).

Grund der Storage-Wahl: GoTrue ist ein **SPA-Client-Library** mit
`flowType: 'implicit'` — der Magic-Link-/Invite-Flow liefert die Tokens im
URL-Hash, `detectSessionInUrl` parsed ihn und muss die Session in einem Storage
ablegen, sonst ist sie nach dem ersten `getSession()` wieder weg (Invite-Flow
bricht auf `null`). Ein reiner `httpOnly`-Cookie-Pfad verlangt einen
**Backend-for-Frontend** (server-seitiger Token-Tausch + Cookie-Set) — die App
spricht aber direkt mit GoTrue, ohne eigenen Auth-BFF.

## Optionen

- **A — `httpOnly`-Cookie via Auth-BFF.** Standard-konform (Token nie im
  JS-Heap/Storage). Verlangt aber einen neuen server-seitigen Auth-Proxy, der
  GoTrue-Tokens gegen ein eigenes Session-Cookie tauscht, plus CSRF-Schutz.
  Erheblicher Umbau gegen ADR-0006 (Direkt-Client). Nicht jetzt.
- **B — `localStorage`.** Persistenz ueber Tab-Schliessung hinaus, aber **breiteste**
  XSS-Oberflaeche (Disk-persistent, alle Tabs). Verworfen.
- **C — `sessionStorage` + harte CSP, gewaehlt.** Tab-Lifetime statt Disk:
  der Token verschwindet beim Tab-Schliessen, kein dauerhaftes Bearer-Token auf
  der Platte. XSS-Restoberflaeche wird durch die zentrale **CSP in Caddy**
  (F-12, eine Header-Ebene) als primaere Verteidigung minimiert.

## Entscheidung

Option **C** als bewusstes, dokumentiertes **Rest-Risiko**. Die Abweichung vom
Cookie-Ideal ist akzeptiert, solange:

- API-Token in-memory bleiben (nie in Storage),
- die Supabase-Session ausschliesslich `sessionStorage` (nie `localStorage`) nutzt,
- die CSP in Caddy scharf bleibt (F-12) — sie ist die tragende XSS-Abwehr,
- kein fremdes/ungesaubertes HTML in die App injiziert wird (Security-Standards:
  Untrusted-HTML sanitisieren).

## Konsequenzen

- **Positiv:** kein Auth-BFF noetig, ADR-0006-Direkt-Client bleibt; Tokens sind
  nicht disk-persistent; Magic-Link-/Invite-Flow funktioniert ohne Sonderpfad.
- **Negativ (akzeptiert):** ein erfolgreicher XSS koennte die laufende
  Tab-Session auslesen. Mitigation = CSP + Sanitizing, nicht Storage-Isolation.
- **Trigger fuer Re-Visit:** sobald ein server-seitiger Auth-Layer (BFF) ohnehin
  entsteht, ist Option A der Zielzustand — dann Session auf `httpOnly`-Cookie
  migrieren und diesen ADR ersetzen.
- Abgegrenzt: betrifft nur die **interaktive** Browser-Session. Der MCP-/
  Maschinen-Pfad nutzt `w2b_`-Token ueber `Authorization`-Header, kein Storage.
