import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Allgemeine Geschaeftsbedingungen / Terms of Service. Strukturgeruest mit
 * Platzhaltern — verbindlicher Text folgt vom Betreiber/Anwalt (CL4).
 */
export function TermsPage() {
  return (
    <LegalArticle
      title="Allgemeine Geschaeftsbedingungen (AGB)"
      intro={
        <p>
          Diese AGB regeln die Nutzung von Who2Be durch{' '}
          <Placeholder>Beschreibung der Nutzergruppe (Verbraucher/Unternehmer)</Placeholder>.
        </p>
      }
    >
      <LegalSection heading="§ 1 Geltungsbereich">
        <p>
          <Placeholder>
            Geltungsbereich, Vertragspartner, Vorrang individueller Abreden, Einbeziehung
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 2 Vertragsgegenstand & Leistungsbeschreibung">
        <p>
          <Placeholder>
            Beschreibung des SaaS-Angebots, Leistungsumfang je Plan (Free/Pro), Verfuegbarkeit/SLA
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 3 Registrierung & Konto">
        <p>
          <Placeholder>
            Registrierungspflicht, Wahrheit der Angaben, Geheimhaltung der Zugangsdaten,
            Mindestalter
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 4 Preise & Zahlungsbedingungen">
        <p>
          <Placeholder>
            Preise, Abrechnungszeitraum, Zahlungsdienstleister (Mollie), Faelligkeit, Verzug,
            Steuern
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 5 Laufzeit & Kuendigung">
        <p>
          <Placeholder>
            Vertragslaufzeit, Verlaengerung, ordentliche/ausserordentliche Kuendigung,
            Kuendigung zum Periodenende
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 6 Widerrufsrecht">
        <p>
          <Placeholder>
            Widerrufsbelehrung fuer Verbraucher inkl. Muster-Widerrufsformular bzw. Hinweis,
            falls nicht einschlaegig
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 7 Pflichten der Nutzer & zulaessige Nutzung">
        <p>
          <Placeholder>
            Acceptable-Use-Policy, verbotene Inhalte, Verantwortung fuer eingestellte Daten
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 8 Verfuegbarkeit, Aenderungen & Wartung">
        <p>
          <Placeholder>Verfuegbarkeitszusage, Wartungsfenster, Aenderungsvorbehalt</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 9 Haftung">
        <p>
          <Placeholder>
            Haftungsregelung (Vorsatz/grobe Fahrlaessigkeit, Kardinalpflichten, Begrenzung)
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 10 Datenschutz">
        <p>
          <Placeholder>
            Verweis auf Datenschutzerklaerung und ggf. Auftragsverarbeitungsvertrag (DPA)
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="§ 11 Schlussbestimmungen">
        <p>
          <Placeholder>
            Anwendbares Recht, Gerichtsstand, salvatorische Klausel, Aenderungen der AGB
          </Placeholder>
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
