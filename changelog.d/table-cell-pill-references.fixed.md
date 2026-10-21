- Placeholder pills inside table cells now count as references. Playbook and
  resource pills placed in a table (also a table nested under another block)
  are picked up when a playbook is saved, so composition, resource links and
  "used by" include them, and an inactive sub-playbook referenced from a table
  blocks activation like any other reference. A table with text, or text in
  nested blocks, now satisfies the "body" requirement on activation. Resource
  link previews and section texts show tables as a GFM table instead of
  dropping them.
