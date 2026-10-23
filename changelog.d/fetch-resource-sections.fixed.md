- `fetch_resource` (MCP) with `block_ids` now returns whole sections, as
  `fetch_playbook` already did. A heading anchor from `list_resource_blocks`
  yields the heading plus everything down to the next heading of the same or a
  higher level; before, only the heading line came back. Non-heading anchors
  still return a single block, sections keep the requested order, overlapping
  sections return each block once, and unknown anchors still match nothing.
- Section boundaries are now the same everywhere: a section ends at the next
  heading of the same **or higher** level. Playbook block selection and the
  block-ref preview (`section_block_ids`) previously ran past a higher-level
  heading until the next heading of the same level; the web picker preview
  already stopped there. Only documents where a deeper heading is directly
  followed by a higher one return fewer blocks than before.
