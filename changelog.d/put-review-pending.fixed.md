- Ein PUT (`update_*`, `PUT .../markdown`) auf ein Element, dessen höchste
  Version in Review steht und das keinen offenen Draft hat, legt keine
  unsichtbare `inactive`-Version mehr an. Er antwortet wie der Auto-Save mit
  409 `review_conflict`, für alle fünf Arten (Persona, Playbook, Resource,
  External Tool, System-Prompt). Der Fehlertext nennt den nächsten Schritt:
  Review abwarten oder per `transition` zurück in `draft` holen. Die
  Werkzeugtexte von `update_*` und `edit_content` sagen jetzt, welcher Stand
  bearbeitet wird, und dass neue Überschriften ohne eigenen Anker `[#id]`
  geschrieben werden (sonst `anchor_unknown`).
