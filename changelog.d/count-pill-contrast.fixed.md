- The count pill next to the page title on the Agents, Playbooks, System prompts
  and External tools lists is now readable in light mode.

  The number used `text-muted-foreground` on `bg-muted` (4.35:1 measured in the
  browser, below the WCAG AA minimum of 4.5:1). It now uses
  `text-foreground/70`: 7.40:1 light, 7.80:1 dark. The four copies are one
  shared `CountPill` component (Audit A12).
