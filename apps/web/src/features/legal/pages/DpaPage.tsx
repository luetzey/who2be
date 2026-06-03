import { LegalArticle, LegalSection } from '../components/LegalArticle'
import { Placeholder } from '../components/Placeholder'

/**
 * Auftragsverarbeitungsvertrag (AVV / DPA, Art. 28 DSGVO) fuer geschaeftliche
 * Kunden, die Who2Be zur Verarbeitung eigener personenbezogener Daten nutzen.
 * Geruest mit Platzhaltern — verbindliche Fassung folgt vom Betreiber/Anwalt.
 */
export function DpaPage() {
  return (
    <LegalArticle
      title="Vertrag zur Auftragsverarbeitung (DPA)"
      intro={
        <p>
          Dieser Vertrag konkretisiert die Pflichten nach Art. 28 DSGVO, wenn der Kunde
          (Verantwortlicher) Who2Be (Auftragsverarbeiter) mit der Verarbeitung personenbezogener
          Daten beauftragt. Er wird Bestandteil des Hauptvertrags.
        </p>
      }
    >
      <LegalSection heading="1. Gegenstand & Dauer">
        <p>
          <Placeholder>
            Gegenstand der Verarbeitung, Laufzeit (gekoppelt an Hauptvertrag), Kuendigung
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="2. Art & Zweck der Verarbeitung">
        <p>
          <Placeholder>
            beschriebene Verarbeitungstaetigkeiten und Zweck der Auftragsverarbeitung
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="3. Art der personenbezogenen Daten">
        <p>
          <Placeholder>
            Datenkategorien (z. B. Konto-/Profildaten, Inhalte der Personas/Playbooks/Resources)
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="4. Kategorien betroffener Personen">
        <p>
          <Placeholder>
            betroffene Personen (z. B. Mitarbeitende, Kunden des Verantwortlichen)
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="5. Pflichten des Auftragsverarbeiters">
        <p>
          <Placeholder>
            Weisungsbindung, Vertraulichkeit, Unterstuetzung bei Betroffenenrechten, Meldepflichten
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="6. Technische & organisatorische Massnahmen (TOM)">
        <p>
          <Placeholder>
            Verweis auf TOM-Anlage (Verschluesselung, Zugriffskontrolle, RLS, Backups, Logging)
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="7. Unterauftragsverarbeiter">
        <p>
          <Placeholder>
            Liste zugelassener Subunternehmer (Hosting/Auth/Mail/Payment), Genehmigungsverfahren
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="8. Drittlandtransfers">
        <p>
          <Placeholder>
            Angaben zu Uebermittlungen in Drittlaender und Garantien (SCC) sofern einschlaegig
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="9. Betroffenenrechte & Unterstuetzung">
        <p>
          <Placeholder>
            Unterstuetzung des Verantwortlichen bei Auskunft/Loeschung/Datenexport
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="10. Loeschung & Rueckgabe nach Vertragsende">
        <p>
          <Placeholder>
            Loesch-/Rueckgabekonzept nach Vertragsende inkl. Fristen
          </Placeholder>
        </p>
      </LegalSection>

      <LegalSection heading="11. Nachweise & Audits">
        <p>
          <Placeholder>
            Nachweispflichten, Audit-Rechte des Verantwortlichen, Zertifizierungen
          </Placeholder>
        </p>
      </LegalSection>
    </LegalArticle>
  )
}
