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
      <article className="flex flex-col gap-8">
        <header className="flex flex-col gap-2 border-b pb-6">
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
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
