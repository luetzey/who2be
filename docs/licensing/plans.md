# Plan-Tiers & Mollie-Metadaten-Konvention

**Single Source of Truth** für die Cloud-Plan-Tiers (Plan
`2026-06-02-1819_followups-rls-mollie-auth-fsl.md` §3.2, Entscheidung M1/M2).
Die Code-Konstanten in `packages/billing/src/who2be_billing/plans.py` (optionales
Cloud-Paket, ADR-0029) spiegeln exakt diese Tabelle; bei Abweichung gewinnt dieses
Dokument und der Code wird nachgezogen.

> **Leitprinzip (Licensing-Standards §3.6):** Das Nutzungsrecht entscheidet die
> App über das **Entitlement** — der Zahlungsanbieter (Mollie) meldet nur
> Ereignisse und steuert den Zugriff nicht. Die freigeschalteten Feature-Codes
> und Limits liegen deshalb in der **Mollie-Subscription-/Customer-Metadata**,
> nicht in einem hartkodierten Produkt→Feature-Mapping.

## Tiers (final, 2 Stufen)

Die einzigen Groessen, die der Code tatsaechlich durchsetzt, sind Preis
(Mollie), MCP-Requests/Monat, MCP-Requests/Minute (beide `Entitlement`,
App-seitiges Rate-Limiting), das Entity-Limit je Workspace
(`Entitlement.entity_limit()`), die Anzahl aktiver API-Tokens je Workspace
(`Entitlement.token_quota`), die Speichergrenze je Workspace
(`Entitlement.storage_quota_bytes`) und die Zahl der Workspaces je
Organisation (`Entitlement.workspace_quota`). Das ist deshalb die
verkaufsrelevante Tabelle:

| Tier | Preis          | MCP-Requests/Monat | MCP-Requests/Minute | Entity-Limit je Workspace | API-Tokens je Workspace | Speicher je Workspace | Workspaces je Org | Features (Metadaten, s. u.) |
|------|----------------|---------------------|----------------------|----------------------------|--------------------------|-----------------------|-------------------|------------------------------|
| Free | 0 € (kein Abo) | 1.000               | 30                   | 50                         | 3                        | 100 MB                | 1                 | `core` |
| Pro  | 29 €/Monat     | 100.000             | 240                  | unbegrenzt                 | 25                       | 10 GB                 | 5                 | `core`, `composite_playbooks`, `agents`, `audit_export` |

Quellen: Preis/MCP-Requests `packages/billing/src/who2be_billing/plans.py`
(`FREE_PLAN`/`PRO_PLAN`: `price_eur`, `mcp_monthly_quota`,
`mcp_rate_per_min`, `token_quota`, `storage_quota_bytes`,
`workspace_quota`); Entity-Limit, Token-, Speicher- und Workspace-Konstanten
`licensing/entitlement.py` (`FREE_ENTITY_QUOTA = 50`,
`Entitlement.entity_limit()`, `FREE_TOKEN_QUOTA = 3`, `PRO_TOKEN_QUOTA = 25`,
`FREE_STORAGE_QUOTA_BYTES = 100 MiB`, `PRO_STORAGE_QUOTA_BYTES = 10 GiB`,
`FREE_WORKSPACE_QUOTA = 1`, `PRO_WORKSPACE_QUOTA = 5`) — `plans.py` importiert
die Zahlen, statt sie zu wiederholen.

**Zur Token-Spalte:** gezaehlt werden nur **nutzbare** Tokens — widerrufene und
abgelaufene zaehlen nicht mit. Die Grenze greift ausschliesslich bei der
**Anlage**: bestehende Tokens bleiben ueber der Grenze nutzbar **und
rotierbar** (Secret-Rotation, RUNBOOK §Secret-Rotation), ein Downgrade sperrt
also keine laufenden Agenten aus. On-Prem/OSS ist unbegrenzt.

