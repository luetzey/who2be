import { useTranslation } from 'react-i18next'

import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Datenschutzerklaerung (Art. 13/14 DSGVO). Geruest mit Platzhaltern; die
 * konkreten Verarbeitungen/Empfaenger traegt der Betreiber/Anwalt nach (CL4).
 */
export function PrivacyPage() {
  const { t } = useTranslation('legal')

  return (
    <LegalArticle
      title={t('privacy.title')}
      intro={<p>{t('privacy.intro')}</p>}
    >
      <LegalSection heading={t('privacy.sections.controller.heading')}>
        <p>
          {t('privacy.sections.controller.text1')}
          <br />
          <Placeholder>{t('privacy.sections.controller.contactPlaceholder')}</Placeholder>
          <br />
          {t('privacy.sections.controller.dpoLabel')}{' '}
          <Placeholder>{t('privacy.sections.controller.dpoPlaceholder')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.hosting.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.hosting.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.serverLogs.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.serverLogs.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.cookies.heading')}>
        <p>
          {t('privacy.sections.cookies.text1')}
          <br />
          <Placeholder>{t('privacy.sections.cookies.listPlaceholder')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.account.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.account.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.auth.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.auth.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.payment.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.payment.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.email.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.email.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.processors.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.processors.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.retention.heading')}>
        <p>
          <Placeholder>{t('privacy.sections.retention.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('privacy.sections.rights.heading')}>
        <p>
          {t('privacy.sections.rights.text1')}
          <br />
          {t('privacy.sections.rights.authorityLabel')}{' '}
          <Placeholder>{t('privacy.sections.rights.authorityPlaceholder')}</Placeholder>
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
