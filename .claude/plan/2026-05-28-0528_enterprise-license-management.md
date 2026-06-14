# Enterprise-Lizenz-Management: Vertrag, Key-Issuance, Operations

**Status:** Plan, noch nicht umgesetzt — deferred bis erster qualifizierter Lead
**Datum:** 2026-05-28
**Branch:** `claude/eager-planck-KCGSi`
**Voraussetzung:** Lizenz-Setup aus `2026-05-27-1935_license-fsl-setup.md` (FSL +
CLA) ist live. Dieser Plan baut darauf auf, nicht parallel.

## Outcome

Who2Be kann Enterprise-Kunden (On-Prem-SKU) rechtssicher, technisch nachvollziehbar
und operativ skalierbar bedienen — vom Lead bis Renewal. Heute kein Code,
sondern Architektur-Entscheidungen und Code-Hooks, damit spaetere Aktivierung
keine Refactor-Welle ausloest.

## Entscheidungen (final, soweit jetzt sinnvoll)

- **Vertragsstruktur:** 3-Schichten — MSA (boilerplate, einmalig) + Order Form
  (pro Deal) + DPA (GDPR-Pflicht). Optional pro Branche: BAA (US-Healthcare),
  TOMs-Anhang (DE-Behoerden).
- **License-Enforcement-Modell:** **Soft-License** — signiertes JWT, Warnung
  bei Ablauf, kein Hard-Stop. Begruendung: Hard-Stop ist Verkaufskiller bei
  Banken/Behoerden; Honor-System reicht nicht ab Kunde 4+.
- **Key-Signatur:** Ed25519 (kompakt, schnell, kein OpenSSL-Drama). Public-Key
  in Binary geshippt, Private-Key in Password-Manager (1Password Vault
  `who2be-licensing`).
- **Telemetry:** **Kein** Phone-Home. Compliance via Annual Self-Attestation
  + Audit-Klausel im MSA. Ist ein bewusstes Verkaufs-Asset.
- **Billing-Modell:** **Stripe Invoicing** (NET-30, Annual-Prepaid). Keine
  Card-Subscriptions — Enterprise will Rechnung.
- **Feature-Differenzierung:** Schon heute via `entitlement`-Layer im Code
  vorbereiten (siehe Phase A.3), auch wenn alle Features in FSL-Build aktiv
  bleiben. Vermeidet spaeteren Refactor.

## Architektur (Ziel-Bild)

```
Lead (Inbound)
  → CRM (Attio/HubSpot Free)
    → Order Form (PandaDoc-Template, Variablen-Felder)
      → Signatur (DocuSign/PandaDoc)
        → Stripe Invoice (NET-30)
          → License-Issuance-Tool (intern, FastAPI-Admin)
            → JWT generiert (Ed25519, customer_id, tier, expires_at, features[])
              → E-Mail an Kunde mit Key + Installations-Doc
                → Kunde fuegt Key in `.env` als `WHO2BE_LICENSE_KEY` ein
                  → App validiert beim Boot + zyklisch alle 24h
                    → 60 Tage vor Ablauf: Banner in UI + Log-Warning
                      → Renewal-Reminder (CRM-Task, 90 Tage vor Ablauf)
```

## Schritte

### Phase A — Heute umsetzbar (Code-Hooks, kein Vertrag)

1. **Entitlement-Layer in `apps/api/`** vorbereiten:
   - Modul `who2be_api/licensing/entitlement.py` mit Klasse `Entitlement`
     (`customer_id`, `tier`, `expires_at`, `features: set[str]`, `valid: bool`).
   - Default-Instanz `OSS_ENTITLEMENT` mit `tier="oss"`, alle bekannten
     Features als `True`, `expires_at=None`. Wird ueberall injiziert, wo
     spaeter Enterprise-Gates noetig sind.
   - **Kein** Enforcement-Code heute — nur die Schnittstelle.
2. **Feature-Gate-Pattern** in einer Beispielroute dokumentieren (als
   ADR-Comment, nicht als aktive Logik):
   ```python
   if entitlement.has("sso"):
       ...  # placeholder, OSS-Build laesst durch
   ```
   So lernt jede neue Enterprise-Feature-PR das Pattern, ohne Tech-Debt heute.
3. **License-Key-Format dokumentieren** in `docs/licensing/key-format.md`
   (neue Datei):
   - JWT-Claims-Schema (`iss=who2be`, `sub=customer_id`, `aud=who2be-onprem`,
     `iat`, `exp`, custom `tier`, `features`, `seats`).
   - Ed25519-Signatur, Key-Rotation-Strategie (jaehrlich, vorheriger Key
     bleibt 12 Monate gueltig fuer Verifikation).
   - Verifikations-Pseudocode.
