- Brand buttons in light mode now meet WCAG AA contrast.

  The label on `variant="brand"` buttons switched from white to dark text in
  light mode, matching dark mode. White on the orange brand fill measured
  2.5:1 (3.1:1 on hover); dark text measures 7.6:1 (6.0:1 on hover). The brand
  color itself is unchanged. A unit test now recomputes the brand token
  contrast from `globals.css` in every theme.
