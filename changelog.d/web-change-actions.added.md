- Web: Das Änderung-Sheet im Review-Ergebnis hat jetzt seine Aktionen
  (ADR-0053 Phase E, Paket E5e, 6.6). Ab Rolle editor fragt „Hat es gewirkt?“
  die Einstufung ab: ein fieldset mit drei Antworten, nichts vorausgewählt.
  Unter den Antworten sagt ein Satz, was die Wahl mit den Rückmeldungen der
  Änderung macht. Gezählt wird nach dem Server-Status der Rückmeldungen. Ein
  Hinweis sagt, dass nur Menschen antworten. „Nein, hat nicht gewirkt“
  verlangt eine Notiz von mindestens 10 Zeichen, weil sie die Begründung der
  wieder geöffneten Rückmeldungen wird. Danach bleibt das Sheet offen und der
  Fokus springt auf das Zustandswort. Ein Link bereitet ein neues Review mit
  demselben Agenten und denselben Rückmeldungen vor.

  Die Frage erscheint genau dann, wenn `GET /measures/{id}/follow-up`
  `reviewable` meldet. Ziele ohne Versionen (Werkzeug-Freigaben, Gedächtnis)
  lassen sich damit ab dem Nachkontroll-Datum auch ohne aktivierte Version
  einstufen.

  „Entwurf verknüpfen…“ öffnet einen Dialog mit festem Baustein. Wählbar sind
  nur Versionen im Status Entwurf oder zur Freigabe. „Zurückziehen…“ liegt
  unter „Weitere Aktionen“ und verlangt eine Begründung. Unter `md` klebt die
  Aktionsleiste unten im Sheet. Viewer sehen keine Aktionen.

  Fehler werden so gezeigt:
  - Fehlt die Änderung, schließt das Sheet mit Toast.
  - Bei 409 lädt das Ergebnis neu.
  - Bei 403 wird die nötige Rolle genannt.
  - Sonst erscheint das Detail des Servers.

  Der Web-Client hat dafür `linkMeasureDraft`, `reviewMeasure` und
  `withdrawMeasure` bekommen.
