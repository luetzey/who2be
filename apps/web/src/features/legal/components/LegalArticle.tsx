import type { ReactNode } from 'react'

import { useTranslation } from 'react-i18next'

import { Container } from '@/components/layout/Container'

import { Placeholder } from './Placeholder'

interface LegalArticleProps {
  title: string
  /** Optionaler Einleitungstext unter dem Titel (z. B. Geltungsbereich). */
  intro?: ReactNode
  children: ReactNode
}

/**
 * Einheitlicher Rahmen fuer alle Rechtsseiten: zentrierte Lesespalte, Titel +
 * „Stand"-Zeile (Platzhalter) und Slot fuer `LegalSection`-Bloecke.
 */
export function LegalArticle({ title, intro, children }: LegalArticleProps) {
  const { t } = useTranslation('legal')

  return (
    <Container className="max-w-3xl">
      {/* #567 (§4.4 Punkt 1 + 5): `break-words` einmal am gemeinsamen
          Prose-Traeger statt je Seite — es deckt lange URLs, E-Mail- und
          Registerangaben in allen vier Rechtstexten und die Placeholder-Chips
          in einem Zug ab. `break-all` waere hier schaedlich: es zerlegt auch
          normale Woerter und macht deutschen Fliesstext unleserlich. */}
      <article className="flex flex-col gap-8 break-words">
        <header className="flex flex-col gap-2 border-b pb-6">
          {/* #567: `text-3xl` (30px) rendert den laengsten deutschen Titel
              gemessen 337px breit gegen 288px Lesespalte (AGB-Seite, 320px
              Viewport) und erzeugte horizontalen Body-Scroll. Mit `text-2xl`
              sind es gemessen 288px; ab `sm` bleibt der bisherige Zustand. */}
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
          <p className="text-sm text-muted-foreground">
            {t('article.lastUpdated')}{' '}
            <Placeholder>{t('article.lastUpdatedPlaceholder')}</Placeholder>
          </p>
          {intro ? <div className="text-sm leading-relaxed text-muted-foreground">{intro}</div> : null}
        </header>
        {children}
      </article>
    </Container>
  )
}

interface LegalSectionProps {
  heading: string
  children: ReactNode
}

/** Nummerierbarer Abschnitt innerhalb eines `LegalArticle`. */
export function LegalSection({ heading, children }: LegalSectionProps) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xl font-semibold tracking-tight">{heading}</h2>
      <div className="flex flex-col gap-3 text-sm leading-relaxed text-foreground/90">{children}</div>
    </section>
  )
}
