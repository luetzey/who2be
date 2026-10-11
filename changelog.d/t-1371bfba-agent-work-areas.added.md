- API: `GET /v1/workspaces/{ws}/agents/{agent_id}/work-areas` liefert die
  Arbeitsbereiche eines Agenten für den Agent-Überblick: Bereich, Stufe des
  Agenten (lesen/schreiben), ob es sein eigener (privater) Bereich ist und wie
  viele Agenten Zugriff haben. Nur für Menschen; viewer sehen geteilte
  Bereiche, ab editor auch den privaten. Unbekannter Agent: 404.
