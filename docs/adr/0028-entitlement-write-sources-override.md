# ADR-0028 — Entitlement-Schreibquellen + befristetes Manual-Override

- Status: Akzeptiert
- Datum: 2026-06-05
- Kontext: Who2Be — Strikte Trennung Kauf/Billing ↔ App-Editionen (Plan `.claude/plan/2026-06-05-1200_build-isolation-entitlement-sources.md`)

## Kontext

`org_entitlement` (Migration 0030, ADR-Linie Track D) ist die Single Source of
Truth der Nutzungsrechte pro Org. Die App **liest** sie über den
`EntitlementPort` (ADR-0029) und entscheidet nie anhand des rohen Zahlungsstatus.

Beim Verifizieren des Ist-Stands fielen zwei Lücken auf:

1. **Mehrere unkontrollierte Schreibwege.** Geschrieben wird heute vom Webhook
   (`source='cloud'`), vom Mollie-Adapter (`source='mollie'`) und vom Dev-/
   Betreiber-CLI `who2be-set-entitlement` (`source='manual'`,
   `core/set_entitlement.py:83`). Die Spalte `source` hat **keinen** CHECK
   (`migrations/0030_org_entitlement.sql:23`).
2. **Roher Tabellen-Write im On-Prem-Build.** `who2be-set-entitlement` ist als
   Console-Script in jedem Artefakt enthalten und schreibt ein **unbefristetes**
   Pro-Entitlement direkt in die Tabelle. Da das On-Prem-Artefakt zugleich den
   Cloud-Read-Adapter enthält, kann ein Operator `WHO2BE_EDITION=cloud` setzen
   und sich Pro **ohne Mollie und ohne signierte Lizenz** geben — das
   On-Prem-Lizenzmodell wird wirkungslos.

Leitprinzip (Auftrag): *Die App erzeugt nie ein Entitlement — sie liest es nur.*
Jedes Entitlement muss aus einer klar benannten, nachvollziehbaren Quelle
stammen.

## Optionen

- **A — Status quo (frei).** Beliebige `source`-Strings, beliebige Writer,
  CLI in jedem Build. Verworfen: erlaubt das beschriebene Selbst-Granting.
- **B — Geschlossene Source-Taxonomie + build-getrennte Writer + befristetes,
  auditiertes Override (gewählt).** `source` per CHECK auf einen festen Satz
  begrenzt; pro Edition ist genau definiert, wer schreiben darf; der Roh-Writer
  entfällt; ein bewusster Ausnahmepfad ist befristet + auditiert.
- **C — Alles über signierte Tokens (auch Cloud).** Maximal einheitlich, aber
  überzogen für den Cloud-Pull-Flow (Mollie schreibt ohnehin nur abgeleitete
  Werte in dieselbe Tabelle) und blockiert den schnellen Support-Override.

## Entscheidung

**Option B.**

### Schreibquellen-Taxonomie (`org_entitlement.source`, CHECK-erzwungen)

| `source` | Edition | Writer | Pflichtfelder |
|---|---|---|---|
| `mollie` | Cloud | Billing-Paket (Mollie-Pull) | `external_ref` |
| `cloud` | Cloud | Billing-Paket (generischer HMAC-Webhook) | `external_ref` |
| `manual_override` | Cloud | Cloud-Ops-Override (Billing-Paket) | `expires_at`, `created_by`, `reason` |
| `signed_license` | On-Prem | **kein Tabellen-Write** — Adapter resolved live aus K_pub-verifiziertem Token | — |

- **On-Prem:** Ein Entitlement entsteht **ausschließlich** über den
  K_pub-Verifikationspfad (`verify_license_token` → `entitlement_from_license`).
  Es gibt im On-Prem-Build **keinen** Tabellen-Writer. Der gekaufte Schlüssel
  wird über ein verifikations-gegateates Install-Werkzeug (`who2be-license
  install`) eingespielt, das nur signierte Keys annimmt und den Token (nicht ein
  abgeleitetes Recht) persistiert; der Adapter re-verifiziert bei jedem Read.
- **Cloud (Regelweg):** Entitlements entstehen **nur** durch den Billing-Dienst.
  Kein roher Admin-Set-CLI als Normalweg.

### Manual-Override (kontrollierter Cloud-Ausnahmepfad)

