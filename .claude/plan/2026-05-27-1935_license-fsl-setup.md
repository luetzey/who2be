# Lizenz-Setup: FSL 1.1 (Apache 2.0 Future) — Cloud-first + On-Prem-Pfad

**Status:** Plan, noch nicht umgesetzt
**Datum:** 2026-05-27
**Branch:** `claude/charming-ramanujan-I2qlB`

## Outcome

Who2Be hat ein dokumentiertes, rechtssicheres Lizenzmodell, das (a) Self-Hosting
fuer interne Nutzung erlaubt, (b) konkurrierendes SaaS-Hosting durch Dritte
unterbindet, (c) eine kommerzielle Enterprise-Lizenz als On-Prem-SKU
ermoeglicht, (d) spaetere Lizenz-Anpassungen offen haelt, und (e) den Pfad vom
Solo-Dev zur Firmen-IP-Owner vorbereitet.

## Entscheidungen (final)

- **Lizenz-Typ:** Functional Source License 1.1 (FSL-1.1-Apache-2.0).
  - Konversion: Nach 2 Jahren je Release automatisch Apache-2.0.
  - Standardtext der "Fair Source"-Initiative — kein Anwalts-Custom.
- **Use-Restriction-Schaerfe:** locker.
  - "Permitted Use" = jede Nutzung **ausser** dem Anbieten von Who2Be als
    konkurrierendes Hosted-/Managed-Service-Produkt an Dritte.
  - Internes Self-Hosting in beliebiger Groessenordnung erlaubt, kein
    Seat-Limit, kein Eval-Cutoff.
- **Copyright-Owner heute:** Privatperson (Solo-Dev).
- **Spaetere Anpassbarkeit gesichert durch:** CLA vor erstem externen PR,
  Major-Version-Cuts fuer Lizenz-Aenderungen, sauberer IP-Assignment-Pfad
  zur kuenftigen GmbH/UG.
- **Tier-Differenzierung On-Prem vs. Free Self-Host:** zunaechst rein
  Service-/Legal-Layer (SLA, Indemnification, Support, Audit-Recht). Kein
  Feature-Split heute — Enterprise-Module erst, wenn der erste qualifizierte
  Lead das erzwingt.

## Was geht — was nicht (Anpassbarkeit)

Erlaubt fuer den Owner (heute Privatperson, spaeter GmbH):

- Kuenftige Releases unter strengerer/anderer Lizenz veroeffentlichen.
- Use-Restriction in spaeteren Versionen lockern oder verschaerfen.
- Enterprise-Module spaeter aus dem Public-Build ausschliessen
  (Feature-Flag- oder Split-Repo-Muster).
- Dual-Lizenzierung (FSL + kommerzielle Lizenz) parallel anbieten.

Nicht erlaubt / unmoeglich:

- Rueckwirkend bereits veroeffentlichte Releases einsperren — wer eine
  Version unter FSL bezogen hat, behaelt seine FSL-Rechte fuer diese
  Version dauerhaft.
- Re-Lizenzierung ohne Zustimmung **aller** Copyright-Holder. Solange Solo:
  trivial. Sobald externe Contributor ohne CLA: blockiert.

## Schritte

### Phase A — Heute umsetzbar (vor Repo-Public-Switch)

1. **`LICENSE.md`** im Repo-Root anlegen mit Standard-FSL-1.1-Text:
   - Header: `Functional Source License, Version 1.1, Apache 2.0 Future License`
   - Copyright-Zeile: `Copyright (c) 2026 <Owner-Name>` — Owner-Name vom
     User bestaetigen lassen.
   - Quelle: <https://fsl.software> (Standardtext, unveraendert uebernehmen).
2. **`README.md`** — kurze "License & Usage"-Sektion am Ende:
   - Ein-Satz-Erklaerung: Free fuer interne Nutzung, kein konkurrierendes
     Hosting, nach 2 Jahren je Release automatisch Apache-2.0, kommerzielle
     Lizenz fuer Enterprise-Support auf Anfrage.
   - Link auf `LICENSE.md` und auf Kontakt fuer Commercial-Lizenz.
3. **`CONTRIBUTING.md`** im Repo-Root anlegen (Skelett):
   - Hinweis "Mit Beitrag stimmst du CLA-Bedingungen zu, sobald aktiv".
   - Platzhalter fuer CLA-Link (wird bei Public-Switch live).
   - Standard-Dev-Workflow (Branch-Konvention, Conventional Commits aus
     CLAUDE.md uebernehmen).
