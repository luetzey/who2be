// Statischer Route-/Shell-Einstieg (design-language §12, Barrel-Ausnahme):
// LegalLayout + CookieConsentBanner werden in `app/routes.tsx` synchron
// gemountet. Bewusst getrennt vom Pages-Barrel `index.ts`, damit dessen
// dynamische Imports effektiv bleiben und die Legal-Pages nicht im
// Hauptchunk landen (FE-10).
export { CookieConsentBanner } from './components/CookieConsentBanner'
export { LegalLayout } from './components/LegalLayout'
// Fuer Features, die auf den Cookie-Hinweis warten (Begruessung, Onboarding
// P6). Statisch hier statt im Pages-Barrel, damit die Rechtsseiten nicht in
// fremde Chunks wandern.
export { useCookieConsent } from './hooks/useCookieConsent'
