- Dependabot now groups `valkey/valkey` and `supabase/postgres` compose updates
  into one pull request per image across all compose directories (groups
  `compose-valkey` and `compose-supabase-postgres`). Their usual updates — a
  new digest for the unchanged `8-alpine` tag, and a fourth-component bump such
  as `15.19.0.007` → `15.19.0.018` — are neither "minor" nor "patch", so they
  fell out of the `compose-images` group and arrived as one pull request per
  directory. Major Postgres bumps stay ignored.