**Zur Speicher-Spalte — was gezaehlt wird und was nicht.** Die Grenze gilt
fuer die Summe aus abgelegten **Blob-Bytes** (`wa_blob.size_bytes`, also Datei-
und URL-Ingest der WorkArea) **und Artifact-Text**
(`wa_artifact.content_bytes` — die UTF-8-Groesse der gespeicherten
Block-Liste). Ein Limit fuer alles: Artifact-Text zaehlt wie eine Datei, es gibt
kein zweites Kontingent fuer Artifacts. Durchgesetzt wird die Grenze an allen
Routen, die Speicher entstehen lassen — den beiden Ingest-Routen und den fuenf
Artifact-Schreibpfaden (`POST /work-areas/{id}/artifacts`, `POST /artifacts`,
`POST /wa-artifacts/{id}/append`, `PATCH /wa-artifacts/{id}`,
`POST /wa-tables/{id}/save-result`), samtlich ueber
`services/storage_quota_service.py`.

Gezaehlt werden **Bytes, nicht Zeichen**: ein Zeichen belegt in UTF-8 1 bis 4
Bytes, wer Zeichen zaehlte, gaebe je nach Sprache des Kunden ein- bis viermal so
viel Platz. Bei `append` zaehlt der **Zuwachs** (die Spalte traegt die
Gesamtgroesse der Zeile, die Summe waechst um das Angehaengte); ein Loeschen
oder ein schrumpfender Patch gibt Platz wieder frei. **Nicht** mitgezaehlt wird
der SQLite-Tabellen-Store je WorkArea (Dateisystem statt Postgres, ADR-0049).

Die Grenze greift ausschliesslich bei NEUEN Schreibzugriffen: Bestand bleibt
les-, export- und loeschbar, auch oberhalb der Grenze — Loeschen ist der Weg
zurueck darunter. Abgewiesen wird mit `402` und `reason:
storage_quota_exceeded`, die Grenze steht in `params`.

**Zur Spalte „Workspaces je Org" — warum es sie gibt.** Die Speichergrenze
zaehlt je Workspace (`STORAGE_USED_SQL` filtert auf `workspace_id`), jeder
weitere Workspace derselben Org bekaeme also dasselbe Kontingent erneut. Ohne
Deckel auf die **Zahl** der Workspaces vervielfacht eine Org ihr Kontingent
damit durch blosses Anlegen. Der Deckel schliesst genau diese Luecke
(`services/workspace_quota_service.py`, durchgesetzt an
`POST /organizations/{id}/workspaces`): erst beide Grenzen zusammen ergeben
eine endliche Speicherzusage — Free 1 x 100 MiB, Pro 5 x 10 GiB = 50 GiB.

Free steht auf **1**, nicht auf 0: jede Org-Anlage erzeugt atomar einen
Default-Workspace, und der letzte Workspace einer Org ist unloeschbar
(`reason: last_workspace_undeletable`). 0 waere zu diesem Bestand
inkonsistent. Org-weites **Speicher**-Zaehlen bleibt bewusst ausserhalb dieser
Stufe — der Deckel begrenzt die Zahl, nicht die Zaehlweise.

**Bekannte Grenze 1 — der Tabellen-Store zaehlt NICHT mit.** Die
SQLite-Dateien je WorkArea
(`{WHO2BE_TABLESTORE_DIR}/{workspace_id}/{area_id}.sqlite`, ADR-0049) liegen
im Dateisystem statt in Postgres und sind ohne `stat()` je Datei nicht
bekannt. Das ist eine bewusste Grenze dieser Stufe, kein Versehen.

**Bekannte Grenze 2 — Vorab-Check-Toleranz.** Das Gate prueft **vor** dem
Ingest `summe >= limit`, ein einzelner Vorgang kann die Grenze also um bis zu
`WHO2BE_INGEST_MAX_BYTES` (Default 20 MiB) ueberschreiten; der naechste wird
abgewiesen.

