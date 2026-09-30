- Keine Who2Be-Seite landet mehr in einem Suchindex: Caddy sendet auf allen
  vier Hosts (auch bei 401/403/404) `X-Robots-Tag: noindex, nofollow,
  noarchive`, die Web-App trägt zusätzlich `<meta name="robots"
  content="noindex, nofollow">` für Deployments ohne Caddy, und `/robots.txt`
  ist eine echte Textdatei statt des SPA-HTML. Sie sperrt bewusst nichts,
  damit Crawler das `noindex` überhaupt lesen können.
- API- und MCP-Antworten tragen `Cache-Control: no-store`, sofern die App
  keinen eigenen Wert setzt; öffentliche `/.well-known/*`-Metadaten bleiben
  cachebar. `deploy/hetzner/tests/test_headers_ci.sh` prüft beides gegen die
  echte Caddyfile und einen echten Web-nginx.
