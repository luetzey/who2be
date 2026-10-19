/**
 * Test-Timeout fuer jeden Test, der axe laufen laesst — die eine Quelle fuer
 * `vite.config.ts` (Projekt `a11y`) und `src/test/a11y.ts` (alle uebrigen
 * Dateien, die den axe-Helfer importieren).
 *
 * Begruendung des Werts: axe ueber eine ganze Seite in jsdom ist CPU-gebunden.
 * Gemessen ruhig 1–3 s (2026-10-19, Load ~3: 67 axe-Tests ausserhalb von
 * `*.a11y.test.tsx`, Median 0,8 s, p95 1,8 s, Maximum 2,0 s), unter fremder
 * Last (Load-Avg ~10, parallele pytest/podman-Laeufe) bis ~7 s. In CI hat genau
 * das den 5-s-Default von Vitest gerissen (main-Lauf 38610320689,
 * ReviewDetailPage/ReviewPreparePage, Issue #975). 15 s = ~2x Puffer ueber dem
 * gemessenen Lastwert.
 *
 * Bewusst ohne Vitest-Import: `vite.config.ts` liest die Konstante ebenfalls.
 */
export const A11Y_TEST_TIMEOUT_MS = 15_000
