- The dashboard review banner now leads straight to the review.

  With up to three versions in review, the banner links each one directly to
  its review view (`?tab=versions&diff=<n>`), so the diff is one click away.
  With more, it links to the list of each affected type filtered to
  `status=review`. Long entity names are truncated inside the banner on narrow
  screens instead of overflowing it. The title uses proper plural forms in English and German
  ("1 version is awaiting review"). The banner description now uses
  `text-foreground/80` instead of `text-muted-foreground`, raising its contrast
  on the brand surface above WCAG AA (4.31:1 before in light mode).
