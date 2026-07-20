// Pages-Barrel — nur lazy aus `app/routes.tsx` importiert. Statische
// Route-/Shell-Exporte (LegalLayout, CookieConsentBanner) liegen in
// `./layout.ts`, damit dieser Einstieg dynamisch bleibt.
export { DpaPage } from './pages/DpaPage'
export { ImpressumPage } from './pages/ImpressumPage'
export { PrivacyPage } from './pages/PrivacyPage'
export { TermsPage } from './pages/TermsPage'
