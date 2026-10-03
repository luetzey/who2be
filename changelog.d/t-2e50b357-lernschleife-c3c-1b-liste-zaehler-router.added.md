- Gedaechtnis: REST-Endpunkte `GET /memories` und `GET /memories/counts`
  (ADR-0053 6.4.1, Paket C3c-1b). `GET /memories` ist die workspace-weite
  Liste ueber alle Agenten und Status. Filter: `status`, `kind`, `scope`,
  `agent_id`, `origin`, `source`, `health`, `held`, `q`, `created_after`.
  Sortiert wird mit `sort=newest|oldest`, geblaettert ueber einen opaken
  `cursor`, `limit` ist hoechstens 50. Die Antwort ist `{items, next_cursor}`.
  `status=pending` ist die Warteschlange und enthaelt keine Lernvorschlaege.

  `GET /memories/counts` nimmt dieselben Filter und liefert `{total, groups}`.
  `group_by` ist wiederholbar (`agent`, `kind`, `status`, `origin`, `source`,
  `health`), jede Gruppe zaehlt ohne ihren eigenen Filter.
  `group_by=subject_user_id` steht nur `admin` offen und liefert je Person nur
  eine Zahl. Ab `viewer` erscheint das eigene Nutzergedaechtnis, ab `editor`
  dazu das Agentengedaechtnis aller Agenten. Fremdes Nutzergedaechtnis
  erscheint nie, auch nicht fuer `admin`.
