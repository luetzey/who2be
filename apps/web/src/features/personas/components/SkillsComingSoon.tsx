// SkillsComingSoon — "Coming Soon"-Platzhalter, der die vorlaeufig
// deaktivierte Skills-Funktion ersetzt (ADR-0026). Skills sind aktuell nicht
// editier- oder nutzbar; der bestehende `skills`-Inhalt bleibt im Datenmodell
// unangetastet erhalten (Backward-Compat). Reaktivierung: diesen Platzhalter
// wieder durch PersonaSkillsEditor (Formular) bzw. PersonaSkillsTable
// (Detail-Page) ersetzen und das Backend-Flag `SKILLS_ENABLED` flippen.

import { Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Badge } from '@/components/ui/badge'

interface SkillsComingSoonProps {
  /**
   * Kompakte, dezente Variante (eine gedaempfte Zeile statt Box mit Erklaer-
   * text). Fuer die Detail-Page gedacht, wo der Hinweis nicht dominieren soll;
   * der Editor nutzt die Default-Box.
   */
  compact?: boolean
}

export function SkillsComingSoon({ compact = false }: SkillsComingSoonProps) {
  const { t } = useTranslation('personas')
  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Sparkles className="size-4" />
        <span>{t('skillsComingSoon.label')}</span>
        <Badge variant="secondary">{t('skillsComingSoon.badge')}</Badge>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-dashed p-6">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-muted-foreground" />
        <Badge variant="secondary">{t('skillsComingSoon.badge')}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        {t('skillsComingSoon.description')}
      </p>
    </div>
  )
}
