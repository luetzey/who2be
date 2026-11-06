- Operator docs: `docs/cloud-erstinbetriebnahme.md` gains a "Domain umziehen"
  section, a step-by-step checklist for moving a running cloud instance to a
  new `DOMAIN`. It covers DNS and TTL, Dokploy values, provider redirect URIs,
  redeploy, Supabase auth, OAuth connectors, Mollie webhooks, acceptance checks
  and a rollback, and every step ends with a check. Existing connector tokens
  stay valid on the server, but every client has to reconnect with the new URL.
  The section explains why and gives a notice template for users.
