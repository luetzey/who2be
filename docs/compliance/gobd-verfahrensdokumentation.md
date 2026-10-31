# GoBD-Verfahrensdokumentation — Who2Be (Cloud-Edition)

> ⚠️ **Disclaimer:** Engineering-/Betriebs-Dokumentation, aus dem Code (Billing,
> Entitlement-Repository, Migrationen) rekonstruiert. **Keine Steuer- oder
> Rechtsberatung.** Ob, in welcher Form und durch wen umsatzsteuerliche Belege
> auszustellen und aufzubewahren sind, ist mit einem Steuerberater zu klaeren.
> Alle `<PLATZHALTER: …>` sind vom Betreiber zu fuellen. Stand der abgeleiteten
> Fakten: 2026-06-05, §1, §4 und §5: 2026-10-24.

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
| **Mollie B.V.** | Zahlungsdienstleister (PSP). Fuehrt Checkout, Abo-Lebenszyklus und Zahlungseinzug. Erzeugt ueber Mollie Invoicing (Sales Invoices API) die Rechnung samt Nummernkreis und PDF. |
| **Who2Be-API** (`packages/billing/`) | Empfaengt Mollie-Webhooks (Pull-after-Ping), leitet daraus den Entitlement-Stand ab und merkt je bezahlter Zahlung eine Rechnung vor (ADR-0061 §3). |
| **Worker-Routine `invoice-retry`** | Stellt vorgemerkte Rechnungen bei Mollie aus, holt das PDF und archiviert es (alle 5 min, ADR-0057). |
| **`billing_invoice`** (Tabelle, Migration `billing_0111`) | Eine Zeile je bezahlter Zahlung (`UNIQUE (payment_id)`): Status, Rechnungsnummer, Schalterwerte, Ablageort und SHA-256 des PDF. |
| **BlobStore, Praefix `invoices/`** | Rechnungsarchiv: das PDF unveraendert, wie Mollie es liefert. |
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

### 4.1 Rechnungsarchiv (ADR-0061 §7)

Mollie haelt Rechnungen nur 5 Jahre vor. Massgeblich ist deshalb das eigene
Archiv von Who2Be:

| Was | Wo | Unveraenderbarkeit |
|---|---|---|
| Rechnungs-PDF, Byte fuer Byte wie von Mollie geliefert | BlobStore (SeaweedFS/S3, ADR-0048), Schluessel `invoices/<org_id>/<jahr>/<rechnungsnummer>.pdf` | Ablageort und SHA-256 stehen in der Archivzeile und sind nach dem ersten Setzen fest |
| Archivzeile je Zahlung | `billing_invoice` (Migration `billing_0111`) | Trigger `billing_invoice_guard`: Status nur nach vorn, Rechnungsnummer, Mollie-ID, Ablageort und Hash nach dem Setzen fest, Steuerangaben, Betrag und Zeitraum ab `issued` fest. Die Laufzeitrolle hat kein `DELETE` |

- **Frist:** mindestens **10 Jahre ab Ende des Ausstellungsjahres** (das Jahr
  steht im Schluessel). Damit ist die laengere der beiden Fristen abgedeckt.
- **Pruefbarkeit:** Der SHA-256 in der Archivzeile belegt, dass das abgelegte
  PDF unveraendert ist. Pruefen durch erneutes Hashen des Objekts und Vergleich
  mit `billing_invoice.pdf_sha256`.
- **Loeschung:** nur durch die Owner-Rolle und erst nach Ablauf der Frist. Eine
  Routine dafuer kommt, wenn die erste Rechnung faellig wird; bis dahin steht
  die Frist im Loeschkonzept.
- **Abgrenzung zum Purge:** Archivzeile und PDF haengen nicht an der
  Organisation (`org_id` ohne Fremdschluessel) und liegen ausserhalb des
  Praefixes `blobs/<workspace_id>/`, den der Workspace-Purge raeumt. Sie
  ueberstehen Konto- und Org-Loeschung.
