- Die grossen MCP-Lese-Werkzeuge koennen ihre Antwort auf `format="text"`
  zuschneiden und passen damit in das Antwort-Budget der Konsumenten-Laufzeit.

  Die Laufzeit von Claude Code/Claude.ai deckelt eine einzelne Tool-Antwort bei
  etwa 50.000 Zeichen — darueber wird sie nicht gekuerzt, sondern **weggelegt**:
  das Modell sieht sie nicht, der Server erfaehrt nichts davon. Vier Werkzeuge
  lagen darueber (gemessen gegen einen echten Workspace): `list_playbooks`
  277.151 Zeichen, `get_persona` 225.559, `fetch_playbook` 64.971, `fetch_agent`
  54.912. Betroffen waren damit genau die Aufrufe, mit denen ein Agent seine
  Arbeit **beginnt** — ein Boot-Schritt, dessen Antwort verschwindet, sieht fuer
  den Agenten aus wie ein leerer Workspace und nicht wie ein Fehler.

  Ursache ist in allen Faellen BlockNote-Editor-JSON, das die Werkzeuge
  unveraendert weitergeben: pro Absatz rund 250 Zeichen Struktur (`props`,
  `styles`, `children`) auf etwa 60 Zeichen Nutztext. Bei `get_persona` und
  `fetch_agent` ist es zusaetzlich eine Dublette, weil derselbe Inhalt als
  Plain-Text in `body_rendered` bzw. `system_prompt_rendered` schon in derselben
  Antwort steht.

  `get_persona`, `fetch_agent`, `list_playbooks` und `list_versions` nehmen
  jetzt `format`. Der Default `"full"` ist die unveraenderte Antwort — bestehende
  Konsumenten merken nichts. `"text"` leert nur den Body und laesst alles
  stehen, was die jeweilige Frage traegt: bei der Persona die Modi,
  `body_rendered` sowie Name, Beschreibung, Tags und Triggers jedes verknuepften
  Playbooks, beim Playbook-Katalog dieselben Auswahl-Felder, bei der
  Versions-Historie `version`, `status` und `created_at`. Bei `get_persona`
  umfasst der Zuschnitt auch die Bodies der verknuepften Playbooks, weil sie in
  derselben Antwort stehen und gemessen mehr beitragen als das Profil selbst.
  Bei `list_versions` wirkt der Zuschnitt typ-agnostisch, weil jede Entitaet
  ihren Body anders nennt (`body` / `blocks` / `usage_notes`). Ein unbekannter
  Wert wird abgewiesen statt still als `full` beantwortet.

  `apps/mcp/tests/test_tool_payload_budget.py` sichert das ab und fuehrt je Fall
  die Rot-Probe mit: erst der Beleg, dass der `full`-Pfad die Grenze mit
  demselben Fixture tatsaechlich reisst, dann die Zusage fuer `text`. Gemessen
  wird die serialisierte Antwort, nicht ein Feldname — faellt der Zuschnitt weg,
  werden beide Pfade gleich gross und der Test wird rot. Ein zusaetzlicher Guard
  meldet jeden kuenftigen `format`-Pfad, zu dem dieser Nachweis fehlt. Das
  Regelwerk samt Inventar steht in `docs/mcp-payload-budget.md`.
