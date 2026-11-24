- The web toolchain now resolves `glob` 14.0.3 and `minimatch` 11.0.3
  through `overrides` in `apps/web/package.json`, closing GHSA-3g3m-2fjr-6pw4
  and GHSA-g3hv-75wg-m249. Both OSV exceptions in `apps/web/osv-scanner.toml`
  are gone. `eslint-plugin-jsx-a11y` keeps `minimatch` 3.1.5 because it breaks
  on 11; that version lies outside the advisory's corrected range
  (7.0.0 up to 11.0.1). Both packages are dev-only tooling and not part of
  the shipped web bundle.
