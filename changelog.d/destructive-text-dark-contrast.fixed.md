- Error and warning text is now readable in dark mode.

  `text-destructive` (form errors, destructive alerts, danger-zone headings)
  used the dark-mode fill color as a text color and measured 1.87:1 on cards.
  It now reads a dedicated `--destructive-text` token: 6.5:1 on cards in dark
  mode. Light mode and destructive buttons are unchanged. A unit test
  recomputes the contrast from `globals.css` in every theme (Audit A6).
