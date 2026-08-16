import { CircleCheck, CircleDashed, CircleHelp, Clock } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { NodeStatus, NodeTier } from '@/api/types'
import { Badge } from '@/components/ui/badge'

// Tier und Status tragen jeweils ein eigenes Icon: Farbe ist nie der alleinige
// Informationstraeger (A11y-Minimum der Designsprache). Die Leiter ist geordnet
// — `verified` ist die menschlich bestaetigte Stufe und bewusst kein
// Agenten-Recht.
const TIER_ICON: Record<NodeTier, LucideIcon> = {
  verified: CircleCheck,
  derived: CircleDashed,
  hypothesis: CircleHelp,
}

const TIER_LABEL: Record<NodeTier, string> = {
  verified: 'kb.tierVerified',
  derived: 'kb.tierDerived',
  hypothesis: 'kb.tierHypothesis',
}

export function TierBadge({ tier }: { tier: NodeTier }) {
  const { t } = useTranslation('workarea')
  const Icon = TIER_ICON[tier]
  return (
    <Badge variant={tier === 'verified' ? 'default' : 'secondary'} className="gap-1">
      <Icon className="size-3" />
      {t(TIER_LABEL[tier])}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: NodeStatus }) {
  const { t } = useTranslation('workarea')
  // `live` ist der Normalfall und braucht keine Auszeichnung — nur der
  // ueberholte Zustand ist eine Information.
  if (status === 'live') return null
  return (
    <Badge variant="outline" className="gap-1">
      <Clock className="size-3" />
      {t('kb.statusStale')}
    </Badge>
  )
}
