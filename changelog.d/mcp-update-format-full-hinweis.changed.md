- MCP write tools with replace semantics (`update_persona`, `update_playbook`,
  `update_resource`, `update_external_tool`, `update_system_prompt`) now state
  in their description that `content` replaces the stored state and that the
  template must be read in full (`format="full"`). The managed resource
  "Agent-Building Conventions" carries the same rule in German and English
  (ADR-0056). This prepares the switch of read tools to a readable default;
  no tool behaviour changes in this release.
