- Auto-Freigabe des Gedächtnisses in den Workspace-Einstellungen (Lernschleife
  C6, ADR-0053 4.1–4.3). Admins sehen unter Einstellungen → Workspace →
  Gedächtnis die Matrix Art × Herkunft. Schaltbar ist genau die Zelle, die der
  Server in `switchable_cells` nennt (heute Nutzerfakt × „Von dir gesagt“);
  alle anderen Zellen stehen als „Immer prüfen“ mit Begründung und ohne
  Bedienelement da. Einschalten geht nur über einen Dialog, der die acht
  Grenzen automatischer Freigabe aus ADR 4.3 vollständig zeigt und eine
  Lese-Bestätigung verlangt; die Liste steht zusätzlich dauerhaft im Abschnitt.
  Ist eine Zelle an und der Memory-Wächter aus, warnt ein Banner. Unter 768 px
  wird die Matrix zur Liste je Art, der Dialog zum Bottom-Sheet.
  Im Agent-Formular heißt der Modus `auto` jetzt „Automatisch nach
  Workspace-Regeln“; der Hilfetext erklärt, dass ohne eingeschaltete Zelle
  alles zur Freigabe landet.