- **Sicherung:** Der Bucket ist Teil des naechtlichen Backups (`s3 sync` plus
  restic, `deploy/hetzner/scripts/backup.sh`). Das Offsite-Backup haelt nur
  6 Monate Historie: ein versehentlich im Bucket geloeschtes PDF ist danach
  nicht mehr wiederherstellbar. Eine zusaetzliche schreibgeschuetzte Ablage
  ausserhalb von Who2Be (Weiche W61-1, Option C) bleibt Betreiber-Aufgabe:
  `<PLATZHALTER: zweite Ablage (Buchhaltung / WORM-Speicher), ab wann>`.

---

## 5 · Rechnungsausstellung (ADR-0061)

Who2Be stellt je **bezahlter** Mollie-Zahlung genau eine Rechnung ueber Mollie
Invoicing aus. Nummernkreis, Pflichtangaben des Absenders und PDF-Layout
kommen aus dem Mollie-Profil des Betreibers.

### 5.1 Ablauf

1. **Vormerken (Webhook).** Meldet der Mollie-Webhook eine bezahlte Zahlung,
   legt Who2Be eine Zeile `pending` in `billing_invoice` an. `UNIQUE
   (payment_id)` verhindert eine zweite Rechnung zur selben Zahlung, auch bei
   doppeltem Webhook.
2. **Ausstellen (Worker `invoice-retry`).** Der Worker bestimmt den Steuerfall
   aus den Rechnungsdaten der Organisation und den Schaltern (Abschnitt 5.2),
   setzt atomar eine Sperre und legt die Rechnung bei Mollie als bezahlt an,
   mit Bezug auf die Zahlung. Status `issued`, Rechnungsnummer und Mollie-ID
   werden festgeschrieben.
3. **Archivieren.** Der Worker holt das PDF, legt es unveraendert ab
   (Abschnitt 4.1) und schreibt Ablageort und SHA-256. Status `archived`.

Bleibt eine Antwort von Mollie unklar (Timeout, Serverfehler), sucht der
naechste Lauf die Rechnung zuerst ueber die Liste bei Mollie, statt neu
anzulegen. So entsteht auch dann keine zweite Nummer.

**Zurueckgehalten** (Status bleibt `pending`, `last_error` beginnt mit
`hold:`) wird eine Rechnung, wenn der Steuermodus nicht gesetzt ist,
Rechnungsdaten oder Empfaenger-E-Mail fehlen oder der bezahlte Betrag nicht
zum Rechnungsbetrag passt. Der Worker prueft stuendlich erneut. Eine Rechnung
ueber einen anderen als den bezahlten Betrag entsteht nie.

**Ungepruefte USt-IdNr.** (Weiche W61-3 A): Der Worker fragt VIES erneut.
Liefert VIES 72 Stunden nach dem Vormerken noch kein Ergebnis, wird die
Rechnung wie bei ungueltiger Nummer ausgestellt und der Worker schreibt eine
Warnung ins Log.

**Technische Fehler** zaehlen einen Versuch; der naechste kommt mit
wachsendem Abstand (5 min bis 6 h). Nach 8 Fehlversuchen steht die Zeile auf
`failed`, und der Worker schreibt eine ERROR-Zeile. Dann prueft der Betreiber
im Mollie-Dashboard, ob zur Zahlung schon eine Rechnung existiert, und stellt
sie sonst von Hand aus. Keine Rechnung geht still verloren.

### 5.2 Schalter

Steuermodus und Preisbasis sind Betriebseinstellungen (ADR-0061 §5), gesetzt
im Deploy fuer die Dienste `api` und `worker`:

| Variable | Werte | Ohne Wert |
|---|---|---|
| `WHO2BE_INVOICE_TAX_MODE` | `regular` · `small_business` | Checkout antwortet 503, vorgemerkte Rechnungen bleiben zurueckgehalten |
| `WHO2BE_INVOICE_PRICE_BASIS` | `net` · `gross` | `net` |

