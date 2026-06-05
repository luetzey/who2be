import { useTranslation } from 'react-i18next'

import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Auftragsverarbeitungsvertrag (AVV / DPA, Art. 28 DSGVO) fuer geschaeftliche
 * Kunden, die Who2Be zur Verarbeitung eigener personenbezogener Daten nutzen.
 * Geruest mit Platzhaltern — verbindliche Fassung folgt vom Betreiber/Anwalt.
 */
export function DpaPage() {
  const { t } = useTranslation('legal')

  return (
    <LegalArticle
      title={t('dpa.title')}
      intro={<p>{t('dpa.intro')}</p>}
    >
      <LegalSection heading={t('dpa.sections.subject.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.subject.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.purpose.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.purpose.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.dataTypes.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.dataTypes.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.dataSubjects.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.dataSubjects.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.processorObligations.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.processorObligations.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.tom.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.tom.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.subprocessors.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.subprocessors.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.transfers.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.transfers.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.dataSubjectRights.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.dataSubjectRights.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.deletion.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.deletion.body')}</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading={t('dpa.sections.audits.heading')}>
        <p>
          <Placeholder>{t('dpa.sections.audits.body')}</Placeholder>
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
