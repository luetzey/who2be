# GoBD-Verfahrensdokumentation — Who2Be (Cloud-Edition)

> ⚠️ **Disclaimer:** Engineering-/Betriebs-Dokumentation, aus dem Code (Billing,
> Entitlement-Repository, Migrationen) rekonstruiert. **Keine Steuer- oder
> Rechtsberatung.** Ob, in welcher Form und durch wen umsatzsteuerliche Belege
> auszustellen und aufzubewahren sind, ist mit einem Steuerberater zu klaeren.
> Alle `<PLATZHALTER: …>` sind vom Betreiber zu fuellen. Stand der abgeleiteten
> Fakten: 2026-06-05.

Die **GoBD** (Grundsaetze zur ordnungsmaessigen Fuehrung und Aufbewahrung von
Buechern, Aufzeichnungen und Unterlagen in elektronischer Form) verlangen eine
Verfahrensdokumentation, die nachvollziehbar macht, **wie buchungsrelevante
Vorgaenge entstehen, verarbeitet, gesichert und aufbewahrt werden**. Dieses
Dokument beschreibt das fuer die **Cloud-Edition** (bezahlte Tarife via Mollie).

> **Geltungsbereich:** Nur die **Cloud-Edition** ist betroffen. Die **On-Prem-
> Edition** rechnet nicht ueber Who2Be ab (Entitlement aus signiertem
> Lizenzschluessel, keine Zahlungsvorgaenge) — fuer sie ist diese Dokumentation
> nicht einschlaegig.

---

## 1 · Buchungsrelevanter Vorgang & beteiligte Systeme

