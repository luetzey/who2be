- Der lokale Stack laeuft unter rootless Podman: der Build-Kontext enthaelt
  keine Git-Worktrees mehr, und die nginx-Container leiten ihren DNS-Resolver
  zur Laufzeit selbst ab statt Dockers `127.0.0.11` festzuschreiben.

  `.worktrees/` stand nicht in `.dockerignore`, lag aber im Repo-Root und damit
  im Build-Kontext beider Dockerfiles (`context: .`). Gemessen waren es 7 GB;
  `podman compose up --build` lief in einen Timeout, bevor der Kontext-Upload
  fertig war. Ohne den Ordner bleiben 26 MB uebrig. Das trifft jede
  Container-Runtime — auch Docker-Nutzer bauen seither schneller.

  Der zweite Punkt war stumm und damit teurer: `apps/web/nginx.conf` und
  `supabase/gateway.conf` brauchen ein `resolver`-Directive, weil sie ihre
  Upstreams ueber eine Variable ansprechen (sonst cached nginx die IP beim
  Worker-Start und haengt nach einem Recreate am alten Wert fest). Die Adresse
  war Dockers eingebettetes DNS `127.0.0.11`. Unter rootless Podman ist sie
  eine andere und nicht vorhersagbar, weshalb dort **jeder Signup mit HTTP 502
  scheiterte** — im Browser ohne verwertbare Meldung, das Formular brach
  einfach ab. `docker/10-who2be-nginx-resolver.sh` schreibt die Adresse jetzt
  beim Container-Start nach `/etc/nginx/resolver.conf`, aus
  `/etc/resolv.conf` des Containers; beide Configs includieren die Datei.
  Unter Docker steht dort weiterhin buchstaeblich `127.0.0.11` — fuer
  Docker-Nutzer aendert sich nichts. `WHO2BE_DNS_RESOLVER` ueberschreibt den
  Wert, falls ein Netz beides braucht.

  Nur der erste `nameserver` wird uebernommen: nginx verteilt Anfragen ueber
  alle genannten Resolver, ein oeffentliches DNS in der Liste wuerde
  Container-Namen sporadisch mit NXDOMAIN beantworten.
