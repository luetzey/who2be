- Der interne Owner-Leitfaden zum Cloud-Hosting liegt nicht mehr im Repo; die
  oeffentliche Dokumentation verweist stattdessen auf ihre Nachfolger.

  Der Leitfaden war ein Analyse- und Beratungspapier mit dem Betreiber als
  Adressat, nicht mit dem Nutzer. Was daran allgemein nuetzlich war, steht
  ohnehin schon oeffentlich: `docs/cloud-erstinbetriebnahme.md` fuehrt durch die
  Vorbereitung, `deploy/hetzner/RUNBOOK.md` traegt Provisioning, Betrieb und
  Backup/Restore, und verbindlich fuer Tarife und Limits ist
  `docs/licensing/plans.md`. Der eine Owner-Schritt, der bisher nur im Leitfaden
  stand — den Auftragsverarbeitungsvertrag mit dem Hoster abschliessen — ist in
  die Erstinbetriebnahme-Liste uebernommen worden. `docs/README.md` verweist auf
  die drei Nachfolger statt auf die entfernte Datei.

  In derselben Runde sind mehrere Textstellen in Tarif-, Betriebs- und
  Aenderungsdokumentation umformuliert: sie beschreiben weiterhin denselben
  Zustand und dieselbe Entscheidung, aber ohne Aufwandskalkulationen, die dem
  Leser die Bewertung eines Umgehungswegs abnehmen. Inhaltlich unangetastet
  bleiben die Architecture Decision Records, die Security-Findings mit ihren
  Begruendungen und die Compliance-Dokumentation. In den beiden
  Findings-Dateien wurde je ein Satz nachgezogen, der noch davon ausging, dass
  das Repository nicht oeffentlich ist. Das Protokoll der Restore-Drills wird
  nicht mehr im Repository gefuehrt, sondern betreiberseitig zu den
  Abnahme-Unterlagen genommen; die Auflage, nach jedem Produktions-Cutover einen
  Drill zu fahren und zu protokollieren, bleibt im RUNBOOK bestehen.
