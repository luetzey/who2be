# Stack unter rootless Podman startklar: `.dockerignore` + nginx-Resolver

Karte: `t_95402784` (Befund aus dem Praxistest `t_e4e9eb2f`)
Stand: 2026-09-25, Branch `fix/podman-startklar-resolver`

## Outcome

Ein frisches `podman compose up --build` aus dem Repo-Wurzelverzeichnis baut
(kein 7-GB-Kontext) und der Signup antwortet mit 200 statt 502 — ohne dass der
Nutzer eine Datei anfasst. Docker-Verhalten bleibt bitgleich.

## Befund N-1 — Build-Kontext

`.worktrees/` ist lokal 7,0 GB (gemessen: `du -sh .worktrees` → `7.0G`) und
steht weder in `.dockerignore` noch in `.gitignore` (`git status` listet es als
`?? .worktrees/`). Beide Dockerfiles bauen mit `context: .` (Repo-Root).

Fix: `.worktrees` in `.dockerignore` **und** `.gitignore` (dort steht bisher nur
`.claude/worktrees/` — der tatsaechlich benutzte Pfad ist `.worktrees/`).

## Befund N-2 — hardcodierter Resolver

Betroffen (im lokalen Stack gemountet/gebaut):
- `apps/web/nginx.conf` — `resolver 127.0.0.11 valid=10s ipv6=off;`
- `supabase/gateway.conf` — dito, gemountet via `docker-compose.yml:117`

NICHT betroffen: `deploy/hetzner/supabase/auth-gateway.conf` (Server-Docker,
eigene Kopie, ausserhalb des Scopes dieser Karte).

Die Variablen-`proxy_pass`-Konstruktion bleibt unangetastet — sie loest ein
anderes Problem (IP-Caching nach Recreate) und ist genau der Grund, warum
ueberhaupt ein `resolver` gebraucht wird.

### Weiche: woher kommt die Adresse?

Die Karte laesst die Wahl. Drei Wege standen an:

- **A — Env-Variable mit Default `127.0.0.11`.** Nutzer muss unter Podman
  wissen, dass es sie gibt, und die richtige Adresse selbst herausfinden
  (`10.89.1.1` ist nicht stabil, sie haengt am Netz). Loest die stumme
  502-Falle also nicht.
- **B — zur Laufzeit aus `/etc/resolv.conf` ableiten (gewaehlt).** Der Container
  weiss selbst, wer sein DNS ist. Kein Nutzerwissen, keine Konfiguration, unter
  Docker kommt exakt `127.0.0.11` heraus — also keine Verhaltensaenderung fuer
  Docker-Nutzer. Env-Override bleibt als Notausgang.
- **C — `resolver` streichen und feste Upstream-Namen ohne Variable.** Waere
  der kleinste Diff, wuerde aber die 502-nach-Recreate-Falle
  wiedereinfuehren, die N-2s Konstruktion gerade verhindert. Verworfen.

B ohne Rueckfrage, weil A die gemeldete Wirkung (stummes 502) nicht beseitigt
und C eine bekannte Regression waere.

## Umsetzung

1. `.dockerignore`: `.worktrees` ergaenzen; `.gitignore`: `.worktrees/` ergaenzen.
2. Neu: `docker/10-who2be-nginx-resolver.sh` (ausfuehrbar, ein Skript fuer beide
   nginx-Container). Ermittelt in dieser Reihenfolge:
   `$WHO2BE_DNS_RESOLVER` → erster `nameserver` aus `/etc/resolv.conf` →
   `127.0.0.11`. Schreibt `/etc/nginx/resolver.conf`:
   `resolver <addr> valid=10s ipv6=off;`
   Nur der ERSTE Nameserver, nicht alle: nginx verteilt Anfragen ueber alle
   genannten Resolver, ein oeffentlicher DNS in der Liste wuerde
   Container-Namen sporadisch mit NXDOMAIN beantworten.
   Laeuft in der nginx-Entrypoint-Kette (`/docker-entrypoint.d`, Praefix `10-`
   also vor `40-who2be-runtime-config.sh`).
3. `apps/web/nginx.conf` + `supabase/gateway.conf`: `resolver …;` →
   `include /etc/nginx/resolver.conf;` (Kommentare nachziehen).
4. `apps/web/Dockerfile`: Skript nach `/docker-entrypoint.d/` kopieren + `chmod +x`.
5. `docker-compose.yml`, Service `auth-gateway`: Skript read-only nach
   `/docker-entrypoint.d/10-who2be-nginx-resolver.sh` mounten.
6. Doku: README/`docs/cloud-local-smoke.md` — Podman-Hinweis, dass
   `gateway.conf`-Aenderungen ein Recreate brauchen (reines `--build` reicht
   nicht), sowie `WHO2BE_DNS_RESOLVER` als Override.

## Verifikation (lokal, rootless Podman 6.1.1)

- `git ls-files`/`podman build` sieht `.worktrees` nicht mehr → Kontextgroesse.
- Isolierter Netz-Test: Podman-Netz + Upstream-Container namens `auth` +
  `auth-gateway` mit der echten `gateway.conf`; `nginx -t` gruen,
  `/etc/nginx/resolver.conf` traegt die Podman-Adresse (nicht `127.0.0.11`),
  Request durch den Gateway erreicht den Upstream (kein 502).
- Gegenprobe Docker-Semantik: mit `WHO2BE_DNS_RESOLVER=127.0.0.11` kommt
  buchstaeblich die alte Zeile heraus.

## Out of Scope

Produktverhalten, `deploy/hetzner/*`, `deploy/dokploy/*`, Kong-Ersatz (MS-2),
Aufraeumen der 7 GB `.worktrees` selbst.
