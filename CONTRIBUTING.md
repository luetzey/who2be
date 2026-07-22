# Contributing to Who2Be

Danke fuer dein Interesse an Who2Be! Dieses Dokument beschreibt den
Entwicklungs-Workflow und die Konventionen fuer Beitraege.

## Contributor License Agreement (CLA)

> **Platzhalter — wird mit dem Public-Switch aktiv.**

Mit dem Einreichen eines Beitrags stimmst du den Bedingungen des Contributor
License Agreements (CLA) zu, sobald dieses aktiv ist. Das CLA raeumt dem
Copyright-Holder (heute **Yannick Lützenburg**, mit Recht zur Uebertragung an
einen Rechtsnachfolger) die noetigen Rechte ein, deinen Beitrag unter der
Projektlizenz zu veroeffentlichen und kuenftig relizenzieren zu koennen.

Der CLA-Link (CLA-Assistant) wird hier ergaenzt, sobald das Repository
oeffentlich ist. Bis dahin sind externe Beitraege noch nicht freigeschaltet.

## Lizenz

Who2Be steht unter der
[Functional Source License 1.1 (Apache 2.0 Future)](LICENSE). Beitraege
werden unter derselben Lizenz aufgenommen.

## Branch-Konvention

- Feature-Branches: `feat/<kurz>`
- Bugfix-Branches: `fix/<kurz>`
- Cloud-/Web-Sessions (Claude Code) nutzen automatisch das `claude/`-Praefix.
- Branch immer von `main` abzweigen; nicht direkt auf `main` pushen.

### Sandbox / Experimente

Schnelle, unfertige Experimente laufen auf lokalen `sandbox/*`-Branches
**ohne Remote-Tracking** — sie werden nicht gepusht und durchlaufen keine CI.
Sobald etwas vorzeigbar ist, wandert es als sauberer `feat/`- bzw.
`fix/`-Branch in den normalen PR-Pfad (oder per Cherry-Pick der relevanten
Commits). So bleibt der oeffentliche Verlauf aufgeraeumt, ohne den
Solo-Dev-Komfort zu verlieren.

## Commit-Konvention

- [Conventional Commits](https://www.conventionalcommits.org/) (z. B.
  `feat: …`, `fix: …`, `docs: …`, `chore: …`).
- Aussagekraeftige Commit-Messages; ein PR pro abgeschlossener Einheit.
- Jeder PR braucht mindestens **ein** Review.

## Definition of Done

Vor jedem Push lokal gegenpruefen (beide Stacks gruen). Die Test-Schritte
laufen bewusst mit denselben Coverage-Gates wie die CI (Coverage-Ratchet):
**lokal gruen = CI gruen** — ein Testlauf ohne Coverage-Gate erfuellt die DoD
nicht.

**Python (uv-Workspace im Repo-Root):**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest --cov --cov-fail-under=85
# OSS-Lizenz-Gate (ADR-0033) — fail-closed gegen Copyleft/AGPL:
uv run --with pip-licenses python -m piplicenses --partial-match \
  --fail-on "GPL;AGPL;LGPL;SSPL;CDDL;EPL;EUPL;OSL;CPL;NPL;Sleepycat;UNKNOWN"
```

**Web (in `apps/web/`):**

```bash
npm run lint
npx tsc --noEmit
npm run test:coverage
npm run build
npm run license:check   # OSS-Lizenz-Gate (ADR-0033)
```

Neue Dependency? Vorher die Lizenz pruefen (Scan-Pflicht, ADR-0033). Erlaubt
sind permissive Lizenzen (MIT, BSD, Apache-2.0, ISC, 0BSD) sowie MPL-2.0;
GPL/AGPL/LGPL und sonstiges Copyleft brechen das Gate. Bewusste Ausnahmen
brauchen einen ADR-Nachtrag.

Bei Bugfixes zuerst einen reproduzierenden, fehlschlagenden Test schreiben,
dann fixen. Ursache statt Symptom beheben; groessere Aenderungen zuerst als
Plan skizzieren.

## Security

Sicherheitsrelevante Funde bitte nicht oeffentlich als Issue melden, sondern
ueber den in [`SECURITY.md`](SECURITY.md) beschriebenen Weg.
