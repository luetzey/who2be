- English agents now get English placeholder sentences. `persona-ref`,
  `playbooks-catalog`, `resources-catalog`, `memory` and the frame of
  `tools-overview` (heading, invocation, write-access and feedback notes,
  scope hints) render in the language of the agent's template. Before, an
  agent built from an English template received these fixed sentences in
  German. German output is byte-identical to before; a missing or unknown
  language falls back to German. The curated tool descriptions in
  `tools-overview` stay German for now.
