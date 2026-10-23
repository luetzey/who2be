- Die acht Builder-Playbooks sind entdoppelt (Builder schlank B3,
  `BUILDER_CONTENT_VERSION` 21 → 22, DE und EN). Der Feedback-Absatz am Ende
  entfällt, weil Server-Anweisungen, Persona und Template ihn schon enthalten.
  Der Abschnitt „Tools & Operations“ bzw. „Werkzeuge“ heißt jetzt „Fallen“ und
  nennt nur noch, was nicht offensichtlich ist: Replace-Semantik, 409 und
  Rechte-Grenzen. „Zweck“ steht in einem Satz. Die Agent-Bau-Konventionen
  werden nicht mehr ganz geladen. Jedes Playbook nennt die zwei bis vier
  Abschnitte, die es braucht, und lädt sie mit einem einzigen
  `fetch_resource(block_ids=[…])`-Aufruf. Ein typischer Bau lädt so auf Deutsch
  etwa 12–16 KB Prozedur-Text statt 27–33 KB, beim Agenten-Bau zusammen mit dem
  Persona-Playbook 31 statt 43 KB. Das Agent-Playbook lehrt jetzt, dass
  `tools-overview` standardmäßig nicht ins Template gehört. Das
  Playbook-Playbook schreibt „Zweck“ und „Tools & Operations“ nicht mehr als
  Gliederung vor. Bestands-Workspaces erhalten die Fassung über den
  Builder-Sync.
