/// <reference types="vite/client" />

// Build-Zeit-Konstante (vite `define`, ADR-0029): true nur im Cloud-Build.
// Steuert das Tree-Shaking der Billing-UI aus dem On-Prem-Bundle.
declare const __CLOUD_BUILD__: boolean
