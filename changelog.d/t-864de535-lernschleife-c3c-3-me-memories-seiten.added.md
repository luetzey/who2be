- Gedächtnis: `GET /me/memories` ist durchsuch- und seitenweise abrufbar
  (ADR-0053 6.4.1, Paket C3c-3). Neu sind `q` (Teilstring in `fact`, ohne
  Groß-/Kleinschreibung), `cursor` und `limit` (1–50, Standard 20) — dieselben
  Grenzen wie bei `GET /memories`. Die Antwort hat dieselbe Form wie dort:
  `{items, next_cursor}`, neueste zuerst. Die Sicht bleibt allein das eigene
  Nutzergedächtnis: kein Agentengedächtnis, auch nicht für `editor`, und nie
  das Gedächtnis einer anderen Person, auch nicht für `admin`.
