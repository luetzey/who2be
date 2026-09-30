- Die Versions-Endpunkte von Personas, Playbooks, Resources, System-Prompts und
  External Tools liefern jetzt die UUID der Version (`id`). Liste, Detail und die
  Antwort eines Status-Übergangs tragen das Feld. Über diese UUID erreicht man
  den Prüfbericht (`GET /versions/{entity_type}/{version_id}/test-report`), und
  Prüfläufe (`POST /test-runs`, `subject_version_id`) adressieren eine Version
  damit. Das Feld kommt nur hinzu, keine bestehende Antwort verliert eines.
