- Der Docs-Schalter der Hetzner-Cloud wird an den Dienst durchgereicht, und ein
  Guard haelt fest, dass die Betreiber-Vorlage keine wirkungslosen Einstellungen
  mehr anbietet.

  Die Hetzner-Stacks nutzen kein `env_file`, sondern listen jede Variable
  einzeln unter `services.api.environment`. Eine nur in `deploy/hetzner/.env`
  gesetzte Variable erreicht den Container deshalb nicht — der Stack startet
  fehlerfrei und die Einstellung bleibt trotzdem wirkungslos. `.env.example`
  bot `WHO2BE_DOCS_PUBLIC` an, ohne dass der Wert ankam; die Zeile steht jetzt
  im Basis-Stack (Default `false`, unveraendert restriktiv).

  Ein daemonfreier Test schneidet ab sofort die Zusagen aus
  `deploy/hetzner/.env.example` gegen die von `Settings` gelesenen ENV-Namen und
  verlangt, dass jede Variable aus diesem Schnitt in der `api`-Umgebung steht.
  Damit ist die Klasse abgedeckt, nicht nur der Einzelfall: bisher fiel eine
  fehlende Zeile erst im Betrieb auf, und nur dem, der genau hinsah.
