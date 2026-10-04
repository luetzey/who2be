// Design-Handoff „Playbooks-Redesign": jeder Playbook-Typ bekommt ein
// Lucide-Icon + eine Pill-Tint (Tokens aus globals.css, @theme-Mapping
// `--color-pill-*`). Die Zuordnung ist die verbindliche Quelle fuer
// Typ-Icon-Chips in Uebersicht, Detail-Hero und Leerzustand.

import {
  ListChecks,
  ListOrdered,
  MessageCircleQuestion,
  Quote,
  Sparkles,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

import type { EntityTone } from '@/components/data/EntityIcon'

export interface PlaybookTypeMeta {
  icon: LucideIcon
  /**
   * Dieselbe Pill-Familie wie `tint`, als `EntityTone` fuer die geteilte
   * Icon-Kachel im `DetailHeader` (Audit A8).
   */
  tone: EntityTone
  /** Tailwind-Klassen der Pill-Tint (bg + fg) aus den Token-Farben. */
  tint: string
}

// `tint` bleibt ein vollstaendiges Klassen-Literal (Tailwind erkennt nur
// solche); `tone` benennt dieselbe Familie — beide pro Zeile gleich halten.
const TYPE_META: Record<string, PlaybookTypeMeta> = {
  workflow: { icon: Workflow, tone: 'catalog', tint: 'bg-pill-catalog text-pill-catalog-fg' },
  instructions: {
    icon: ListOrdered,
    tone: 'playbook',
    tint: 'bg-pill-playbook text-pill-playbook-fg',
  },
  checklist: { icon: ListChecks, tone: 'resource', tint: 'bg-pill-resource text-pill-resource-fg' },
  faq: { icon: MessageCircleQuestion, tone: 'persona', tint: 'bg-pill-persona text-pill-persona-fg' },
  snippet: { icon: Quote, tone: 'tools', tint: 'bg-pill-tools text-pill-tools-fg' },
  prompt: { icon: Sparkles, tone: 'date', tint: 'bg-pill-date text-pill-date-fg' },
}

// Unbekannter/leerer Typ (Draft-Zustand ''): neutrale Tools-Tint.
const FALLBACK: PlaybookTypeMeta = TYPE_META.snippet

export function playbookTypeMeta(type: string | undefined): PlaybookTypeMeta {
  return (type !== undefined ? TYPE_META[type] : undefined) ?? FALLBACK
}