Für Support-/Kulanz-/Webhook-Hänger-Fälle existiert **ein** bewusst gebauter
Override — als nachvollziehbarer Entitlement-Typ, **nicht** als roher
Tabellen-Write:

- eigener Ursprung `source='manual_override'`, unterscheidbar von `mollie` /
  `signed_license`;
- **Pflicht-`expires_at`** (befristet, z. B. „Pro für 1 Monat") — DB-CHECK
  erzwingt `expires_at NOT NULL` für `manual_override`;
- Urheber (`created_by`) + `reason` werden gespeichert (Audit), per CHECK
  Pflicht;
- nur in der Cloud-Edition verfügbar (liegt im Billing-Paket, ADR-0029) → **nicht**
  im On-Prem-Build;
- läuft über `EntitlementRepository.upsert` in dieselbe Tabelle; die App liest es
  identisch. Ablauf greift ohne Sonderlogik über `is_active()`/`expires_at`.

### Generalität (Marketplace-Vorbereitung)

`manual_override` ist konzeptionell nur **eine weitere Quelle** neben Kauf und
signierter Lizenz. Ein späterer Marketplace-Kauf ist strukturell dasselbe: eine
eigene `source`, geschrieben von einem separaten Transaktions-Dienst, gelesen von
der App über denselben Port. Die Taxonomie ist offen erweiterbar (neue `source`
+ CHECK-Wert), ohne den Read-Pfad zu ändern.

## Konsequenzen

- Migration ergänzt `created_by`/`reason`, CHECK auf den `source`-Satz und den
  Override-Pflicht-CHECK; Bestand `source='manual'` wird migriert.
- `core/set_entitlement.py` (Roh-Writer) wird gelöscht und das Script entfernt;
  Ersatz für Cloud ist der befristete `manual_override`, für On-Prem das
  Lizenz-Install-Werkzeug.
- `EntitlementRepository.upsert` trägt optional `created_by`/`reason`; `fetch`
  bleibt unverändert; die App-Read-Seite ändert sich nicht.
- Audit/Compliance verbessern sich: jeder Nicht-Kauf-Grant ist befristet und
  einem Urheber + Grund zugeordnet.
- **Offene Auflage (Issue #462, Owner-Entscheidung 2026-09-06, Weg C):**
  `EntitlementRepository.upsert` schreibt bedingungslos (`ON CONFLICT ... DO
  UPDATE` ohne Reihenfolge-Pruefung) — ein verspaetet zugestelltes
  Anbieter-Ereignis kann einen bereits geschriebenen neueren Stand
  zuruecksetzen. Heute tragbar: kein Anbieter sendet auf den generischen
  Webhook-Pfad, `mollie` hat einen eigenen Dedupe-Schutz, und die
  Ablauffrist aus #452 begrenzt den Schaden (kein wiedereingespieltes
  Ereignis kann ein unbefristetes Entitlement erzeugen). Verworfen wurden
  eine sofortige `event_at`-Spalte + Migration (kauft eine Migration fuer
  ein heute nicht bestehendes Risiko) und eine Naeherung ueber `updated_at`
  mit Toleranz (tauscht das theoretische Problem gegen praktisch
  faelschlich abgewiesene, legitim verspaetete Ereignisse). **Sobald ein
  signierender Anbieter an den generischen Pfad angebunden wird, ist die
  `event_at`-Spalte + eine `WHERE`-Bedingung, die aeltere Ereignisse
  verwirft, der richtige Weg** — das ist dann keine offene Frage mehr,
  sondern umzusetzen. Ausfuehrlich an der UPSERT-Stelle in
  `entitlement_repository.py`.

## Nachtrag 2026-07-20 (Q2)

Implementiert ist der On-Prem-Pfad **ohne Token-Persistenz**: es gibt
`who2be-license verify` plus Env-Validierung von `WHO2BE_LICENSE_KEY`, ein
`license install` mit persistiertem Token existiert nicht. Der Adapter
re-verifiziert den Token bei jedem `resolve()` direkt aus der Env — der oben
beschriebene Install-/Persistenz-Schritt entfällt.

Zusätzlich ist der `manual_override`-Writer seit 2026-07-20 technisch gegated
(LIC-1, fail-closed): nur Betreiber auf der Allowlist
`WHO2BE_BILLING_OVERRIDE_OPERATORS` und mit aal2-Step-up dürfen ihn aufrufen.
