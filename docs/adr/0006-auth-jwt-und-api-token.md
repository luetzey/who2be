# ADR-0006 — Auth: Supabase-JWT + eigene API-Token-Tabelle

- Status: Akzeptiert
- Datum: 2026-05-21
- Kontext: Who2Be MVP (PROJ-19)

## Kontext

Zwei Nutzergruppen greifen zu: Menschen ueber die Web-UI und Agenten ueber den
MCP-Server. Der MVP-Scope legt fest: Supabase Auth (Email/Passwort + JWT) fuer
die Web-UI, eine eigene API-Token-Tabelle fuer Agenten.

## Optionen

Die Aufteilung selbst ist durch den Projekt-Scope vorgegeben. Offen war die
Verifikation des Supabase-JWT in der API:

- **A — JWT lokal verifizieren:** HS256-Signatur gegen das Supabase-
  `JWT_SECRET` pruefen, ohne Netz-Aufruf. Schnell, aber das Secret muss
  vorliegen.
- **B — JWT bei Supabase verifizieren:** Pro Request ein Aufruf an Supabase.
  Kein Secret im API-Prozess, aber Latenz und Abhaengigkeit pro Request.

## Entscheidung

Web-Login laeuft client-seitig direkt gegen Supabase Auth; die API verifiziert
das ausgestellte JWT **lokal** (Option A, HS256, `JWT_SECRET`) und liest `sub`
als `owner_id`. Agenten senden einen `w2b_`-praefixierten API-Token; die API
hasht ihn (SHA-256) und schlaegt ihn in `api_token` nach. Eine gemeinsame
Dependency `get_current_user` erkennt den Weg am Token-Praefix und liefert in
beiden Faellen `owner_id`. Jede Persona-/Playbook-Query filtert serverseitig
nach `owner_id`.

## Konsequenzen

- Einheitlicher `owner_id`-Kontext fuer beide Auth-Wege — eine Autorisierungs-
  Logik fuer Web und Agenten.
- API-Token werden nur gehasht gespeichert; der Klartext wird genau einmal bei
  der Erstellung zurueckgegeben und ist widerrufbar (`revoked_at`).
- Das Supabase-`JWT_SECRET` muss als Secret im API-Prozess vorliegen (Env).
- Kein komplexes Rollensystem (Out of Scope MVP): ein Owner pro Persona/
  Playbook.
