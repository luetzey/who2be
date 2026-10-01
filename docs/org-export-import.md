# Organisation exportieren und importieren (`who2be-org-transfer`)

Betreiber-Anleitung. Grundlage: ADR-0055 §4.6 und R6
(`docs/adr/0055-mandantentrennung-trennungskonzept.md`).

Mit `who2be-org-transfer` exportiert der Betreiber eine Organisation vollständig
und spielt sie in eine leere oder fremde Instanz ein. Der Export deckt drei Anlässe ab:

- die Rückgabe der Daten nach Art. 28 Abs. 3 lit. g DSGVO,
- das Zurückspielen einer einzelnen Org aus einem früheren Export,
- später den Umzug in eine andere Instanz.

Das Werkzeug läuft wie `who2be-purge` mit der Owner-Verbindung (`DATABASE_URL`,
RLS-Bypass) im API-Container. Es sieht dieselben Speicher wie die API:
Postgres, Tabellen-Store (`WHO2BE_TABLESTORE_DIR`) und BlobStore.

## Exportieren

```bash
who2be-org-transfer export \
  --org-id <org-uuid> \
  --recipient <gpg-schluessel-id-oder-mail> \
  --output /backups/org-<org-uuid>.tar.gpg
```

- Das Archiv wird mit `gpg --encrypt` für den Empfänger verschlüsselt. Ohne
  `--recipient` startet der Export nicht. Einen Klartext-Ausgang gibt es nicht.
  Der öffentliche Schlüssel muss im Schlüsselbund des Containers liegen
  (`gpg --import`). Das Runtime-Image bringt `gnupg` mit.
- `--output -` schreibt nach stdout, etwa für `| ssh … 'cat > …'`. Eine bestehende
  Datei wird nicht überschrieben. Die neue Datei bekommt die Rechte `0600`.
- Scheitert gpg, zum Beispiel weil der Schlüssel unbekannt ist, bricht der
  Export ab und hinterlässt keine Datei.
- Fehlt ein Blob, auf den eine `wa_blob`-Zeile zeigt, im BlobStore, läuft der
  Export weiter. Der Blob steht dann unter `missing_blobs` im Manifest, und die
  Zusammenfassung auf stderr nennt die Anzahl. Ein solcher Fehlbestand bestand
  schon vor dem Export und ist kein Fehler des Werkzeugs.

## Importieren

```bash
gpg --decrypt /backups/org-<org-uuid>.tar.gpg | who2be-org-transfer import
# oder
who2be-org-transfer import --input /pfad/zum/entschluesselten/archiv.tar
```

Der Import prüft zuerst das ganze Archiv und schreibt erst danach. Er bricht
mit Code 1 und einer Meldung ab, wenn eine dieser Prüfungen fehlschlägt:

| Prüfung | Abbruch, wenn … |
|---|---|
| Format | das Archiv nicht lesbar ist, zum Beispiel noch verschlüsselt (Hinweis auf `gpg --decrypt`), oder `format_version` unbekannt ist |
| Prüfsummen | eine Tabelle, SQLite-Datei oder ein Blob nicht zu seiner sha256 im Manifest passt |
| Migrationsstand | Quelle und Ziel nicht genau dieselben Migrationen angewandt haben |
| Zugangsdaten | das Archiv eine Zugangsdaten-Tabelle enthält |
| Vollständigkeit | eine Org-Tabelle des Ziel-Schemas im Archiv fehlt (der Export schreibt jede, auch leere) |
| Mandant | eine Zeile einer anderen Org oder einem Workspace außerhalb des Archivs gehört |
| Referenzen | ein Fremdschlüssel auf eine Zeile außerhalb des Archivs zeigt |
| Kollision | die Org, ein Workspace oder eine andere ID im Ziel schon existiert |

Postgres wird in einer einzigen Transaktion geschrieben. SQLite-Dateien und Blobs
werden vor dem COMMIT geschrieben. Schlägt danach ein Schritt fehl, rollt die
Transaktion zurück und die geschriebenen Dateien und Objekte werden wieder
entfernt. Im Ziel bleibt nichts zurück.

IDs werden nicht umgeschrieben, weil Inhalte IDs inline tragen
(`{{resource:<id>}}`). Wer eine Org über sich selbst zurückspielen will, löscht
sie deshalb zuerst mit dem Org-Purge (`docs/compliance/data-retention-and-erasure.md`)
und importiert dann. Der Purge lässt die SQLite-Verzeichnisse der Workspaces
bewusst liegen (`<WHO2BE_TABLESTORE_DIR>/<workspace_id>/`). Entfernt der
Betreiber sie nicht vorher, bricht der Import mit „Tabellen-Store existiert im
Ziel bereits“ ab.

## Was im Archiv steht und was nicht

| Klasse | Tabellen | Export | Import |
|---|---|---|---|
| Inhalte und Steuerung | alle Tabellen mit `workspace_id`/`org_id`, dazu `organization`, `workspace` | ja | ja |
| Entitlements und Verbrauch | `org_entitlement`, `entitlement_history`, `mcp_usage` | ja | nein, weil `org_entitlement` nur die benannten Quellen schreiben (ADR-0028/0029) |
| Zugangsdaten | `api_token`, `oauth_authorization_code`, `oauth_refresh_token`, `workspace_invitation` | nein | nein |
| global | `schema_migrations`, `oauth_client`, `processed_webhook_event`, `account_deletion` | nein | nein |

Eine neue Tabelle, die weder `workspace_id` noch `org_id` trägt und keiner
Klasse zugeordnet ist, bricht den Export ab (fail-closed). Sie muss dann in
`apps/api/src/who2be_api/core/org_transfer.py` eingeordnet werden.

**Nach einem Import:** Agenten-Tokens, MCP-Connectoren (OAuth) und offene
Einladungen werden neu ausgestellt. Das CLI erinnert daran. Nutzer-IDs bleiben
unverändert. Im Ziel melden sich die Mitglieder mit demselben Konto an
(dieselbe Auth-Instanz oder dieselben `auth.users`-IDs). Ein Mapping auf Konten
einer fremden Instanz gibt es noch nicht.

## Archivformat (`format_version` 1)

Das Archiv ist ein tar mit folgenden Mitgliedern:

- `postgres/<tabelle>.jsonl`: je Datensatz eine `to_jsonb`-Zeile ohne
  generierte Spalten, byteweise sortiert. Dieselben Zeilen ergeben dieselben
  Bytes und damit dieselbe Prüfsumme.
- `tablestore/<workspace_id>/<area_id>.sqlite`: ein konsistenter Snapshot je
  WorkArea (ADR-0049).
- `blobs/<workspace_id>/<sha256>`: die Objekte des BlobStores (ADR-0048).
- `manifest.json` als letztes Mitglied: Org, Workspaces, angewandte Migrationen
  sowie Zeilenzahl, Spalten und sha256 je Datei.

## Grenzen

- Die Postgres-Zeilen einer Org werden im Speicher gehalten. Für sehr große Orgs
  fehlt noch Streaming.
- Ältere Archive lassen sich nur in eine Instanz mit demselben Migrationsstand
  importieren. Eine Archiv-Migration gibt es noch nicht.
- Eine Self-Service-Rückgabe für Org-Admins (API, UI) gibt es noch nicht. Die
  Rückgabe ist ein Betreiber-Schritt.
