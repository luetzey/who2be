- Dates in the web app now follow the UI language instead of the browser
  locale. With an English (US) browser, a German UI used to show dates such as
  "10/9/2026, 7:11:53 AM" in the pattern sheet, the feedback detail and ten other
  places. All of them now go through one helper (`apps/web/src/lib/dates.ts`),
  and an ESLint rule rejects `toLocaleString()`, `toLocaleDateString()` and
  `toLocaleTimeString()` without a locale argument, so the mistake cannot come
  back unnoticed.