| System | Rolle im Beleg-/Zahlungsfluss |
|---|---|
| **Mollie B.V.** | Zahlungsdienstleister (PSP). Fuehrt Checkout, Abo-Lebenszyklus, Zahlungseinzug und die zahlungsbezogene Belegerstellung. |
| **Who2Be-API** (`packages/billing/`) | Empfaengt Mollie-Webhooks (Pull-after-Ping), leitet daraus den Entitlement-Stand ab. Stellt **keine** eigenen Rechnungen aus. |
| **`org_entitlement`** (Tabelle) | Aktueller Tarif-/Berechtigungsstand pro Organisation (UPSERT, „letzter Stand"). |
| **`entitlement_history`** (Tabelle, WP-A/C) | **Unveraenderbares, lueckenloses Journal** jeder Entitlement-Aenderung (append-only). |
| **`processed_webhook_event`** | Dedupe-Ledger fuer Mollie-Webhooks (Idempotenz). |

---

## 2 · Beleg-/Datenfluss (Entstehung)

1. **Checkout:** Der Nutzer startet ein kostenpflichtiges Abo. Who2Be erstellt
   bei Mollie einen Customer + die Erst-Zahlung und leitet auf die
   Mollie-gehostete Checkout-Seite um. **Zahlungsdaten (Karten-/Kontodaten) gehen
   ausschliesslich an Mollie**, nicht an Who2Be.
2. **Webhook (Pull-after-Ping):** Mollie sendet bei Zahlungs-/Abo-Ereignissen nur
   eine ID; Who2Be holt das vollstaendige Objekt aktiv ueber den `MOLLIE_API_KEY`
   nach (Trust-Boundary: `org_id` stammt aus den bei Mollie hinterlegten
   Metadaten). Jedes Ereignis wird in `processed_webhook_event` dedupliziert.
3. **Entitlement-Ableitung:** Aus dem Mollie-Objekt werden Status, Features,
   Limits (`mcp_monthly_quota`, `mcp_rate_per_min`), `expires_at` und ggf.
   `grace_until` (Dunning) bestimmt.
4. **Persistenz (atomar):** `org_entitlement` wird per UPSERT auf den neuen Stand
   gesetzt **und** im selben Transaktionspfad ein Eintrag in `entitlement_history`
   geschrieben (Felder + `source`, `external_ref`, `created_by`, `reason`,
   `recorded_at`). So bleibt der aktuelle Stand abfragbar und die Aenderung
   lueckenlos protokolliert.

**`source`-Werte** (Herkunft der Aenderung, CHECK-Constraint `migrations/0043`):
`mollie` · `cloud` · `manual_override` (befristet, auditiert: `created_by` +
`reason` Pflicht) · `signed_license` (nur On-Prem, nie in die Tabelle
geschrieben).

---

## 3 · Unveraenderbarkeit & Nachvollziehbarkeit (GoBD-Kernforderung)

- `entitlement_history` ist **append-only**: die Laufzeitrolle `who2be_app` hat
  nur `SELECT, INSERT` (kein UPDATE/DELETE; REVOKE in `migrations/0044/0045`,
  ADR-0031). Korrekturen entstehen als **neuer** Journaleintrag, nie durch
  Ueberschreiben — das erfuellt die GoBD-Forderung nach Unveraenderbarkeit und
  Protokollierung von Aenderungen.
- Reihenfolge/Zeitbezug ueber `recorded_at` (+ Index `(org_id, recorded_at DESC)`).
- `org_entitlement` ist der schnelle „Ist-Stand"; das **Journal** ist der
  revisionssichere Nachweis.

> Hinweis: `entitlement_history` und die Append-only-Grants werden durch die
> Schwester-Pakete **WP-A** (Schema) und **WP-C** (Verdrahtung im
> `entitlement_repository`) eingefuehrt (ADR-0031). Dieses Dokument beschreibt den
> Ziel-Stand.

---

## 4 · Aufbewahrung (§14b UStG / §147 AO)

- Buchungs-/zahlungsrelevante Daten unterliegen gesetzlichen
  Aufbewahrungsfristen (i. d. R. **bis zu 10 Jahre**, §147 AO; §14b UStG fuer
  Rechnungen). Die konkrete Frist und welche Artefakte darunterfallen, ist vom
  Steuerberater festzulegen: `<PLATZHALTER: konkrete Aufbewahrungsfristen je
  Artefakt>`.
- **Konflikt Aufbewahrung vs. DSGVO-Loeschung:** `entitlement_history` wird beim
  Konto-/Org-Hard-Purge **bewusst nicht geloescht** (`org_id` ohne
  `ON DELETE CASCADE`). Der Loeschanspruch (Art. 17 DSGVO) tritt insoweit hinter
  die gesetzliche Aufbewahrungspflicht zurueck (Art. 17 Abs. 3 lit. b/e DSGVO).
  Begruendung dokumentiert in ADR-0031 und
  [`data-retention-and-erasure.md`](./data-retention-and-erasure.md).
- **Beleg-Aufbewahrung Mollie-seitig:** Da Mollie die zahlungsbezogenen Belege
  fuehrt, ist zu klaeren, wie der Betreiber an diese Belege fuer die eigene
  Aufbewahrung kommt (Export/Archiv): `<PLATZHALTER: Mollie-Beleg-Export &
  Archivierungsverfahren>`.

---

## 5 · Rechnungsausstellung & E-Rechnung (EN 16931)

- **Who2Be stellt keine eigenen Rechnungen aus.** Die zahlungsbezogene
  Belegerstellung liegt bei Mollie bzw. beim Betreiber ausserhalb dieser
  Codebase.
- Daraus folgt: Die Pflicht zur **strukturierten E-Rechnung (EN 16931 /
  XRechnung / ZUGFeRD)** ist fuer die Who2Be-Codebase **nicht einschlaegig** —
  es gibt keine eigene Rechnungsfunktion, die ein E-Rechnungsformat erzeugen
  muesste.
- **Wird das geaendert** (z. B. eigene Rechnungsstellung / Enterprise-SKU mit
  eigenem Invoicing), ist EN 16931 neu zu bewerten und eine eigene
  Verfahrensdokumentation dafuer zu erstellen.

---

## 6 · Offene Betreiber-Fragen (Steuer/Vertrieb)

Diese Punkte sind **nicht** durch Code entscheidbar und vom Betreiber mit
Steuerberater zu klaeren:

1. **Vertriebsmodell / USt-Schuldner:** Wer stellt die umsatzsteuerlich
   massgebliche Rechnung an B2B-Kunden aus — Mollie-Receipt vs. ordnungsgemaesse
   Rechnung des Betreibers? `<PLATZHALTER: Entscheidung>`.
2. **USt-IdNr / Reverse-Charge:** Erfassung der USt-IdNr und Reverse-Charge-
   Behandlung sind heute **nicht** in der App abgebildet. Solange Mollie die
   Steuerbehandlung uebernimmt, kein Code-Bedarf; bei EU-B2B-Direktverkauf durch
   den Betreiber neu zu bewerten. `<PLATZHALTER: Klaerung USt-IdNr/Reverse-Charge>`.
3. **Aufbewahrungsfristen & Archiv-Form:** Welche Artefakte, wie lange, in
   welchem Format/Speicherort (GoBD-konformes Archiv)? `<PLATZHALTER>`.
4. **Datenzugriff der Finanzverwaltung (Z1/Z2/Z3):** Wie wird ein etwaiger
   Datenzugriffsanspruch bedient? `<PLATZHALTER>`.

---

## 7 · Aenderungshistorie dieses Dokuments

| Datum | Aenderung | Quelle |
|---|---|---|
| 2026-06-05 | Erstanlage (WP-H) — aus Billing-/Entitlement-Code abgeleitet | Plan §WP-H, ADR-0031 |