4. **`pyproject.toml`** — `authors`-Eintrag und `license = "FSL-1.1-Apache-2.0"`
   ergaenzen (im Root-Workspace und in den drei Member-Paketen
   `apps/api`, `apps/mcp`, `packages/models`).
5. **`apps/web/package.json`** — `"license": "FSL-1.1-Apache-2.0"` setzen.

### Phase B — Vor Repo-Public-Switch

6. **CLA-Assistant** (<https://cla-assistant.io>) auf dem GitHub-Repo
   konfigurieren. CLA-Text basierend auf Sentry-/Cal.com-Template,
   angepasst auf "Copyright-Holder = `<Owner-Name>` heute, mit Recht zur
   Uebertragung an Rechtsnachfolger (Gruendungs-GmbH)".
   - Aktivierung blockiert PR-Merges bis CLA-Signatur — sicherer Default.
7. **Trademark-Check** "Who2Be" bei DPMA + EUIPO recherchieren
   (Klasse 9 + 42 — Software + SaaS). Falls frei: Anmeldung vor
   Public-Launch erwaegen. **Out-of-Scope dieses Plans**, nur Hinweis.

### Phase C — Bei Unternehmensgruendung (deferred)

8. **IP-Assignment-Vertrag** Privatperson → GmbH/UG durch Gruendungs-Notar
   oder IT-Anwalt aufsetzen lassen. Uebertraegt: Code-Copyright,
   CLA-eingebrachte Rechte, Trademark, Domain-Rechte.
9. **Copyright-Zeile in `LICENSE.md`** auf die Firma umschreiben (kein
   neuer Lizenz-Cut noetig, nur Owner-Update).
10. **CLA-Receiving-Party** auf die Firma migrieren — neue CLA-Version,
    bestehende Contributor unterzeichnen erneut. CLA-Assistant supportet
    das nativ.

### Phase D — Bei erstem qualifizierten On-Prem-Lead (deferred)

11. Enterprise-SKU-Pricing finalisieren (Anker: 5k / 25k / 50k+ €/Jahr).
12. Master Service Agreement (MSA) + DPA-Template durch IT-Anwalt
    erstellen lassen.
13. Entscheidung "Feature-Flag-Split" vs. "Service-only-Differenzierung"
    abhaengig vom Lead-Profil.

## Acceptance Criteria

- [ ] `LICENSE.md` existiert im Repo-Root, enthaelt unveraenderten
      FSL-1.1-Apache-2.0-Standardtext mit korrekter Copyright-Zeile.
- [ ] `README.md` enthaelt License-Sektion mit Verweis auf `LICENSE.md`.
- [ ] `CONTRIBUTING.md` existiert mit CLA-Hinweis-Platzhalter.
- [ ] Alle `pyproject.toml` und `apps/web/package.json` haben
      `license = "FSL-1.1-Apache-2.0"`.
- [ ] `git status` clean, Commit mit Conventional-Commits-Message,
      Push auf `claude/charming-ramanujan-I2qlB`.
- [ ] Keine CI-Failures (ruff/mypy/pytest, Web lint/tsc/test/build).

## Offene Klaerung vor Umsetzung

- **Owner-Name fuer Copyright-Zeile** — voller Name (Privatperson) noetig,
  da `<Dein Name>` im LICENSE-File nicht steht.
- **Kontakt fuer Commercial-Lizenz** in README — E-Mail oder Landing-Page-URL?
  Vorschlag: `commercial@who2be.dev` (Platzhalter bis Domain steht) oder
  vorerst die im CLAUDE.md hinterlegte `luetzey@gmail.com`.

## Out of Scope

- Trademark-Anmeldung (eigener Prozess).
- Gruendung der GmbH/UG (Notar/Steuerberater).
- Konkretes Pricing-/SKU-Design publik (Cloud-Tiers + On-Prem) — separater Plan.
- Enterprise-Feature-Module (SSO, Audit-Log-Export, SCIM) — separater Plan,
  erst wenn Lead da.

## Notes / Aenderungen

2026-05-27 1935 — V1.0: Initial-Anlage nach Entscheidung W1=FSL, W2=locker,
Solo-Dev mit Gruendungsperspektive.