4. **Public-Key-Slot** in `apps/api/` und `apps/mcp/`:
   - `who2be_api/licensing/keys/` — Verzeichnis, heute leer mit `.gitkeep`.
   - Spaeter: `current.pub`, `previous.pub` (Public-Keys, Ed25519, ~32B).

### Phase B — Erster qualifizierter Lead (Trigger: Lead mit > 10k €/Jahr-Indikation)

5. **MSA-Template** durch IT-Anwalt (DE) erstellen lassen — Startpunkt:
   - CommonPaper Cloud Service Agreement (OSS-Template, EU-tauglich)
     <https://commonpaper.com/standards/cloud-service-agreement/>
   - Anpassungen: FSL-Konformitaet erwaehnen, On-Prem-Klausel, Audit-Recht
     (1×/Jahr, 30 Tage Notice), Limitation of Liability auf 12 Monate
     Lizenzgebuehr cappen.
   - Kosten: ~2k € einmalig.
6. **Order-Form-Template** in PandaDoc oder DocuSign:
   - Variable Felder: Kundenname, Adresse, Steuernummer, SKU, Seats,
     Start-Datum, Term (12/24/36 Monate), Preis, NET-Terms.
   - Verweis auf MSA als Anhang.
7. **DPA-Template** (Auftragsverarbeitungsvertrag nach Art. 28 GDPR) —
   On-Prem ist juristisch grenzwertig (Kunde verarbeitet selbst), aber
   Procurement-Abteilungen verlangen das trotzdem. Template via Anwalt.
8. **License-Issuance-Service** bauen:
   - **Option 1 (DIY, empfohlen fuer Kunde 1–10):** Kleines internes CLI/
     FastAPI-Tool in `tools/license-issuer/` — generiert JWT, signiert mit
     Ed25519-Private-Key aus `op://Private/who2be-licensing/private-key`
     (1Password CLI), schreibt Audit-Log nach `licenses.jsonl`.
   - **Option 2 (Keygen.sh, ab Kunde 10+):** SaaS, ~$79/Monat, machined
     Lizenz-Portal fuer Kunden inklusive. Migration von Option 1 ist
     trivial (gleiches JWT-Format).
   - Entscheidung deferred bis Kunde 5 — DIY skaliert problemlos so weit.
9. **Soft-License-Verification** im API-Boot:
   - `WHO2BE_LICENSE_KEY` env-var lesen, JWT verifizieren, `Entitlement`
     instanziieren. Bei Fehlen: `OSS_ENTITLEMENT` (heutige Default-Bahn).
   - Bei Ablauf: `entitlement.valid=False` setzen, Warn-Log + UI-Banner via
     `/v1/license/status`-Endpoint, **aber** Features bleiben aktiv.
10. **Annual Self-Attestation-Formular** als PDF-Template:
    - "Wir haben Who2Be im Berichtszeitraum auf X Nodes mit Y aktiven Seats
      betrieben." Unterschrift, Datum.
    - Im MSA als Verpflichtung verankert (Klausel "Reporting").

### Phase C — Skalierung (Trigger: Kunde 5+ oder erstes Renewal faellig)

