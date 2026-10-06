- Transitive web dependency `source-map-js` updated from 1.2.1 to 1.2.2 to
  close GHSA-68fv-2mgg-jv7q; 1.2.2 is the fixed release. It is a lockfile-only
  change within the declared semver ranges of the packages that pull it in
  (Tailwind's Vite plugin, PostCSS, css-tree, magicast); `npm ls source-map-js`
  now resolves to a single 1.2.2 copy. Updating was chosen over a scanner
  exception because a fixed version exists. No overrides were added, and the
  existing time-boxed exception for GHSA-ch52-4w7c-c8xp stays unchanged: it
  still filters a live finding, even though osv-scanner 2.2.4 also lists it
  under "unused ignores".
