- Betreiber der Instanz: Die neue Route `GET /v1/system/routines` zeigt die
  Hintergrund-Routinen des Workers (ADR-0057 §7, Paket P4c). Je Routine
  liefert sie den wirksamen Zeitplan, an/aus, ob ein `WHO2BE_ROUTINE_*`-Override
  greift, den letzten Lauf, den nächsten Termin und den letzten Erfolg, dazu
  „Worker zuletzt gesehen“. Sichtbar ist das nur für Betreiber aus
  `WHO2BE_OPERATORS` mit MFA-Session (aal2), in Cloud und On-Prem. Alle anderen
  bekommen 403, auch Org-Admins von Kunden-Organisationen und API-Tokens. Ein
  ungültiger Zeitplan-Override ergibt 503 mit dem Namen der Variable statt eines
  Serverfehlers. Der `api`-Dienst bekommt dafür in allen Compose-Stacks
  dieselben `WHO2BE_WORKER_ENABLED`- und `WHO2BE_ROUTINE_*`-Variablen wie der
  `worker`, damit die Übersicht die Zeitpläne zeigt, nach denen der Worker
  tatsächlich läuft. Ein Drift-Test schlägt fehl, wenn eine Routine an einem
  der beiden Dienste fehlt.
