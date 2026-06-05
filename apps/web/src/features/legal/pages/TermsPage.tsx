import type { ReactNode } from 'react'

import { useTranslation } from 'react-i18next'

import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Allgemeine Geschaeftsbedingungen / Terms of Service. Strukturgeruest mit
 * Platzhaltern — verbindlicher Text folgt vom Betreiber/Anwalt (CL4).
 *
 * Struktur (WP-I): drei Abschnitte als `LegalSection` (h2) — A. Allgemein,
 * B. Verbraucher (B2C), C. Unternehmer (B2B). Einzelne Klauseln rendern als
 * `Clause` (h3) darunter, damit die Heading-Hierarchie h1>h2>h3 sauber bleibt.
 * Inhalte bleiben markierte `<Placeholder>` (keine erfundenen Rechtstexte).
 */

/** Einzelne AGB-Klausel (§) innerhalb eines Gruppen-Abschnitts. */
function Clause({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-base font-semibold tracking-tight text-foreground">{heading}</h3>
      <div className="flex flex-col gap-2 text-sm leading-relaxed text-foreground/90">
        {children}
      </div>
    </div>
  )
}

export function TermsPage() {
  const { t } = useTranslation('legal')

  return (
    <LegalArticle
      title={t('terms.title')}
      intro={
        <p>
          {t('terms.intro')}{' '}
          <Placeholder>{t('terms.introUserGroup')}</Placeholder>
          {t('terms.introPeriod')}
        </p>
      }
    >
      {/* A. Allgemeine Bestimmungen — fuer alle Nutzer */}
      <LegalSection heading={t('terms.groups.general.heading')}>
        <Clause heading={t('terms.sections.scope.heading')}>
          <p>
            <Placeholder>{t('terms.sections.scope.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.subject.heading')}>
          <p>
            <Placeholder>{t('terms.sections.subject.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.registration.heading')}>
          <p>
            <Placeholder>{t('terms.sections.registration.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.pricing.heading')}>
          <p>
            <Placeholder>{t('terms.sections.pricing.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.termination.heading')}>
          <p>
            <Placeholder>{t('terms.sections.termination.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.obligations.heading')}>
          <p>
            <Placeholder>{t('terms.sections.obligations.body')}</Placeholder>
          </p>
        </Clause>
        {/* SLA-Geruest (Werte als Platzhalter) — als Unterpunkte des
            Verfuegbarkeits-Paragraphen, kein eigener Route-Eintrag. */}
        <Clause heading={t('terms.sections.availability.heading')}>
          <p>
            <Placeholder>{t('terms.sections.availability.body')}</Placeholder>
          </p>
          <p className="font-medium text-foreground">{t('terms.sections.availability.slaIntro')}</p>
          <dl className="flex flex-col gap-2">
            <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
              <dt className="font-medium">{t('terms.sections.availability.slaUptimeLabel')}</dt>
              <dd>
                <Placeholder>{t('terms.sections.availability.slaUptime')}</Placeholder>
              </dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
              <dt className="font-medium">{t('terms.sections.availability.slaResponseLabel')}</dt>
              <dd>
                <Placeholder>{t('terms.sections.availability.slaResponse')}</Placeholder>
              </dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
              <dt className="font-medium">
                {t('terms.sections.availability.slaMaintenanceLabel')}
              </dt>
              <dd>
                <Placeholder>{t('terms.sections.availability.slaMaintenance')}</Placeholder>
              </dd>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
              <dt className="font-medium">{t('terms.sections.availability.slaCreditsLabel')}</dt>
              <dd>
                <Placeholder>{t('terms.sections.availability.slaCredits')}</Placeholder>
              </dd>
            </div>
          </dl>
        </Clause>
        <Clause heading={t('terms.sections.liability.heading')}>
          <p>
            <Placeholder>{t('terms.sections.liability.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.privacy.heading')}>
          <p>
            <Placeholder>{t('terms.sections.privacy.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.sections.final.heading')}>
          <p>
            <Placeholder>{t('terms.sections.final.body')}</Placeholder>
          </p>
        </Clause>
      </LegalSection>

      {/* B. Zusaetzliche Bestimmungen fuer Verbraucher (B2C) */}
      <LegalSection heading={t('terms.groups.consumer.heading')}>
        <p className="text-sm text-muted-foreground">{t('terms.groups.consumer.note')}</p>
        <Clause heading={t('terms.consumerSections.withdrawal.heading')}>
          <p>
            <Placeholder>{t('terms.consumerSections.withdrawal.body')}</Placeholder>
          </p>
          <p>
            <span className="font-medium">
              {t('terms.consumerSections.withdrawal.formLabel')}
            </span>{' '}
            <Placeholder>{t('terms.consumerSections.withdrawal.form')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.consumerSections.einvoice.heading')}>
          <p>
            <Placeholder>{t('terms.consumerSections.einvoice.body')}</Placeholder>
          </p>
          <p>
            <span className="font-medium">
              {t('terms.consumerSections.einvoice.consentLabel')}
            </span>{' '}
            <Placeholder>{t('terms.consumerSections.einvoice.consent')}</Placeholder>
          </p>
        </Clause>
      </LegalSection>

      {/* C. Zusaetzliche Bestimmungen fuer Unternehmer (B2B) */}
      <LegalSection heading={t('terms.groups.business.heading')}>
        <p className="text-sm text-muted-foreground">{t('terms.groups.business.note')}</p>
        <Clause heading={t('terms.businessSections.deviations.heading')}>
          <p>
            <Placeholder>{t('terms.businessSections.deviations.body')}</Placeholder>
          </p>
        </Clause>
        <Clause heading={t('terms.businessSections.jurisdiction.heading')}>
          <p>
            <Placeholder>{t('terms.businessSections.jurisdiction.body')}</Placeholder>
          </p>
        </Clause>
      </LegalSection>
    </LegalArticle>
  )
}