**Bekannte Grenze 3 — der Workspace-Deckel verschiebt den Multiplikator, er
schliesst ihn nicht.** `POST /organizations` hat selbst keine Obergrenze, und
jede neue Org bringt atomar einen Default-Workspace mit. Wer mehr Speicher
will, als sein Tarif zusagt, kann also weitere **Organisationen** anlegen statt
weiterer Workspaces. **Das ist eine bewusste Owner-Entscheidung vom
2026-09-22, keine uebersehene Luecke** — bitte nicht als offener Befund wieder
aufmachen. Zwei Gruende tragen sie:

* **Der Umgehungspfad ist um Faktor 100 teurer.** Eine frisch angelegte Org hat
  kein Mollie-Abo und faellt auf `CLOUD_FREE_ENTITLEMENT`, also 100 MiB statt
  10 GiB je Workspace. Fuer die 50 GiB, die ein einzelnes Pro-Abo zusagt,
  braeuchte es rund **500 Orgs** — jede mit bestaetigter Mailadresse und,
  sobald das Captcha scharf geschaltet ist, je einem geloesten Captcha.
* **Ein Org-Deckel traefe zuerst den ehrlichen Nutzer.** Organisationen sind
  das Mandanten-Modell dieses Produkts; eine Agentur mit acht Kunden legt
  berechtigt acht Orgs an. Speicher- und Token-Quote treffen, wer viel
  *verbraucht*; ein Org-Deckel traefe, wer viel *strukturiert* — und zwar beim
  Onboarding, an der teuersten Stelle der Kundenbeziehung.

**Gueltigkeitsbereich dieser Entscheidung.** Sie traegt, solange eine Free-Org
nichts bekommt, was echtes Geld kostet. Kaemen LLM-Aufrufe, Mailversand in
Menge oder Rechenzeit ins Free-Kontingent, ist die Rechnung neu zu machen: der
Faktor 100 oben ist dann nicht mehr der richtige Massstab. Das ist kein offenes
TODO, sondern die Bedingung, unter der die Entscheidung gilt.

**Kein Datenverlust.** Wie beim Entity-Limit bleibt Bestehendes ueber der
Grenze les- und herunterladbar — abgewiesen werden ausschliesslich **neue**
Ingests (`402`, `reason: storage_quota_exceeded`, Grenze in `params`).
Dasselbe gilt fuer den Workspace-Deckel: liegt eine Org nach einem Downgrade
ueber ihrer Grenze, bleiben **alle** Workspaces vollstaendig nutzbar (lesen,
schreiben, loeschen); nur die **Anlage** antwortet mit `402`,
`reason: workspace_quota_exceeded` und der Grenze in `params`. Eine Loeschung
gibt den Platz sofort wieder frei.

**Zur Features-Spalte — praezise gelesen:** Die Feature-Codes sind Metadaten
des Entitlements, kein Kaufargument. `Entitlement.entity_limit()` liest nur,
**ob ueberhaupt** ein Paid-Feature-Code vorliegt (`self.features - {Feature.CORE}`)
— diese Anwesenheit hebt das Entity-Limit von `FREE_ENTITY_QUOTA` auf
unbegrenzt. Die **einzelnen** Codes (`composite_playbooks`, `agents`,
`audit_export`) werden dagegen nirgends im Repo gegatet (keine
`has_feature()`-Pruefung greift auf sie zu; fuer `audit_export` existiert
nicht einmal ein Endpunkt) und sind deshalb **kein Leistungsversprechen** —
nur `core` selbst und das daraus abgeleitete Entity-Limit sind wirksam. Sie
tauchen weiterhin in `whoami`- und `entitlement`-Responses auf und bleiben
Teil des Datenmodells (ADR-0028 baut den On-Prem-Lizenz-Flow darauf auf) —
nur als Verkaufsversprechen zaehlen sie nicht.

- **Free** ist der Default jeder frisch registrierten Cloud-Org (ohne Mollie-Abo).
  Entspricht 1:1 `CLOUD_FREE_ENTITLEMENT` in `licensing/entitlement.py`.
