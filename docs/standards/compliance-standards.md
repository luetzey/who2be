# Compliance & OSS-Lizenz-Hygiene

Zwei orthogonale Themen: (a) Rechts-/Compliance-Pflichten des Produkts,
(b) Lizenz-Hygiene der eingebundenen Dependencies.

> **Disclaimer:** Engineering-Leitplanken, **keine Rechtsberatung.** Bei
> kommerziell kritischen Fragen fachkundige Prüfung einholen.

## A. Compliance (DE/SaaS)

Vier Domänen: **Privacy-by-Design**, **Legal-Texts**, **Security-Infra**,
**Finance-Compliance**. Die Nachweis-/Pflichtdokumente liegen in
[`../compliance/`](../compliance/) (VVT, GoBD-Verfahrensdoku, Retention-/
Löschkonzept, Legal-Texts-Checkliste, C5-Mapping). Audit-Journale: ADR-0031.

## B. OSS-License-Compliance

Leitprinzip: **Jede Dependency bringt ihre Lizenz mit — die falsche kann das
eigene IP gefährden.** Konkretisierung + CI-Gate: ADR-0033, `CONTRIBUTING.md`
§DoD (`license:check` / `pip-licenses`).

- **Permissiv = unbedenklich für SaaS:** MIT, Apache 2.0, BSD, ISC, 0BSD, MPL-2.0.
- **Copyleft (GPL):** kann bei Modifikation + *Verbreitung* greifen; reines SaaS
  löst klassisches GPL-Copyleft meist nicht aus — Vorsicht bei On-Premise-/
  Distributions-Varianten.
- **AGPL-Falle:** speziell für SaaS — schon der **Netzwerkzugriff** kann die
  Pflicht auslösen, den *gesamten* modifizierten Quellcode offenzulegen. Bei SaaS
  kritisch prüfen oder meiden.
- **Lizenz-Kompatibilität:** keine inkompatiblen Lizenzen mischen (z. B.
  Apache 2.0 ≠ GPLv2-kompatibel).
- **Scan-Pflicht:** bei **jedem** Dependency-Add die Lizenz prüfen (automatisiert
  in CI). Das Gate ist fail-closed gegen GPL/AGPL/LGPL/SSPL/… (ADR-0033).

## Anti-Patterns

- AGPL-Dependency ins SaaS ziehen ohne Netzwerk-Copyleft-Prüfung; Lizenzen erst
  beim Launch prüfen; inkompatible Lizenzen mischen; Dependencies ohne erkennbare
  Lizenz einbinden; GPL/AGPL mit „ist ja Open Source" gleichsetzen.
