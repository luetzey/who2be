// SkillsComingSoon — "Coming Soon"-Platzhalter, der die vorlaeufig
// deaktivierte Skills-Funktion ersetzt (ADR-0026). Skills sind aktuell nicht
// editier- oder nutzbar; der bestehende `skills`-Inhalt bleibt im Datenmodell
// unangetastet erhalten (Backward-Compat). Reaktivierung: diesen Platzhalter
// wieder durch PersonaSkillsEditor (Formular) bzw. PersonaSkillsTable
// (Detail-Page) ersetzen und das Backend-Flag `SKILLS_ENABLED` flippen.

import { Sparkles } from 'lucide-react'

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
  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Sparkles className="size-4" />
        <span>Skills</span>
        <Badge variant="secondary">Coming Soon</Badge>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-dashed p-6">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-muted-foreground" />
        <Badge variant="secondary">Coming Soon</Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        Skills bekommen bald ein eigenes, versioniertes Format — als paketierte,
        wiederverwendbare Fähigkeit für deine Agenten. Die Funktion ist aktuell
        noch nicht aktiv.
      </p>
    </div>
  )
}