- **Pro** ist eine einzelne wiederkehrende Mollie-Subscription (monatlich). Eine
  Kündigung (oder ausbleibende Zahlung → `canceled`/`suspended`) fällt die Org
  automatisch auf **Free** zurück — nie auf einen voll gesperrten Zustand, damit
  `core` erhalten bleibt.
- Pro ist bewusst ein **Superset** von Free (enthält `core`), sonst würden
  core-gated Reads für zahlende Kund:innen fehlschlagen.

## Mollie-Metadaten-Konvention

Beim Checkout schreibt die App die folgenden Schlüssel in die **Metadata** des
Mollie-Customers **und** der Subscription/Zahlung. Der Pull-Adapter
(`licensing/adapters/mollie.py`) liest sie nach dem Webhook-Ping wieder aus und
leitet daraus das Org-Entitlement ab.

| Schlüssel           | Typ    | Bedeutung                                                        |
|---------------------|--------|------------------------------------------------------------------|
| `org_id`            | UUID   | Ziel-Organisation des Entitlements (Pflicht).                    |
| `license_policy`    | String | Whitespace-/komma-separierte Liste der Feature-Codes (Pflicht).  |
| `mcp_monthly_quota` | Int    | Monats-Kontingent agent-facing MCP-Reads.                        |
| `mcp_rate_per_min`  | Int    | Rate-Ceiling (req/min) — zwei Fenster, siehe unten.              |
| `token_quota`       | Int    | Max. Anzahl aktiver API-Tokens je Workspace.                     |
| `storage_quota_bytes` | Int  | Speichergrenze **je Workspace** in Bytes (Summe `wa_blob.size_bytes` + `wa_artifact.content_bytes`). |
| `workspace_quota`   | Int    | Max. Anzahl Workspaces je **Organisation** (einziger Key der Konvention, der nicht je Workspace gilt). |

**Zu `mcp_rate_per_min` — zwei Fenster, ein Wert:** Seit #537 deckelt derselbe
Wert **zwei** Sliding-Windows mit jeweils demselben Ceiling — eines pro **Token**
und eines pro **Organisation**; effektiv gilt das **Minimum** der beiden. Ein
Aufrufer mit einem einzigen Token merkt davon nichts; N Tokens derselben Org
ergeben aber nicht mehr N × die beworbene Rate. Die Tarif-Tabelle oben (Free 30,
Pro 240) bleibt dadurch unveraendert gueltig — sie ist jetzt auch als
Org-Gesamtrate wahr. Durchgesetzt in
`apps/api/src/who2be_api/services/mcp_limit_service.py`
(`McpLimitService.enforce()`, Schritt 1).

Beispiel-Metadata für **Pro**:

```json
{
  "org_id": "11111111-1111-1111-1111-111111111111",
  "license_policy": "agents audit_export composite_playbooks core",
  "mcp_monthly_quota": "100000",
  "mcp_rate_per_min": "240",
  "token_quota": "25",
  "storage_quota_bytes": "10737418240",
  "workspace_quota": "5"
}
```

`license_policy` akzeptiert sowohl Komma- als auch Whitespace-Trenner; unbekannte
Codes werden ignoriert (Forward-Compatibility). Fehlen `mcp_monthly_quota`/
`mcp_rate_per_min`/`storage_quota_bytes`, gilt das jeweilige Limit als
unbegrenzt (`None`).

Für `token_quota` **und `workspace_quota`** gilt das **nur außerhalb der Cloud**
(On-Prem/OSS). Fehlt der
Schlüssel in einer Cloud-Subscription — etwa weil sie vor Einführung des Feldes
angelegt wurde, oder weil es sich um ein Downgrade-Entitlement handelt, das der
Webhook ohne dieses Feld schreibt —, bedeutet das nicht „unbegrenzt", sondern
„nicht gesetzt": `Entitlement.effective_token_quota` bzw.
`effective_workspace_quota` fällt dann auf den
Tarifwert zurück (gekündigt/zahlungssäumig oder Free ⇒ Free-Wert, aktiver
Paid-Plan ⇒ Pro-Wert). Sonst hätte eine Kündigung die Grenze aufgehoben, statt
sie durchzusetzen.

