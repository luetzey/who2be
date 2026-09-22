# Backlog-Aufbereitung — Lauf 28 (2026-09-22)

Norm: Resource „Agent-ready Arbeitspaket" (vier Pflichtfelder + fuenftes ab
Nicht-Trivialitaet). Prozedur: Playbook „Issue-Refinement". Reihenfolge-Kriterien
und Pflege-Regeln: Issue #442.

## Ausgangslage (gemessen, nicht fortgeschrieben)

- `main` @ `87de64c`, **9 Commits seit Lauf 27** (`69bfeda`). Die beiden in Lauf 27
  offenen PRs sind gemergt: **#548** (#520) und **#549** (#517), dazu **#552**
  (Nachtrag #520) und **#553** (Node-22-Pin).
- **#517 schliesst jetzt 12/12**: `CLAUDE.md:152` = `npx tsc -b`, `:234` =
  `npm run lint`, `npx tsc -b`, `npm run test:coverage`, `npm run build`.
  Der Lauf-27-Fund (10/12) ist mit `e062c01` erledigt.
- **#520 ist in beide Richtungen belegt** (Regel 32, echtes Artefakt): `npm run lint`
  **66 problems (0 errors, 66 warnings)** auf frischem Baum, `npm run test:coverage`
  erzeugt **390 Dateien** unter `coverage/`, danach **wieder 66** — die
  Reihenfolgeabhaengigkeit aus Lauf 18–27 ist weg.
- Web-Gates gruen: `npx tsc -b` Exit 0 / **1658 Dateien**; `npm run test:coverage`
  Exit 0, **194/194 Dateien, 1151/1151 Tests**, 158 s, Branches 81,68 %.
  `npx tsc --noEmit --listFiles` weiterhin **0** — das Kommando ist nur aus der
  normativen Doku entfernt, nicht repariert (Eigenschaft des Solution-tsconfig).
- **Kein Docker-Daemon, sechzehnter Lauf in Folge** (`docker info` Exit 1,
  `/var/run/docker.sock` fehlt).
- Nur Doku/Konfig hat sich bewegt: kein `apps/web/src/**` und kein `apps/api/**`
  im Diff. **`datei:zeile`-Zeiger in Quellcode koennen nicht gedriftet sein**;
  geprueft werden die in `CLAUDE.md`, `CONTRIBUTING.md`, `eslint.config.js`,
  `package.json`, `docs/frontend/**`.
- Neu seit Lauf 27: **dreizehn W3-Pakete #561–#573** (Zuschnitt von #431 W3,
  2026-09-21) und **#576** (K6 von #535, 2026-09-22).

## Schritte

1. **Bestandsaufnahme** — 29 offene Issues, Zuordnung zu Familien (W3-Zuschnitt,
   Cloud-Haertung, Tracking, `human-only`, Queue).
2. **Norm-Pruefung je Issue** durch read-only Pruef-Agenten (kein git-Schreibbefehl,
   keine Gate-Laeufe — Regel 30/31/45): vier Pflichtfelder einzeln abhaken,
   `datei:zeile`-Zeiger nachschlagen, Verifikations-Kommandos gegen `ci.yml`
   pruefen, Label-Konsistenz (`agent-ready` vs. `size/M`, Regel 7).
3. **Triage** (Playbook Schritt 4): belegt → mit Beleg ins Issue; Urteil →
   Kommentar mit drei Optionen + Empfehlung, Label `needs-decision`.
4. **Queue #442 neu ordnen** — Kriterien 1–5, Wellen nach Datei-Disjunktheit und
   Stack-Trennung. Body **ersetzen**, vorher Laenge messen (Regel 11).
5. **Bericht** in drei Bloecken + Notification an den Owner.

## Abgrenzung

Kein Repo-Code, kein Branch fuer fremde Pakete, kein Issue geclaimt. Einzige
Repo-Aenderung ist diese Plandatei.