11. **Renewal-Automation** in CRM:
    - Order-Form-Closure setzt CRM-Task auf `expires_at - 90d` ("Renewal
      anstossen") und `expires_at - 30d` ("Renewal eskalieren").
    - Renewal = neuer Order Form (kein neuer MSA), neuer JWT mit
      verlaengertem `exp`.
12. **License-Portal fuer Kunden** evaluieren (Keygen.sh oder Eigenbau in
    `apps/web/`): Self-Service Re-Issuance, Seat-Erweiterung, Invoice-Download.
    Reduziert Support-Last spuerbar ab Kunde 8+.
13. **SBOM-Generierung** in CI ergaenzen (`cyclonedx-py`, `cyclonedx-npm`) —
    Enterprise-Procurement fragt staendig danach. Out-of-Scope eigentlich
    Lizenz-Plan, aber tightly coupled.

### Phase D — Feature-Split (Trigger: erstes echtes Enterprise-only-Feature)

14. **Entscheidung Feature-Flag vs. Split-Repo:**
    - **Feature-Flag** (empfohlen): Enterprise-Code im FSL-Repo, durch
      `entitlement.has(...)` geschuetzt. Vorteil: ein Build, ein CI-Pfad.
      Nachteil: Code liegt offen, kann theoretisch ausgebaut werden — aber
      die FSL-"Competing Use"-Klausel deckt das vertraglich ab.
    - **Split-Repo** (private `who2be-enterprise` Repo, als Git-Submodule
      oder separates Python-Package geshippt): Vorteil: Code ist privat.
      Nachteil: zwei CI-Pfade, License-Mix in Builds.
    - Empfehlung bei Aktivierung: Feature-Flag fuer die ersten 3 Features,
      Split-Repo nur bei IP-kritischen Modulen (z. B. Embedded-LLM-Routing).
15. **SKU-Definition** finalisieren:
    - **Free Self-Host** (FSL): unbegrenzt, Community-Support
    - **Enterprise** (Order Form): SLA 99.9 %, Email-Support 8×5,
      Indemnification, Audit-Recht. Anker-Preis: 25k €/Jahr fuer 50 Seats,
      gestaffelt.
    - **Enterprise Plus** (auf Anfrage): SSO, SCIM, Audit-Log-Export,
      dedizierter Engineer-Slack-Channel. Anker-Preis: 75k €/Jahr+.

## Was geht — was nicht

Erlaubt unter FSL-Modell:
- Soft-License im FSL-Code shippen — Verifikation ist kein "Competing Use".
- Enterprise-Module via Feature-Flag im FSL-Build deaktiviert lassen, solange
  Code zugaenglich bleibt (FSL-konform).
- Split-Repo fuer Enterprise-Module — separate, **proprietaere** Lizenz fuer
  das Split-Repo ist legitim (kein FSL-Konflikt).

Nicht erlaubt / problematisch:
- Hard-Stop-Lizenz-Check, der Kunden in Produktion blockiert, wenn JWT
  abgelaufen ist — vertraglich heikel, schlechtes Selling.
- Phone-Home-Telemetry ohne explizite Opt-In-Klausel im MSA.
- Lizenz-Keys ohne Audit-Log generieren — Procurement-Audits verlangen
  Nachweis "wer hat wann welchen Key erhalten".

## Acceptance Criteria

**Phase A (heute umsetzbar):**
- [ ] `who2be_api/licensing/entitlement.py` existiert mit `Entitlement`-Klasse
      und `OSS_ENTITLEMENT`-Default.
- [ ] `docs/licensing/key-format.md` dokumentiert JWT-Claims + Ed25519-Signatur.
- [ ] `who2be_api/licensing/keys/.gitkeep` existiert.
- [ ] `who2be_mcp/licensing/` spiegelt API-Layer (importiert aus
      `who2be_models` falls geteilt — Entscheidung in Umsetzung).
- [ ] mypy strict + ruff gruen.

**Phase B–D:** keine Code-Akzeptanz-Kriterien heute, da Trigger-basiert.

## Offene Klaerung vor Phase B

- **Anwaltskanzlei** fuer MSA/DPA — Vorschlag: spezialisierte IT-Boutique
  (z. B. Spirit Legal, Osborne Clarke DE) statt Allgemein-Anwalt. ~2–3k €
  Budget einplanen.
- **CRM-Wahl** — Attio (modern, API-first, ~$29/Seat/Monat) vs. HubSpot Free
  (gratis bis 1k Kontakte, klobiger). Empfehlung Attio, sobald > 5 aktive Deals.
- **Stripe-Account-Form:** Privatperson zunaechst (Kleinunternehmerregelung
  prueft Steuerberater), Migration auf GmbH bei Gruendung.
- **Currency-Default:** EUR fuer DE/EU-Kunden, USD optional fuer US-Deals.
  Stripe-Multi-Currency ab Tag 1 aktivieren.

## Out of Scope

- Konkrete Pricing-Modelle (Per-Seat vs. Per-Node vs. Flat) — separater
  Pricing-Plan, sobald 2–3 Lead-Gespraeche stattfanden.
- Marketing-Landingpage fuer Enterprise-SKU — separater Plan.
- Partner-/Reseller-Programm — fruehestens nach 10 Direct-Kunden.
- Open-Core-Diskussion (welche Module werden je Enterprise-only) — in
  Phase D.14 verankert, nicht jetzt entscheiden.
- SOC2/ISO27001-Zertifizierung — Trigger ist Enterprise-Lead-Pull, nicht
  Push. Vorbereitung (Drata/Vanta) erst, wenn 2+ Leads das explizit fordern.

## Notes / Aenderungen

2026-05-28 0528 — V1.0: Initial-Anlage nach Diskussion zum FSL-Plan
(`2026-05-27-1935_license-fsl-setup.md`). Fokus: Code-Hooks heute (Phase A)
+ Bauplan deferred (Phase B–D).
