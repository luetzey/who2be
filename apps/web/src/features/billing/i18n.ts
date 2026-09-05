// Billing-Namespace-Registrierung (ADR-0029, Build-Zeit-Isolation).
//
// Bewusst NICHT in den zentralen `src/i18n/locales/{de,en}.json` — die werden
// immer ins Bundle gezogen. Die Billing-UI (und ihre Strings wie „Jetzt
// upgraden") darf im On-Prem-Build nicht auftauchen. Da `features/billing` nur
// im Cloud-Build dynamisch importiert wird (`__CLOUD_BUILD__`-Gate in
// OrgSettingsPage), lebt die Uebersetzung hier im Billing-Chunk und wird im
// On-Prem-Build mit-tree-geshaked. Side-Effect-Import in den Billing-Modulen
// registriert den Namespace, bevor eine Billing-Komponente rendert.
import i18n from '@/i18n'

const de = {
  panel: {
    title: 'Plan & Nutzung',
    statusActive: 'Aktiv',
    statusInactive: 'Inaktiv',
    quota: {
      unlimited: 'MCP-Kontingent: unbegrenzt',
      monthlyLabel: 'MCP-Reads diesen Monat',
      ariaLabel: 'MCP-Kontingent-Verbrauch',
    },
    rateLimit: 'Rate-Limit',
    validUntil: 'Gueltig bis',
    unlimited: 'unbegrenzt',
    plan: {
      label: 'Plan',
      priceLabel: 'Preis',
      entityLimitLabel: 'Entity-Limit je Workspace',
      unknown: 'unbekannt',
    },
    price: {
      free: 'Kostenlos',
      perMonth: '{{amount}} €/Monat',
    },
    features: {
      label: 'Features',
      none: 'keine',
    },
    proActive: '{{plan}} aktiv',
    upgrading: 'Weiterleitung…',
    upgrade: 'Jetzt upgraden',
  },
  expiry: {
    unlimited: 'unbegrenzt',
  },
  error: {
    checkoutFailed: 'Checkout fehlgeschlagen.',
    unknown: 'Unbekannter Fehler.',
  },
} as const

const en = {
  panel: {
    title: 'Plan & Usage',
    statusActive: 'Active',
    statusInactive: 'Inactive',
    quota: {
      unlimited: 'MCP quota: unlimited',
      monthlyLabel: 'MCP reads this month',
      ariaLabel: 'MCP quota usage',
    },
    rateLimit: 'Rate limit',
    validUntil: 'Valid until',
    unlimited: 'unlimited',
    plan: {
      label: 'Plan',
      priceLabel: 'Price',
      entityLimitLabel: 'Entity limit per workspace',
      unknown: 'unknown',
    },
    price: {
      free: 'Free',
      perMonth: '€{{amount}}/month',
    },
    features: {
      label: 'Features',
      none: 'none',
    },
    proActive: '{{plan}} active',
    upgrading: 'Redirecting…',
    upgrade: 'Upgrade now',
  },
  expiry: {
    unlimited: 'unlimited',
  },
  error: {
    checkoutFailed: 'Checkout failed.',
    unknown: 'Unknown error.',
  },
} as const

i18n.addResourceBundle('de', 'billing', de, true, true)
i18n.addResourceBundle('en', 'billing', en, true, true)
