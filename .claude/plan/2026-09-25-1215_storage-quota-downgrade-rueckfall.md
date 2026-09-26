# Downgrade-Rueckfall fuer `storage_quota_bytes` (Karte `t_98e05120`)

Basis: `origin/main` @ `cee6478e`. Branch
`who2be/t_98e05120-w8-p2-gekuendigte-cloud-orgs-haben-unbeg`.

## Outcome (Completion-Condition, messbar)

Eine gekuendigte Cloud-Org faellt beim Speicher auf `FREE_STORAGE_QUOTA_BYTES`
(100 MiB) zurueck, statt unbegrenzt zu sein — belegt durch einen Kettentest,
der **vor** der Aenderung rot ist (kein `402`) und danach gruen (`402`,
`reason: storage_quota_exceeded`, `params.limit == FREE_STORAGE_QUOTA_BYTES`).

## Befund (verifiziert, nicht uebernommen)

- `grep "def effective_" licensing/entitlement.py` → nur `effective_token_quota`
  (Z. 158) und `effective_workspace_quota` (Z. 188). Kein Speicher-Pendant.
- `services/storage_quota_service.py:100` liest `entitlement.storage_quota_bytes`
  roh und steigt bei `None` aus (Z. 101-102), ohne die Summe abzufragen.
- `routers/entitlement.py:102` liest ebenfalls roh — die Zeilennummer aus dem
  Bericht stimmt noch. Die beiden Nachbarzeilen 101/103 benutzen die
  `effective_*`-Methoden; Zeile 102 ist die Auslassung.
- Weitere Lesestellen von `storage_quota_bytes` (erschoepfend, `grep` ueber
  `apps` + `packages` ohne Tests):
  - `core/license_cli.py:39` — On-Prem-CLI, zeigt bewusst das **rohe** Feld der
    signierten Lizenz. Kein Cloud-Pfad, bleibt unveraendert.
  - `licensing/license.py:59`, `repositories/entitlement_repository.py`,
    `billing/plans.py`, `billing/mollie.py`, `billing/router.py`,
    `billing/webhook.py` — Schreib-/Transport-Stellen, kein Gate.

## Namenswahl (Abweichung vom Kartenwortlaut, bewusst)

Die Karte schreibt `effective_storage_quota(...)`. Ich nenne die Methode
`effective_storage_quota_bytes(...)`, weil die beiden Zwillinge exakt
`effective_` + Feldname heissen (`token_quota` → `effective_token_quota`) und
das Feld hier `storage_quota_bytes` ist. `effective_storage_quota` waere das
**dritte** Muster (Name ohne Einheit, Feld mit) — genau das, was das
Akzeptanzkriterium „kein neues Muster" ausschliesst. Die Befund-Sonde des
Berichts erwartet denselben Namen (`test_storage_quota_downgrade_probe.py:178`).

## Schritte

1. `effective_storage_quota_bytes(*, cloud, now=None)` in `entitlement.py`
   direkt nach `effective_token_quota` einfuegen — wortgleiche Konstruktion,
   Konstanten `FREE_STORAGE_QUOTA_BYTES` / `PRO_STORAGE_QUOTA_BYTES`.
   Feldkommentar (Z. 115-118) auf den Rueckfall hinweisen wie bei
   `workspace_quota` (Z. 119-124).
2. `storage_quota_service.py:100` → `entitlement.effective_storage_quota_bytes(cloud=True)`
   (der Service ist hinter `is_cloud()` bereits gated — identisch zu
   `token_quota_service.py:121` und `workspace_quota_service.py:97`).
   Modul-Docstring Z. 7-8 nachziehen.
3. `routers/entitlement.py:102` → `effective_storage_quota_bytes(cloud=is_cloud(settings))`,
   Feldkommentar im `EntitlementInfo` wie bei den Nachbarn.
4. Aufgabe 3 (alle Quota-Felder) als Kartenkommentar, Feld → Rueckfall ja/nein
   → Belegstelle.
5. Neuer Kettentest `packages/billing/tests/test_storage_quota_downgrade_chain.py`
   nach dem Muster von `test_workspace_quota_downgrade_chain.py`, Verbrauch
   200 MiB wie in der Sonde; zweiter Test fuer das Bestands-Abo ohne Metadatum
   (muss Pro-Wert bekommen, nicht Free). Rot-Probe vor Schritt 1-3 belegen.
6. `docs/licensing/plans.md` Z. 176-189 nachziehen: `storage_quota_bytes` aus
   der „gilt als unbegrenzt"-Aufzaehlung heraus in den Rueckfall-Absatz.
7. `changelog.d/w8p2-storage-quota-downgrade.changed.md` — `changed`, nicht
   `fixed`, mit dem ausdruecklichen Hinweis auf die Verhaltensaenderung fuer
   Bestandskunden.
8. DoD nach `CONTRIBUTING.md` (Python-Stack; die Web-Seite ist unberuehrt),
   PR gegen `main`.

## Dateibudget

6 Dateien (3 Code, 1 Test, 1 Doku, 1 Changelog) — unter der Achtdateigrenze.

## Out of Scope

Artifact-Limit, neue Quota-Felder, Aenderung der Free-Limits,
`core/license_cli.py` (On-Prem-Rohanzeige).
