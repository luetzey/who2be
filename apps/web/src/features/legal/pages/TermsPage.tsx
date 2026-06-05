import { useTranslation } from 'react-i18next'

import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Allgemeine Geschaeftsbedingungen / Terms of Service. Strukturgeruest mit
 * Platzhaltern — verbindlicher Text folgt vom Betreiber/Anwalt (CL4).
 */
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
      <LegalSection heading={t('terms.sections.scope.heading')}>
        <p>
          <Placeholder>{t('terms.sections.scope.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.subject.heading')}>
        <p>
          <Placeholder>{t('terms.sections.subject.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.registration.heading')}>
        <p>
          <Placeholder>{t('terms.sections.registration.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.pricing.heading')}>
        <p>
          <Placeholder>{t('terms.sections.pricing.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.termination.heading')}>
        <p>
          <Placeholder>{t('terms.sections.termination.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.withdrawal.heading')}>
        <p>
          <Placeholder>{t('terms.sections.withdrawal.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.obligations.heading')}>
        <p>
          <Placeholder>{t('terms.sections.obligations.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.availability.heading')}>
        <p>
          <Placeholder>{t('terms.sections.availability.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.liability.heading')}>
        <p>
          <Placeholder>{t('terms.sections.liability.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.privacy.heading')}>
        <p>
          <Placeholder>{t('terms.sections.privacy.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('terms.sections.final.heading')}>
        <p>
          <Placeholder>{t('terms.sections.final.body')}</Placeholder>
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