Zusätzlich schreibt der Checkout einen **operativen** Schlüssel `plan_code`
(z. B. `"pro"`) in die Metadata. Er ist *nicht* Teil der entitlement-ableitenden
Konvention oben, sondern erlaubt dem Webhook, beim Anlegen der wiederkehrenden
Subscription Preis und Intervall des gebuchten Tiers wiederzufinden.

## Pull-Modell (Mollie-spezifisch, Entscheidung M2)

Mollie sendet **keine** signierten Webhook-Bodies, sondern nur einen Ping mit der
Zahlungs-`id` (form-encoded `id=`). Die Sicherheit entsteht durch das
**Pull-after-Ping**: die App holt das Objekt aktiv über die Mollie-API
(`MOLLIE_API_KEY`) — ein gefälschter Ping mit fremder/erfundener `id` liefert
entweder einen 404 oder ein Objekt ohne unsere `org_id`-Metadata und wird
verworfen. Optional härtet `MOLLIE_WEBHOOK_SECRET` den Endpunkt zusätzlich über
einen Pfad-/Query-Token (`?token=…`, konstant-zeitlich verglichen).

Ablauf:

1. **Checkout** (`POST /v1/workspaces/{ws}/billing/checkout`, admin): Mollie-Customer
   anlegen + erste Zahlung (`sequenceType=first`) mit Plan-Metadata erzeugen →
   Hosted-Checkout-URL zurückgeben.
2. **Erste Zahlung bezahlt** (Webhook-Ping): App fetcht die Zahlung; bei `paid` +
   gültigem Mandat + Plan-Metadata wird die eigentliche **Subscription** angelegt
   und das Org-Entitlement auf den gebuchten Tier gesetzt (`source="mollie"`,
   `external_ref=<subscription_id>`).
3. **Folgezahlungen / Statuswechsel** (Webhook-Ping): App fetcht die zugehörige
   Subscription → `active` ⇒ Tier bleibt; `canceled`/`suspended`/`completed` ⇒
   Org fällt auf **Free** zurück.

## Entitlement-Schreibquellen (ADR-0028)

`org_entitlement` ist die einzige **gelesene** SSoT; sie wird nur von klar
benannten Quellen **geschrieben** (per CHECK auf diese vier begrenzt), nie von der
ausgelieferten Read-App:

| `source` | Edition | Wer schreibt | Pflichtfelder |
|---|---|---|---|
| `mollie` | Cloud | Billing-Paket (Mollie-Pull) | `external_ref` |
| `cloud` | Cloud | Billing-Paket (generischer HMAC-Webhook) | `external_ref` |
| `manual_override` | Cloud | Admin-Endpoint `POST …/billing/override` | `expires_at`, `created_by`, `reason` |
| `signed_license` | On-Prem | **kein Tabellen-Write** — Adapter resolved live aus dem K_pub-verifizierten Token | — |

- **On-Prem:** Entitlement nur über den K_pub-Verifikationspfad
  (`WHO2BE_LICENSE_KEY`, env-validiert via `who2be-license verify`). Kein
  Tabellen-Writer im On-Prem-Build (das rohe `who2be-set-entitlement` wurde
  entfernt).
- **`manual_override`:** kontrollierter, **befristeter** + auditierter
  Ausnahmepfad (Support/Kulanz/Webhook-Hänger) — gleiche Tabelle, gleiches Lesen,
  Ablauf über `is_active()`/`expires_at`. Nur in der Cloud-Edition (Billing-Paket).
- **Build-Isolation:** Das Mollie-/Billing-Modul (`who2be-billing`) ist im
  On-Prem-Artefakt physisch nicht vorhanden (ADR-0029).

## Out of Scope (späterer Iterationsschritt)

Dunning/Retry-Strategie, Idempotency-Key-Dedupe der Webhooks und mehr als zwei
Tiers — siehe Plan §5.
