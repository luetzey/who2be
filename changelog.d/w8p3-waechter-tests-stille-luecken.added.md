- Zwei Waechter-Tests machen die Kette „neues Pro-Feature" laut, statt sie still
  durchlaufen zu lassen.

  Eine Messung mit sechs gezielten Auslassungen hat gezeigt, dass vier von ihnen
  durch die volle Suite, ruff und mypy gruen liefen — zwei davon schalten in der
  Cloud ein Abrechnungs-Gate ab. `test_entitlement_field_completeness.py` prueft,
  dass jedes `Entitlement`-Feld in allen vier SQL-Fragmenten von
  `PgEntitlementRepository` steht und jedes Quota-Feld ein `META_*`-Metadatum
  sowie eine Anzeige in `EntitlementInfo` hat; ein neues Feld, das nirgends
  klassifiziert ist, bricht den Test ebenfalls.
  `test_gate_inventory.py` friert das Gate-Inventar aller POST-Routen als Golden
  ein (`apps/api/tests/contract/gate_inventory.json`, Aktualisierung mit
  `REGEN=1 uv run pytest apps/api/tests/test_gate_inventory.py`): verschwindet
  ein Gate oder erscheint eine neue ungegatete Route, bricht der Diff — und jede
  ungegatete Zeile braucht eine Begruendung im Golden.
