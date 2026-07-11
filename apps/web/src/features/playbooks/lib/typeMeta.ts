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

export interface PlaybookTypeMeta {
  icon: LucideIcon
  /** Tailwind-Klassen der Pill-Tint (bg + fg) aus den Token-Farben. */
  tint: string
}

const TYPE_META: Record<string, PlaybookTypeMeta> = {
  workflow: { icon: Workflow, tint: 'bg-pill-catalog text-pill-catalog-fg' },
  instructions: { icon: ListOrdered, tint: 'bg-pill-playbook text-pill-playbook-fg' },
  checklist: { icon: ListChecks, tint: 'bg-pill-resource text-pill-resource-fg' },
  faq: { icon: MessageCircleQuestion, tint: 'bg-pill-persona text-pill-persona-fg' },
  snippet: { icon: Quote, tint: 'bg-pill-tools text-pill-tools-fg' },
  prompt: { icon: Sparkles, tint: 'bg-pill-date text-pill-date-fg' },
}

// Unbekannter/leerer Typ (Draft-Zustand ''): neutrale Tools-Tint.
const FALLBACK: PlaybookTypeMeta = TYPE_META.snippet

export function playbookTypeMeta(type: string | undefined): PlaybookTypeMeta {
  return (type !== undefined ? TYPE_META[type] : undefined) ?? FALLBACK
}
