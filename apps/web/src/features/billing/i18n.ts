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
    storage: {
      unlimited: 'Speicher: unbegrenzt',
      label: 'Belegter Speicher',
      ariaLabel: 'Speicher-Verbrauch',
    },
    rateLimit: 'Rate-Limit',
    validUntil: 'Gueltig bis',
    unlimited: 'unbegrenzt',
    plan: {
      label: 'Plan',
      priceLabel: 'Preis',
      entityLimitLabel: 'Entity-Limit je Workspace',
      tokenQuotaLabel: 'API-Tokens je Workspace',
      workspaceQuotaLabel: 'Workspaces je Organisation',
      unknown: 'unbekannt',
    },
    price: {
      free: 'Kostenlos',
      // Intl-Formatierung (i18next-Built-in): 9.99 wird im deutschen Locale zu
      // „9,99". Ohne den `number`-Formatter stuende hier der rohe
      // JS-Zahlenstring mit Dezimalpunkt.
      perMonth: '{{amount, number}} €/Monat',
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
  details: {
    title: 'Rechnungsdaten',
    intro: 'Diese Angaben stehen auf deinen Rechnungen.',
    requiredForUpgrade: 'Bitte zuerst die Rechnungsdaten speichern, dann kannst du upgraden.',
    edit: 'Bearbeiten',
    save: 'Rechnungsdaten speichern',
    saving: 'Speichert…',
    cancel: 'Abbrechen',
    countryPlaceholder: 'Land wählen',
    vatPlaceholder: 'z. B. {{prefix}}…',
    vatHelp: 'Wird bei VIES (EU-Kommission) geprüft. Ist VIES nicht erreichbar, speichern wir die Nummer als „ungeprüft“.',
    customerType: {
      business: 'Firma',
      consumer: 'Privatperson',
    },
    fields: {
      customer_type: 'Kundentyp',
      given_name: 'Vorname',
      family_name: 'Nachname',
      company_name: 'Firmenname',
      street: 'Straße und Hausnummer',
      postal_code: 'PLZ',
      city: 'Ort',
      country: 'Land',
      vatId: 'USt-IdNr.',
      vatIdOptional: 'USt-IdNr. (optional)',
    },
    vatStatus: {
      valid: 'geprüft',
      invalid: 'ungültig',
      unchecked: 'ungeprüft',
    },
    validation: {
      required: 'Pflichtfeld.',
      tooLong: 'Höchstens {{max}} Zeichen.',
      vatEuOnly: 'Eine USt-IdNr. gibt es nur für Adressen in der EU.',
      vatFormat: 'Das sieht nicht wie eine USt-IdNr. aus.',
      vatPrefix: 'Die USt-IdNr. muss zum Land passen und mit {{prefix}} beginnen.',
    },
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
    storage: {
      unlimited: 'Storage: unlimited',
      label: 'Storage used',
      ariaLabel: 'Storage usage',
    },
    rateLimit: 'Rate limit',
    validUntil: 'Valid until',
    unlimited: 'unlimited',
    plan: {
      label: 'Plan',
      priceLabel: 'Price',
      entityLimitLabel: 'Entity limit per workspace',
      tokenQuotaLabel: 'API tokens per workspace',
      workspaceQuotaLabel: 'Workspaces per organization',
      unknown: 'unknown',
    },
    price: {
      free: 'Free',
      perMonth: '€{{amount, number}}/month',
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
  details: {
    title: 'Billing details',
    intro: 'These details appear on your invoices.',
    requiredForUpgrade: 'Please save your billing details first, then you can upgrade.',
    edit: 'Edit',
    save: 'Save billing details',
    saving: 'Saving…',
    cancel: 'Cancel',
    countryPlaceholder: 'Select country',
    vatPlaceholder: 'e.g. {{prefix}}…',
    vatHelp: 'Checked with VIES (European Commission). If VIES is unavailable, we save the number as “unchecked”.',
    customerType: {
      business: 'Company',
      consumer: 'Individual',
    },
    fields: {
      customer_type: 'Customer type',
      given_name: 'First name',
      family_name: 'Last name',
      company_name: 'Company name',
      street: 'Street and number',
      postal_code: 'Postal code',
      city: 'City',
      country: 'Country',
      vatId: 'VAT ID',
      vatIdOptional: 'VAT ID (optional)',
    },
    vatStatus: {
      valid: 'verified',
      invalid: 'invalid',
      unchecked: 'unchecked',
    },
    validation: {
      required: 'Required.',
      tooLong: 'At most {{max}} characters.',
      vatEuOnly: 'VAT IDs exist only for addresses in the EU.',
      vatFormat: 'This does not look like a VAT ID.',
      vatPrefix: 'The VAT ID must match the country and start with {{prefix}}.',
    },
  },
  error: {
    checkoutFailed: 'Checkout failed.',
    unknown: 'Unknown error.',
  },
} as const

i18n.addResourceBundle('de', 'billing', de, true, true)
i18n.addResourceBundle('en', 'billing', en, true, true)
