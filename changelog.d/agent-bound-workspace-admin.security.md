- Agent-gebundene API-Tokens können keine Workspace-Verwaltung mehr ausführen.

  Ein Token mit Rollen-Snapshot `admin`, aber eingeschränkter Pro-Agent-Policy kam
  bisher an allen sieben `require_role(ctx, admin)`-Stellen der workspace-scoped
  Router durch: `POST /invitations` stellte eine Admin-Einladung samt
  Klartext-Token aus, `PATCH /v1/workspaces/{ws}` änderte den Namen,
  Mitglieder-Rollen und Workspace-Delete waren ebenso erreichbar. Damit konnte
  ein eingeschränkter Agent seine eigene Policy umgehen — derselbe
  Eskalationsweg, den die Token-Verwaltung seit je verbaut. Die Routen antworten
  jetzt mit `403` und `reason: workspace_administration_forbidden`; Menschen und
  ungebundene API-Tokens sind unverändert durchlässig. Der bestehende
  Token-Verwaltungs-Pfad behält Status, Text und `reason:
  token_management_forbidden`.
