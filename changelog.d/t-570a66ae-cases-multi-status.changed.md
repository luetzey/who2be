- `GET /v1/workspaces/{workspace_id}/cases` nimmt `status` jetzt auch mehrfach
  an, etwa `?status=open&status=reopened`. Die Liste enthält dann Fälle in
  einem der genannten Status, und die Keyset-Seiten über `X-Next-Cursor`
  folgen demselben Filter. So filtert die Fall-Liste den Chip „Offen“
  (`open` und `reopened`) auf dem Server statt im Browser, und Seite und
  Zähler bleiben stimmig. Ein einzelner `status` wirkt wie bisher.
