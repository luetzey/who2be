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
[Functional Source License 1.1 (Apache 2.0 Future)](LICENSE.md). Beitraege
werden unter derselben Lizenz aufgenommen.

## Branch-Konvention

- Feature-Branches: `feat/<kurz>`
- Bugfix-Branches: `fix/<kurz>`
- Cloud-/Web-Sessions (Claude Code) nutzen automatisch das `claude/`-Praefix.
- Branch immer von `main` abzweigen; nicht direkt auf `main` pushen.

## Commit-Konvention

- [Conventional Commits](https://www.conventionalcommits.org/) (z. B.
  `feat: …`, `fix: …`, `docs: …`, `chore: …`).
- Aussagekraeftige Commit-Messages; ein PR pro abgeschlossener Einheit.
- Jeder PR braucht mindestens **ein** Review.

## Definition of Done

Vor jedem Push lokal gegenpruefen (beide Stacks gruen):

**Python (uv-Workspace im Repo-Root):**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -q
```

**Web (in `apps/web/`):**

```bash
npm run lint
npx tsc --noEmit
npm test
npm run build
```

Bei Bugfixes zuerst einen reproduzierenden, fehlschlagenden Test schreiben,
dann fixen. Ursache statt Symptom beheben; groessere Aenderungen zuerst als
Plan skizzieren.

## Security

Sicherheitsrelevante Funde bitte nicht oeffentlich als Issue melden, sondern
ueber den in [`SECURITY.md`](SECURITY.md) beschriebenen Weg.
