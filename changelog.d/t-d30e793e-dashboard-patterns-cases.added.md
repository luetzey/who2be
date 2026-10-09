- **Muster und offene Fälle auf dem Dashboard** (Lernschleife D6h). Editors
  and admins see two new entries in the „Braucht jetzt deine Aufmerksamkeit“
  band: „{{count}} Muster“ (count of `GET /patterns`, action „Ansehen“ →
  `/feedback?tab=patterns`) and „{{count}} offene Fälle“ (`open` + `reopened`
  from `GET /cases/counts`, action „Einordnen“ → `/feedback?tab=cases`). The
  case list is never loaded just to count. Each entry appears only when its
  count is above zero; if one of the two requests fails, that entry is left
  out and the rest of the dashboard stays. „Alles erledigt“ only shows once
  both counts are known to be zero. Viewers make neither request and see
  neither entry.
