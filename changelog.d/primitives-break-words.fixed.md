- Lange Bezeichner ohne Trennstellen brechen in den geteilten Listen- und
  Detail-Primitives um, statt bei 320 px über den Kartenrand zu laufen.

  Betroffen sind der Beschreibungs-Absatz in `EntityCard` und die H1 in
  `DetailHeader` — beide bekommen `break-words` (`overflow-wrap: break-word`).
  Weil die Änderung am geteilten Primitive sitzt, wirkt sie in allen dreizehn
  Domänen gleichzeitig; nichts wird abgeschnitten, die Karte darf höher werden.
  Auslöser war ein MCP-Server-Name ohne Trennstelle im Beschreibungs-Slot der
  Tools-Domäne.
