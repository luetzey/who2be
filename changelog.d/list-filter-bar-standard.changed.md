- The shared list filter bar (`ListFilterBar`) is now the standard filter
  pattern for every list. It gains generic status chips with counts, generic
  facet selects with optional per-value counts and hints, a sort option, one
  "Active filters" row with a chip for every set facet (including tag and
  type) and "Reset filters" at its end, a "counts unavailable" note, and a
  `bare` mode for bars inside a card. Below `md`, two or more facets now open
  a bottom sheet ("Filters apply right away.") with "Reset filters" and
  "Show n results"/"Done" in a fixed footer instead of expanding inline; a
  single facet stays inline. The "Filters" button shows a count only when a
  facet is set, and status chips and active-filter chips get 40 px hit targets
  on mobile.
