# BSI-C5-Mapping (Orientierung) — Who2Be

> ⚠️ **Disclaimer:** Leichtgewichtige **Orientierung**, **kein** C5-Testat und
> keine Zusicherung der Konformitaet. Ein C5-Testat erteilt ausschliesslich ein
> Wirtschaftspruefer. Dieses Dokument ordnet vorhandene technische Belege grob
> ausgewaehlten C5-Kriterien zu, um Luecken sichtbar zu machen — es behauptet
> **nicht** „bestanden". Stand: 2026-07-08.

Der BSI-**C5** (Cloud Computing Compliance Criteria Catalogue) ist der gaengige
Kriterienkatalog fuer Cloud-Sicherheit in DE. Die folgende Tabelle mappt einige
relevante Kontrollbereiche auf existierende Belege in diesem Repo. Spalte
„Status" ist eine **Selbsteinschaetzung**, kein Pruefurteil.

| C5-Bereich (Auswahl) | Kriterium (sinngemaess) | Beleg im Repo | Status |
|---|---|---|---|
| **OIS** (Org. der Informationssicherheit) | Richtlinien/Verantwortlichkeiten | `<PLATZHALTER: Security-Policy/Verantwortliche>` | offen |
| **IDM / IAM** (Identitaets-/Rechteverwaltung) | Authentifizierung, Rollen, least privilege | GoTrue-Auth; RBAC (`workspace_member`, `require_role`); Laufzeitrolle `who2be_app` (`NOSUPERUSER, NOBYPASSRLS`) | umgesetzt |
| **IDM** | Starke Authentifizierung fuer Admins | MFA/AAL2-Gate umgesetzt (WP-F): `require_aal2` in `apps/api/src/who2be_api/core/security.py`, von `require_role(minimum=admin)` zentral erzwungen; GoTrue-TOTP (`docs/mfa-admin.md`); Cloud fail-closed bei fehlendem `aal`-Claim, On-Prem-fail-open sichtbar (Warn-Event `aal_missing_onprem`) + optional hart via `WHO2BE_REQUIRE_MFA_ONPREM` | umgesetzt |
| **CRY** (Kryptographie) | Verschluesselung at-Rest & in-Transit | At-Rest: `RUNBOOK.md` §Verschluesselung at-Rest; in-Transit: TLS via `deploy/hetzner/Caddyfile`; Backups GPG+restic | teilweise (At-Rest betreiberseitig zu belegen) |
| **PS / PSS** (Mandantentrennung) | Trennung der Tenant-Daten | RLS-Policies (`migrations/0036`, `0037`), org-scoped `current_setting('app.current_org')` | umgesetzt |
| **OPS-18 / Protokollierung** | Audit-/Security-Logging, Unveraenderbarkeit | `status_history`, `audit_log` (append-only, WP-A/B), `entitlement_history` (WP-A/C); ADR-0031 | teilweise (WP-A/B/C) |
| **OPS** (Datensicherung) | Backup + Restore + Test | `backup.sh` (GPG+restic), Restore-Drill-Tabelle im RUNBOOK | umgesetzt |
| **OPS** (Schwachstellenmanagement) | Patch-/CVE-Prozess | CI-`audit`-Job (pip-audit/npm audit), `dependabot.yml`, `RUNBOOK.md` §CVE-Response | umgesetzt |
| **PI** (Portabilitaet) | Datenexport | GDPR-Export (`gdpr_export_service.py`, GoTrue-Profil = WP-E) | teilweise |
| **AM** (Asset-/Lieferantenmgmt) | Sub-Processor-Uebersicht | `RUNBOOK.md` §Standort & Auftragsverarbeiter, `vvt.md` §5 | umgesetzt (Doku) |
| **BCM** (Notfallmanagement) | Wiederanlauf/Recovery | Restore-Verfahren im RUNBOOK | teilweise |
| **DEV** (sichere Entwicklung) | CI-Gates, Reviews | `.github/workflows/ci.yml` (lint/type/test/build + audit), PR-Review | umgesetzt |

## Bekannte Luecken (→ Plan-WPs)

- ~~**MFA fuer Admin-Zugaenge** (IDM)~~: **geschlossen** (WP-F umgesetzt,
  `require_aal2` — siehe Tabelle; verifiziert im Standards-Review 2026-07-08).
- **At-Rest-Verschluesselung Live-DB nachweisen** (CRY): Verfahren dokumentiert,
  betreiberseitiger Nachweis ausstehend → **WP-G** (`RUNBOOK.md`).
- **Append-only-Audit/Journal verdrahtet** (OPS-18): Schema + Wiring → **WP-A/B/C**.
- **Vollstaendige Security-Policy/OIS-Dokumentation**: `<PLATZHALTER>`.

## Verweis

- C5-Tiefe (Orientierung vs. angestrebtes Testat) ist eine offene
  Betreiber-Entscheidung — siehe Plan §8.
