- Code references in issues, cards, plans and reviews now follow a binding
  convention: a stable anchor — commit SHA, symbol name, or both — instead of a
  bare `file.py:441`, whose line number drifts as the file grows and then
  silently names the wrong code. `scripts/check_code_refs.py` verifies those
  references mechanically (does the file exist, is the symbol defined there),
  reports in text or JSON, and changes nothing. Pre-existing bare pointers are
  reported as `legacy` and deliberately left alone; `--strict` promotes them to
  errors once the backlog is gone. Convention and usage:
  `docs/code-references.md`.