Welche Werte gelten, legt der Betreiber fest:
`<PLATZHALTER: Steuermodus und Preisbasis, festgelegt am>`. Ein Wechsel wirkt
nur fuer neue Rechnungen; jede Archivzeile haelt fest, mit welchen Werten sie
entstand (`tax_mode`, `price_basis`, `vat_rate`, `memo_key`). Die Steuerlogik
steht als Tabelle in `packages/billing/src/who2be_billing/tax.py`.

### 5.3 Storno und Erstattung (ADR-0061 §8)

Die Sales Invoices API kennt weder Gutschrift noch Stornorechnung. Who2Be
aendert ausgestellte Rechnungen deshalb **nie automatisch** und erkennt
Erstattungen heute nicht von selbst. Erstattung und Rueckbuchung bearbeitet
der Betreiber von Hand: Erstattung in Mollie, Korrekturbeleg mit Bezug auf die
Originalnummer, Ablage neben dem Original (ADR-0061 §8). Ablauf:
[`../cloud-erstinbetriebnahme.md`](../cloud-erstinbetriebnahme.md#storno-und-erstattung).

### 5.4 E-Rechnung (EN 16931)

Die Rechnungen sind PDF, keine strukturierte E-Rechnung. Ob fuer die
ausgestellten Betraege eine Pflicht zur E-Rechnung (EN 16931 / XRechnung /
ZUGFeRD) besteht, ist vom Betreiber zu bestaetigen (ADR-0061 §13):
`<PLATZHALTER: Bewertung E-Rechnungspflicht>`. Mollie bietet den Versand
ueber Peppol an, falls Geschaeftskunden danach fragen.

---

## 6 · Offene Betreiber-Fragen (Steuer/Vertrieb)

Diese Punkte sind **nicht** durch Code entscheidbar und vom Betreiber mit
Steuerberater zu klaeren:

1. **Steuermodus und Preisbasis:** Werte der beiden Schalter (Abschnitt 5.2)
   und Texte der Rechnungsvermerke (`MEMO_TEXTS` in `tax.py`) bestaetigen.
   `<PLATZHALTER: Entscheidung>`.
2. **USt-IdNr / Reverse-Charge:** Die App erfasst die USt-IdNr. je
   Organisation und prueft sie bei VIES (ADR-0061 R1); Reverse Charge und
   Drittland sind Zeilen der Steuertabelle. Der Steuerfall je Kundengruppe ist
   zu bestaetigen. `<PLATZHALTER: Klaerung USt-IdNr/Reverse-Charge>`.
3. **Aufbewahrungsfristen & Archiv-Form:** Frist je Artefakt und zweite,
   schreibgeschuetzte Ablage neben dem Archiv aus Abschnitt 4.1.
   `<PLATZHALTER>`.
4. **Korrekturbelege:** Welcher Beleg bei Erstattung oder Rueckbuchung noetig
   ist (Abschnitt 5.3). `<PLATZHALTER>`.
5. **Datenzugriff der Finanzverwaltung (Z1/Z2/Z3):** Wie wird ein etwaiger
   Datenzugriffsanspruch bedient? `<PLATZHALTER>`.

---

## 7 · Aenderungshistorie dieses Dokuments

| Datum | Aenderung | Quelle |
|---|---|---|
| 2026-06-05 | Erstanlage (WP-H) — aus Billing-/Entitlement-Code abgeleitet | Plan §WP-H, ADR-0031 |
| 2026-10-21 | Hinweis in §5: Rechnungsstellung ueber Mollie Invoicing angekuendigt, Neufassung mit R2 | ADR-0061 |
| 2026-10-24 | §1, §4 und §5 neu gefasst (Rechnung je Zahlung, Archiv, Schalter, Storno), §6 nachgezogen | ADR-0061 §5, §7, §8; Pakete R2a–R2d |
