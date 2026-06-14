# Compliance-Dokumente — Who2Be (DE/SaaS)

> ⚠️ **Disclaimer (gilt fuer alle Dokumente in diesem Verzeichnis):**
> Engineering-/Betriebs-Dokumentation, aus der Code-Realitaet rekonstruiert.
> **Keine Rechts- oder Steuerberatung.** Die Dokumente liefern Struktur,
> abgeleitete Fakten und klar markierte Betreiber-Platzhalter
> (`<PLATZHALTER: …>`) — **keine** verbindlichen Rechts-/Steueraussagen. Vor
> jedem Launch sind die konkreten Pflichten mit einer fachkundigen Stelle
> (Anwalt/Steuerberater/Wirtschaftspruefer) zu verifizieren. Stand der
> abgeleiteten Fakten: 2026-06-05.

Dieses Verzeichnis buendelt die Nachweis-/Pflichtdokumente, die das Audit gegen
die internen *Compliance-Standards (DE/SaaS)* als fehlend markiert hat
(Befunde P1, P5, F2 sowie der Standort-/Supply-Chain-Teil aus P4/S2/S5).

## Inhalt

| Dokument | Zweck | Audit-Befund |
|---|---|---|
| [`vvt.md`](./vvt.md) | Verzeichnis von Verarbeitungstaetigkeiten (Art. 30 DSGVO) | P1 |
| [`gobd-verfahrensdokumentation.md`](./gobd-verfahrensdokumentation.md) | GoBD-Verfahrensdokumentation (Beleg-/Buchungsfluss, Aufbewahrung) | F2 |
| [`data-retention-and-erasure.md`](./data-retention-and-erasure.md) | Retention- & Loeschkonzept (Grace, Purge, Backups, Ausnahmen) | P5 |
| [`legal-texts-checklist.md`](./legal-texts-checklist.md) | Betreiber-Checkliste: Inhalte fuer Impressum (§5 DDG) + Datenschutzerklaerung | L1/L2 |
| [`c5-mapping.md`](./c5-mapping.md) | Leichtgewichtiges BSI-C5-Mapping (Orientierung, kein Testat) | P4/S2/S5 |

## Verweise

- **Interner Standard** *Compliance-Standards (DE/SaaS)* — Quelle des Audits und
  der Disclaimer-Pflicht; vier Domaenen (Privacy-by-Design, Legal-Texts,
  Security-Infra, Finance-Compliance).
- **Ausfuehrungsplan:**
  [`.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md`](../../.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md)
  — Arbeitspakete WP-A … WP-I.
- **ADR-0031** (`docs/adr/0031-compliance-audit-journals.md`, wird von WP-A
  angelegt) — dokumentiert das Append-only-Privileg-Split (`status_history`,
  `audit_log`) und die GoBD-Aufbewahrung von `entitlement_history` trotz
  DSGVO-Erasure. Die hier beschriebenen `audit_log`-/`entitlement_history`-
  Mechanismen werden von den Schwester-Paketen **WP-A** (Schema), **WP-C**
  (Journal-Verdrahtung) und **WP-D** (Erasure-Anonymisierung) umgesetzt; dieses
  Verzeichnis beschreibt den Ziel-/Soll-Stand.
- **Infra-Belege:**
  [`deploy/hetzner/RUNBOOK.md`](../../deploy/hetzner/RUNBOOK.md) — At-Rest-
  Verschluesselung, Standort & Auftragsverarbeiter, Backup/Restore.

## Pflege

Diese Dokumente sind **lebende Dokumente**. Aenderungen an Schema (Migrationen),
Zahlungsfluss (`packages/billing`), Loeschpfad (`core/purge.py`,
`repositories/account_repository.py`) oder Deploy-Topologie (`deploy/hetzner/**`)
muessen hier nachgezogen werden. Bei jeder Aktualisierung das Stand-Datum oben
und in der jeweiligen Datei mitfuehren.
