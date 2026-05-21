# ADR-0001 — Modularer Monolith statt Microservices

- Status: Akzeptiert
- Datum: 2026-05-21
- Kontext: Who2Be MVP (PROJ-19)

## Kontext

Who2Be besteht aus REST-API, MCP-Server und Web-UI. Es ist zu entscheiden, ob
diese als unabhaengig deploybare Services oder als ein Deployment-Verbund
gebaut werden. Randbedingungen: Solo-Entwickler, eine Hetzner-Instanz als
Ziel-Hosting, kein bekannter Skalierungsdruck.

## Optionen

- **A — Modularer Monolith:** Ein Backend (die API) als DB-Eigentuemer,
  intern in klare Module/Schichten geteilt. Wenig Betriebs-Overhead.
- **B — Microservices:** API, MCP und Auth als getrennte Services mit eigenem
  Lebenszyklus. Unabhaengig skalierbar, aber verteilte Komplexitaet
  (Netzwerk, Deployment, Beobachtbarkeit).
- **C — Serverless-Functions:** Endpunkte als einzelne Functions. Feingranular
  skalierbar, aber Cold-Starts, lokal schwer testbar, an Plattform gekoppelt.

## Entscheidung

Option A. Die Architektur-Standards geben fuer kleinere Projekte den modularen
Monolithen vor; Microservices erst bei echtem Skalierungsbedarf. Der bewusst
gesetzte Modul-/Schichtschnitt erlaubt eine spaetere Aufteilung ohne Rewrite.

## Konsequenzen

- Ein Deployment-Artefakt, ein DB-Eigentuemer — geringer Betriebs-Overhead.
- Skalierung zunaechst vertikal; horizontale Aufteilung bleibt durch die
  Modulgrenzen moeglich, wenn sie noetig wird.
- Microservices-Vorteile (unabhaengiges Deployment/Skalieren) entfallen
  vorerst — fuer den Solo-MVP ein akzeptierter Tausch.
