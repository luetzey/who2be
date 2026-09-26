- Kontoweite Routen verlangen jetzt einen menschlichen Aufrufer, und an einen Agenten gebundene API-Tokens erhalten hoechstens die Rolle `editor`.

  Die Endpunkte ausserhalb des Workspace-Prefix (`DELETE /v1/me`, die
  `/v1/organizations`-Routen, der DSGVO-Export, der Invitation-Accept) hingen an
  einer Dependency, die den Aufrufer auf die nackte Nutzer-ID reduziert: ein
  `w2b_`-Token war dort von einer angemeldeten Person nicht zu unterscheiden und
  konnte kontoweit handeln, obwohl seine Reichweite eigentlich an einem
  Workspace endet. Das Gate sitzt jetzt in der Dependency selbst — eine neue
  Route auf diesem Pfad ist damit per Vorgabe abgesichert und nicht per
  Nachtrag. Der Versuch beantwortet sich mit `403 account_route_requires_human`.

  `GET /v1/me` bleibt fuer Tokens erreichbar, weil der MCP-Server darueber Token
  und Workspace aufloest; die Antwort wird fuer den Token-Pfad aber auf den
  gebundenen Workspace geschnitten und nennt nicht mehr jede Organisation des
  Besitzers.

  Zugleich ist `admin` an einem Maschinen-Token nicht mehr moeglich: eine
  ausdruecklich angeforderte Admin-Rolle wird mit
  `403 agent_bound_role_capped` abgelehnt, eine von der Ersteller-Rolle
  geerbte still auf `editor` gedeckelt — auch auf dem OAuth-Connector-Pfad.
  Vorhandene Admin-Tokens zieht eine Migration nach und hinterlaesst dafuer je
  Token ein `token.role_capped`-Ereignis im Audit-Log.

  **Fuer Betreiber:** bricht eine Integration danach mit `403`, ist die Abhilfe
  nicht ein neues Admin-Token — es gibt keines mehr. Entweder gehoert die
  Aktion einer angemeldeten Person, oder die benoetigte Berechtigung gehoert
  als Capability in die Tool-Policy des Agenten.
