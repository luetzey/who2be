import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Impressum / Anbieterkennzeichnung (§ 5 DDG, § 18 MStV). Geruest mit
 * Platzhaltern — finaler Text kommt vom Betreiber/Anwalt (CL4).
 */
export function ImpressumPage() {
  return (
    <LegalArticle title="Impressum">
      <LegalSection heading="Angaben gemaess § 5 DDG">
        <p>
          <Placeholder>Firmenname / Rechtsform</Placeholder>
          <br />
          <Placeholder>Strasse und Hausnummer</Placeholder>
          <br />
          <Placeholder>PLZ und Ort</Placeholder>
          <br />
          <Placeholder>Land</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="Vertreten durch">
        <p>
          <Placeholder>Name der vertretungsberechtigten Person(en)</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="Kontakt">
        <p>
          Telefon: <Placeholder>Telefonnummer</Placeholder>
          <br />
          E-Mail: <Placeholder>Kontakt-E-Mail</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="Registereintrag">
        <p>
          Eintragung im <Placeholder>Handels-/Vereinsregister</Placeholder>
          <br />
          Registergericht: <Placeholder>zustaendiges Registergericht</Placeholder>
          <br />
          Registernummer: <Placeholder>Registernummer</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="Umsatzsteuer-ID">
        <p>
          Umsatzsteuer-Identifikationsnummer gemaess § 27a UStG:{' '}
          <Placeholder>USt-IdNr.</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="Verantwortlich i.S.d. § 18 Abs. 2 MStV">
        <p>
          <Placeholder>Name und Anschrift der verantwortlichen Person</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="EU-Streitschlichtung">
        <p>
          Die Europaeische Kommission stellt eine Plattform zur
          Online-Streitbeilegung (OS) bereit:{' '}
          <Placeholder>Link zur OS-Plattform</Placeholder>. Wir sind{' '}
          <Placeholder>bereit / nicht bereit / nicht verpflichtet</Placeholder>, an einem
          Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
