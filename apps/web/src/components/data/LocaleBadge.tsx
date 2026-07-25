import { useTranslation } from 'react-i18next'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface LocaleBadgeProps {
  /** Element-Sprache (`locale`-Attribut aus der Read-Response). */
  locale: string | undefined
  className?: string
}

// Kompaktes Zwei-Buchstaben-Kuerzel fuer die dichten Listen-/Header-Zeilen
// (Design-Language §9.1: Badges bleiben knapp). Faellt fuer unbekannte
// Sprachen (offenes Backend-Sprach-Set, ADR-0045) auf die Grossschreibung
// des Rohwerts zurueck, statt nichts anzuzeigen.
function shortLabel(locale: string): string {
  return locale.length <= 2 ? locale.toUpperCase() : locale.slice(0, 2).toUpperCase()
}

/**
 * Sprach-Badge fuer Listen-Items und Detail-Header der fuenf Element-Typen
 * (Persona/Playbook/Resource/Tool/System-Prompt) — „Ein Element, eine
 * Sprache" (ADR-0045). `locale` fehlt bei aelteren Backend-Antworten
 * (Rollout-Uebergang) — dann rendert die Badge nichts, statt ein
 * irrefuehrendes Label zu zeigen.
 */
export function LocaleBadge({ locale, className }: LocaleBadgeProps) {
  const { t } = useTranslation('common')
  if (locale === undefined || locale === '') {
    return null
  }
  // `t()` faellt bei unbekannten Sprachen (offenes Set) auf den Rohwert
  // zurueck (i18next-Default), damit die Badge trotzdem etwas Sinnvolles
  // als A11y-Label traegt.
  const fullName = t(`contentLocale.${locale}`, { defaultValue: locale })
  return (
    <Badge
      variant="outline"
      className={cn('font-mono text-xs', className)}
      aria-label={fullName}
      title={fullName}
    >
      {shortLabel(locale)}
    </Badge>
  )
}
