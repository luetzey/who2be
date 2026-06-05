import { useTranslation } from 'react-i18next'

import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Impressum / Anbieterkennzeichnung (§ 5 DDG, § 18 MStV). Geruest mit
 * Platzhaltern — finaler Text kommt vom Betreiber/Anwalt (CL4).
 */
export function ImpressumPage() {
  const { t } = useTranslation('legal')

  return (
    <LegalArticle title={t('impressum.title')}>
      <LegalSection heading={t('impressum.sections.legalNotice.heading')}>
        <p>
          <Placeholder>{t('impressum.sections.legalNotice.companyName')}</Placeholder>
          <br />
          <Placeholder>{t('impressum.sections.legalNotice.street')}</Placeholder>
          <br />
          <Placeholder>{t('impressum.sections.legalNotice.city')}</Placeholder>
          <br />
          <Placeholder>{t('impressum.sections.legalNotice.country')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('impressum.sections.representative.heading')}>
        <p>
          <Placeholder>{t('impressum.sections.representative.name')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('impressum.sections.contact.heading')}>
        <p>
          {t('impressum.sections.contact.phoneLabel')}{' '}
          <Placeholder>{t('impressum.sections.contact.phone')}</Placeholder>
          <br />
          {t('impressum.sections.contact.emailLabel')}{' '}
          <Placeholder>{t('impressum.sections.contact.email')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('impressum.sections.register.heading')}>
        <p>
          {t('impressum.sections.register.registryLabel')}{' '}
          <Placeholder>{t('impressum.sections.register.registry')}</Placeholder>
          <br />
          {t('impressum.sections.register.courtLabel')}{' '}
          <Placeholder>{t('impressum.sections.register.court')}</Placeholder>
          <br />
          {t('impressum.sections.register.numberLabel')}{' '}
          <Placeholder>{t('impressum.sections.register.number')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('impressum.sections.vatId.heading')}>
        <p>
          {t('impressum.sections.vatId.label')}{' '}
          <Placeholder>{t('impressum.sections.vatId.value')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('impressum.sections.responsible.heading')}>
        <p>
          <Placeholder>{t('impressum.sections.responsible.name')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('impressum.sections.dispute.heading')}>
        <p>
          {t('impressum.sections.dispute.text1')}{' '}
          <Placeholder>{t('impressum.sections.dispute.platformLink')}</Placeholder>.{' '}
          {t('impressum.sections.dispute.text2')}{' '}
          <Placeholder>{t('impressum.sections.dispute.participation')}</Placeholder>
          {t('impressum.sections.dispute.text3')}
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
