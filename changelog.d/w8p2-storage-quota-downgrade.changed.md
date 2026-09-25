- Eine gekuendigte oder zahlungssaeumige Cloud-Organisation faellt beim Speicher
  jetzt auf das Free-Limit (100 MiB) zurueck, statt unbegrenzt zu sein.

  **Verhaltensaenderung, auch fuer Bestandskunden** — keine reine
  Fehlerbehebung: Der Revoke-Pfad des Billing-Webhooks schreibt
  `storage_quota_bytes` nicht, und ein leeres Feld hiess bisher „unbegrenzt".
  Dadurch hatte ausgerechnet eine gekuendigte Org keine Speichergrenze. Das
  betrifft ebenso jede Entitlement-Zeile, die vor Migration 0084 geschrieben
  wurde, und jedes vor Einfuehrung des Feldes angelegte Abo: solche Orgs hatten
  faktisch unbegrenzten Speicher und sehen nun die Grenze ihres Tarifs. Ein
  aktives Paid-Abo ohne das Metadatum bekommt weiter den Pro-Wert (10 GiB), wird
  also nicht auf Free heruntergedeckelt. `Entitlement.effective_token_quota`
  (Token) und `effective_workspace_quota` (Workspaces) haben diesen Rueckfall
  seit ihrer Einfuehrung; `effective_storage_quota_bytes` zieht ihn nach.
  Bereits abgelegte Bytes bleiben vollstaendig les- und herunterladbar —
  abgewiesen wird ausschliesslich der naechste Ingest (`402`,
  `reason: storage_quota_exceeded`, Grenze in `params`). On-Prem und OSS bleiben
  unbegrenzt.
