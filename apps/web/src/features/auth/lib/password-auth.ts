// Passwort-Login: in der Cloud-Edition ausgeblendet, im Self-Hosting aktiv.
//
// Owner-Entscheidung 2026-09-24: In der Cloud meldet man sich ausschliesslich
// ueber externe Provider an (Google, GitHub). Das ist **Sichtbarkeit und
// Erreichbarkeit**, kein Code-Rueckbau — `signInWithPassword` & Co. bleiben
// unveraendert im Bundle und im Self-Hosting der Normalweg. Jederzeit
// umkehrbar, indem das Edition-Flag umgestellt wird.
//
// Das Edition-Merkmal ist das bestehende (ADR-0029): Build-Arg
// `VITE_WHO2BE_EDITION` → `vite.config.ts` `define` → `__CLOUD_BUILD__`.
// Bewusst **kein zweiter Schalter** — dasselbe Flag, das heute schon die
// Billing-UI aus dem On-Prem-Bundle tree-shaked. Das Backend-Pendant ist
// `GOTRUE_EXTERNAL_EMAIL_ENABLED` (in den Deploy-`.env` der Cloud auf `false`,
// Compose-Default ueberall `true`); beide werden im Deploy gemeinsam gesetzt,
// analog zum Paar `VITE_WHO2BE_SIGNUP_DISABLED`/`GOTRUE_DISABLE_SIGNUP`.
//
// Warum eine Funktion und keine exportierte Konstante: `__CLOUD_BUILD__` ist
// ein Literal-Replacement — in Vitest laesst es sich nicht stubben. Ueber
// dieses Modul koennen die Tests beide Richtungen (Cloud / Self-Hosting)
// per `vi.mock` pruefen, ohne einen zweiten Build zu brauchen.

/** True im Self-Hosting (Passwort-Login sichtbar), false in der Cloud. */
export function isPasswordAuthEnabled(): boolean {
  return !__CLOUD_BUILD__
}
