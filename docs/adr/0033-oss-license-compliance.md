# ADR-0033 — OSS-License-Compliance-Gate (Deny-Liste in CI)

- Status: Akzeptiert
- Datum: 2026-06-05
- Kontext: Coding-Standards-Remediation — Plan
  `.claude/plan/2026-06-05-1930_coding-standards-audit-remediation.md` (Welle 1,
  WP-1.1/1.2). Interner Standard *OSS-License-Compliance* (Coding-Standards).
- Bezug: `LICENSE.md` (FSL-1.1-Apache-2.0), ADR-0029 (Build-Isolation Billing),
  CI-`audit`-Job (Supply-Chain), Deployment-Standards (Distribution Cloud + On-Prem)

## Kontext

Der Audit gegen das Coding-Standards-Composite hat eine inhaltliche Luecke
gefunden: Der CI-`audit`-Job prueft ausschliesslich **Schwachstellen**
(`pip-audit`, `npm audit`), aber **keine Lizenzen**. Der Standard
*OSS-License-Compliance* verlangt eine Scan-Pflicht bei jeder Dependency-Wahl,
mit besonderem Fokus auf die **AGPL-Netzwerkfalle** und sonstiges Copyleft.

Das Produkt steht unter **FSL-1.1-Apache-2.0** (source-available, konvertiert
nach 2 Jahren zu Apache 2.0) und wird sowohl als Cloud-SaaS als auch
**On-Premise** verteilt (Deployment-Standards). Eine eingezogene (A)GPL-/Copyleft-
Dependency koennte beim Verteilen des On-Prem-Artefakts Offenlegungspflichten
ausloesen, die mit dem Lizenzmodell kollidieren. Ohne automatisiertes Gate
faellt so etwas erst spaet auf — Entfernen ist dann teuer.

Stand der Bestandsaufnahme (empirischer Scan): **keine** GPL/AGPL/LGPL-Deps in
Python oder Web. Vorhandenes Copyleft beschraenkt sich auf **MPL-2.0**
(file-level): Python `certifi`/`pathspec`, Web `@blocknote/*` (Editor, ADR-0022)
und `lightningcss` (Tailwind-v4-Engine). MPL-2.0 wirkt nur auf modifizierte
MPL-Dateien selbst — wir konsumieren diese Pakete unveraendert, daher unkritisch.

## Optionen

- **A — Allow-Liste (`--allow-only`).** Nur explizit erlaubte Lizenzen bestehen.
  Maximal streng, aber **hohe False-Positive-Rate**: uneinheitliche Lizenz-Strings
  (`MIT` vs. `MIT License`, Dual-Lizenzen wie `(MIT OR CC0-1.0)`, eigene
  Workspace-Pakete als `FSL-1.1`/`UNLICENSED`) brechen den Build dauernd; jede
  neue permissive Dependency erzwingt Pflege. Verworfen.
- **B — Deny-Liste (`--fail-on` / `--failOn`), gewaehlt.** Fail-closed nur gegen
  die im Standard benannten Risiken (Copyleft + AGPL + unbekannt). Geringe
  False-Positive-Rate, wartungsarm (neue permissive Deps brauchen keine Pflege),
  trifft genau die Sorge des Standards.
- **C — Nur SBOM erzeugen, kein Gate.** Dokumentiert, erzwingt aber nichts —
  verfehlt die Scan-/Gate-Pflicht. (SBOM bleibt als optionales Folge-WP-1.3.)

## Entscheidung

Ein **fail-closed Deny-Listen-Gate** je Oekosystem, in **bestehende** CI-Jobs
integriert (keine neuen Runner — Actions-Minuten schonen):

### Python — Step im `python`-Job (Deps dort bereits `uv sync`-installiert)

```
uv run --with pip-licenses python -m piplicenses --partial-match \
  --fail-on "GPL;AGPL;LGPL;SSPL;CDDL;EPL;EUPL;OSL;CPL;CPAL;NPL;Sleepycat;UNKNOWN"
```

`--partial-match` faengt Schreibvarianten der GPL-Familie; `UNKNOWN` faengt Deps
ohne erkennbare Lizenz. MPL ist bewusst **nicht** auf der Liste.

### Web — Step im `audit`-Job (Web-Deps dort via `npm ci`)

`npm run license:check` (Script + `license-checker-rseidelsohn` als devDependency,
reproduzierbar via Lockfile):

```
license-checker-rseidelsohn --production --excludePrivatePackages \
  --failOn "GPL;LGPL;AGPL;SSPL;CDDL;EPL;EUPL;OSL;CPAL;CPL;NPL;Sleepycat;UNKNOWN"
```

`--production` prueft nur den ausgelieferten Bundle-Anteil; `--excludePrivatePackages`
nimmt das eigene (private, `UNLICENSED`) `who2be-web` heraus.

### Policy

- **Erlaubt:** MIT, BSD-2/3-Clause, Apache-2.0, ISC, 0BSD, Unlicense, PSF-2.0,
  CC0-1.0 sowie **MPL-2.0** (file-level, konsumiert/unveraendert).
- **Verboten (fail-closed):** GPL, AGPL, LGPL, SSPL, CDDL, EPL, EUPL, OSL und
  unbekannte/fehlende Lizenzen.
- **Ausnahme:** eine bewusst akzeptierte Copyleft-Dependency braucht einen
  ADR-Nachtrag mit Begruendung + ggf. `--excludePackages`-Eintrag.

## Konsequenzen

- Neue Dependency mit Copyleft/AGPL/unbekannter Lizenz → CI-`python`- bzw.
  `audit`-Job bricht rot, bevor sie in `main` landet.
- Negativ-getestet: beide Gates failen nachweislich auf einer real vorhandenen
  Lizenz (Python `MIT`, Web `MPL-2.0`) — kein No-Op.
- Wartung: permissive Deps brauchen keine Pflege; nur neues Copyleft erzwingt
  eine bewusste Entscheidung. Lizenz-Strings-Drift trifft nur den eng gefassten
  Deny-Set, nicht jede neue Abhaengigkeit.
- Abgegrenzt von ADR-0029/Licensing-Standards (Entitlements): das hier regelt
  **Fremd**-Lizenzen der Dependencies, nicht die eigene Feature-Freischaltung.
- Offen (optional, WP-1.3): SBOM-Artefakt (`cyclonedx`) im CI als formale
  Bill-of-Materials — nicht Teil dieses ADR.
