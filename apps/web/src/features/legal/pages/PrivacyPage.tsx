import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Datenschutzerklaerung (Art. 13/14 DSGVO). Geruest mit Platzhaltern; die
 * konkreten Verarbeitungen/Empfaenger traegt der Betreiber/Anwalt nach (CL4).
 */
export function PrivacyPage() {
  return (
    <LegalArticle
      title="Datenschutzerklaerung"
      intro={
        <p>
          Diese Erklaerung informiert ueber die Verarbeitung personenbezogener Daten bei der
          Nutzung von Who2Be.
        </p>
      }
    >
      <LegalSection heading="1. Verantwortlicher">
        <p>
          Verantwortlich im Sinne der DSGVO ist:
          <br />
          <Placeholder>Name / Anschrift / Kontakt des Verantwortlichen</Placeholder>
          <br />
          Datenschutzbeauftragter: <Placeholder>Kontakt DSB oder „nicht benannt"</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="2. Hosting & Infrastruktur">
        <p>
          <Placeholder>
            Hosting-Anbieter (z. B. Hetzner), Serverstandort, Auftragsverarbeitung, Rechtsgrundlage
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="3. Zugriffsdaten / Server-Logs">
        <p>
          <Placeholder>
            erhobene Log-Daten, Zweck, Speicherdauer, Rechtsgrundlage Art. 6 Abs. 1 lit. f DSGVO
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="4. Cookies & Einwilligung">
        <p>
          Wir setzen technisch notwendige Cookies (Session/Authentifizierung) auf Grundlage von §
          25 Abs. 2 TDDDG. Optionale Cookies werden nur nach Einwilligung gesetzt (§ 25 Abs. 1
          TDDDG, Art. 6 Abs. 1 lit. a DSGVO); die Einwilligung kann jederzeit mit Wirkung fuer die
          Zukunft widerrufen werden.
          <br />
          <Placeholder>Auflistung konkreter Cookies / Speicherdauer / Widerrufsweg</Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="5. Registrierung & Konto">
        <p>
          <Placeholder>
            verarbeitete Konto-/Stammdaten, Zweck (Vertragserfuellung Art. 6 Abs. 1 lit. b),
            Speicherdauer
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="6. Authentifizierung (Supabase/GoTrue)">
        <p>
          <Placeholder>
            Auth-Dienst, verarbeitete Daten, ggf. OAuth-Provider (Google/GitHub), Rechtsgrundlage
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="7. Zahlungsabwicklung">
        <p>
          <Placeholder>
            Zahlungsdienstleister (Mollie), uebermittelte Daten, eigene Datenschutzerklaerung des
            Anbieters, Rechtsgrundlage
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="8. E-Mail-Versand (Transaktionsmails)">
        <p>
          <Placeholder>
            SMTP-/Mail-Provider, Anlaesse (Verify/Invite/Reset), Rechtsgrundlage
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="9. Empfaenger & Auftragsverarbeiter">
        <p>
          <Placeholder>
            Liste der Auftragsverarbeiter, Drittlandtransfers + Garantien (SCC) sofern einschlaegig
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="10. Speicherdauer">
        <p>
          <Placeholder>
            allgemeine Loeschkonzepte, gesetzliche Aufbewahrungsfristen
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="11. Deine Rechte">
        <p>
          Du hast das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Loeschung (Art. 17),
          Einschraenkung (Art. 18), Datenuebertragbarkeit (Art. 20) und Widerspruch (Art. 21)
          sowie das Recht auf Beschwerde bei einer Aufsichtsbehoerde (Art. 77).
          <br />
          Zustaendige Aufsichtsbehoerde: <Placeholder>zustaendige Datenschutzbehoerde</Placeholder>
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
